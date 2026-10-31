"""Trông máy trung chuyển (Chặng 4): xem tình trạng, cập nhật bằng một lệnh, đặt khoá và báo sập.

    .venv\\Scripts\\python.exe tools\\relay_ops.py status [--log 20] [--url wss://...]
    .venv\\Scripts\\python.exe tools\\relay_ops.py deploy   # test -> wrangler deploy -> /v1/health
    .venv\\Scripts\\python.exe tools\\relay_ops.py setup    # tạo khoá, đặt lên Cloudflare, báo sập

Khoá xem tình trạng (ADMIN_KEY) lấy từ biến NEONPOOL_ADMIN_KEY, hoặc file
%APPDATA%\\NeonPool\\relay-admin.key (ngoài git). Địa chỉ mặc định là máy trung chuyển thật
(`config.NET_RELAY_URL`; NEONPOOL_RELAY_URL thay). Giao thức: docs/ARCHITECTURE.md (Vận hành).
"""

from __future__ import annotations

import argparse
import json
import os
import secrets
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from game.net import relay  # noqa: E402  (after the path: this file is run as a script)

CLOUDFLARE_DIR = ROOT / "server" / "cloudflare"
KEY_ENV = "NEONPOOL_ADMIN_KEY"
STATE_WORDS = {
    "waiting": "đang chờ khách",
    "playing": "đang chơi",
    "host_away": "chủ phòng đang nối lại",
}
EVENT_WORDS = {
    "room_new": "phòng mới",
    "guest_in": "khách vào",
    "guest_out": "khách ra",
    "guest_replaced": "khách cũ im quá lâu nên bị thay",
    "host_out": "chủ phòng mất kết nối",
    "host_back": "chủ phòng nối lại",
    "room_end": "phòng đóng",
}
WHY_WORDS = {
    "host_closed": "chủ phòng tự đóng",
    "idle": "chờ quá 30 phút không ai vào",
    "expired": "chủ phòng mất kết nối quá 90 giây",
    "host_link": "đường nối của chủ phòng đứt",
    "guest_link": "đường nối của khách đứt",
}


# --- the key ---
def key_path() -> Path:
    if os.environ.get("NEONPOOL_ADMIN_KEY_FILE"):
        return Path(os.environ["NEONPOOL_ADMIN_KEY_FILE"])
    base = os.environ.get("APPDATA")
    return (Path(base) if base else Path.home()) / "NeonPool" / "relay-admin.key"


def read_key() -> str | None:
    """The admin key: the environment first, then the key file; None when there is neither."""
    given = os.environ.get(KEY_ENV, "").strip()
    if given:
        return given
    try:
        return key_path().read_text(encoding="utf-8").strip() or None
    except OSError:
        return None


# --- asking the relay ---
def fetch(url: str, path: str, timeout: float = 10.0) -> tuple[int, object]:
    """(HTTP status, JSON or text) of a plain request; status 0 when there is no answer."""
    request = urllib.request.Request(
        f"{relay._http_base(url)}{path}", headers={"User-Agent": relay.USER_AGENT}
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as r:
            status, text = r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        status, text = exc.code, exc.read().decode("utf-8", "replace")
    except OSError as exc:
        return 0, str(exc)
    try:
        return status, json.loads(text)
    except ValueError:
        return status, text


# --- the words ---
def _age(seconds: int) -> str:
    if seconds < 60:
        return f"{seconds} giây"
    if seconds < 3600:
        return f"{seconds // 60} phút"
    return f"{seconds // 3600} giờ {seconds % 3600 // 60} phút"


def _count(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def render_status(body: dict, url: str = "") -> str:
    """The status JSON as a few lines of text."""
    today = body.get("today", {})
    rooms = body.get("rooms", [])
    out = [
        f"Máy trung chuyển {url}".rstrip() + f" — ngày {body.get('day', '?')} (giờ UTC)",
        f"Hôm nay: {today.get('rooms', 0)} phòng mới · {today.get('joins', 0)} lượt vào · "
        f"{_count(today.get('frames', 0))} khung tin · "
        f"{str(today.get('used_pct', 0)).replace('.', ',')}% mức miễn phí (ước, thấp hơn thật)",
        f"Đang có {len(rooms)} phòng" + (":" if rooms else "."),
    ]
    for room in rooms:
        rtt, state = room.get("rtt_ms"), room.get("state", "?")
        out.append(
            f"  {room.get('code', '?'):5}{STATE_WORDS.get(state, state):24}"
            f"{_age(int(room.get('age_s', 0))):>12}   ping {'--' if rtt is None else rtt} ms"
        )
    log = body.get("log", [])
    out.append("Nhật ký (mới nhất ở cuối):" if log else "Nhật ký: trống.")
    for line in log:
        stamp = time.strftime("%H:%M:%S", time.localtime(line.get("at", 0) / 1000))
        text = EVENT_WORDS.get(line.get("ev"), line.get("ev", "?"))
        if line.get("why"):
            text += f" — {WHY_WORDS.get(line['why'], line['why'])}"
        out.append(f"  {stamp}  {line.get('code', '?'):5}{text}")
    return "\n".join(out)


def render_health(status: int, body: object) -> str:
    if status == 0:
        return f"KHÔNG TRẢ LỜI: {body}"
    if isinstance(body, dict) and status == 200:
        return (
            f"KHOẺ: {body.get('rooms', 0)} phòng, đã dùng ~{body.get('used_pct', 0)}% mức miễn phí"
        )
    if isinstance(body, dict) and body.get("why") == "near_limit":
        return f"SẮP HẾT LƯỢT MIỄN PHÍ (~{body.get('used_pct')}%): phòng mới có thể bị từ chối"
    return f"LỖI HTTP {status}: {str(body)[:120]}"


# --- commands ---
def cmd_status(args) -> int:
    key = read_key()
    if key is None:
        print(
            f"THIẾU KHOÁ — chưa có {KEY_ENV} và chưa có file {key_path()}.\n"
            "Làm: chạy `tools\\relay_ops.py setup` một lần (tạo khoá và đặt lên Cloudflare)."
        )
        return 1
    query = urllib.parse.urlencode({"key": key, "log": args.log})
    status, body = fetch(args.url, f"{relay.API}/status?{query}")
    if status == 200 and isinstance(body, dict):
        print(render_status(body, args.url))
        return 0
    if status == 403:
        print(
            "KHOÁ BỊ TỪ CHỐI — khoá ở máy này khác khoá trên máy chủ (hoặc máy chủ chưa có khoá)."
        )
        print("Làm: chạy `tools\\relay_ops.py setup --force` để đặt khoá mới ở cả hai nơi.")
    elif status == 404:
        print("Máy chủ chưa có phần theo dõi — chạy `tools\\relay_ops.py deploy` để cập nhật.")
    else:
        print(render_health(status, body))
    return 1


def _npx() -> str | None:
    return shutil.which("npx.cmd") or shutil.which("npx")


def _run(cmd: list[str], cwd: Path, stdin: str | None = None) -> int:
    print(f"$ {' '.join(cmd)}", flush=True)
    return subprocess.run(cmd, cwd=cwd, input=stdin, text=True).returncode


def cmd_deploy(args) -> int:
    npx = _npx()
    if npx is None:
        print("THIẾU npx — cài Node.js rồi chạy lại (server/cloudflare dùng wrangler).")
        return 1
    print("BƯỚC 1/3: test giao thức trên bản máy mình")
    tests = ["tests/test_net_relay.py", "tests/test_net_ops.py", "-q"]
    if _run([sys.executable, "-m", "pytest", *tests], ROOT) != 0:
        print("DỪNG ở bước 1: test đỏ, chưa đưa gì lên máy chủ.")
        return 1
    print("BƯỚC 2/3: đưa lên Cloudflare (wrangler deploy)")
    if _run([npx, "wrangler", "deploy"], CLOUDFLARE_DIR) != 0:
        print(
            "DỪNG ở bước 2: wrangler báo lỗi. Nếu nó hỏi đăng nhập: chạy "
            f"`{npx} wrangler login` trong {CLOUDFLARE_DIR} (bấm Allow ở trình duyệt), chạy lại."
        )
        return 1
    print("BƯỚC 3/3: hỏi máy chủ vừa cập nhật")
    status, body = 0, ""
    for _ in range(5):  # (a fresh version takes a moment to be everywhere)
        status, body = fetch(args.url, f"{relay.API}/health")
        if status == 200:
            break
        time.sleep(2.0)
    print(render_health(status, body))
    return 0 if status == 200 else 1


def cmd_setup(args) -> int:
    npx = _npx()
    if npx is None:
        print("THIẾU npx — cài Node.js rồi chạy lại.")
        return 1
    path = key_path()
    if path.exists() and not args.force:
        print(f"Đã có khoá ở {path}. Muốn đặt khoá mới: thêm --force.")
        key = read_key()
    else:
        key = secrets.token_urlsafe(24)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(key + "\n", encoding="utf-8")
        print(f"Đã tạo khoá và lưu ở {path} (ngoài git).")
        if _run([npx, "wrangler", "secret", "put", "ADMIN_KEY"], CLOUDFLARE_DIR, key) != 0:
            print("DỪNG: không đặt được khoá lên Cloudflare (xem lỗi ở trên). Khoá ở máy vẫn còn.")
            return 1
    print(
        "\nBÁO SẬP BẰNG EMAIL (Cloudflare miễn phí không gửi thư được, nên dùng UptimeRobot):\n"
        "  1. Vào https://uptimerobot.com , đăng ký bằng email của bạn (miễn phí).\n"
        "  2. Bấm 'Add New Monitor' → loại 'HTTP(s)'.\n"
        f"  3. URL: {relay._http_base(args.url)}{relay.API}/health\n"
        "  4. Chu kỳ 5 phút; ô nhận thông báo: tick email của bạn → Create.\n"
        "Địa chỉ đó trả lỗi khi máy chủ sập HOẶC khi mức miễn phí trong ngày đã dùng ≥ 90%."
    )
    return 0 if key else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--url", default=relay.relay_url(), help="địa chỉ máy trung chuyển")
    sub = parser.add_subparsers(dest="cmd", required=True)
    one = sub.add_parser("status", help="xem phòng, số hôm nay, nhật ký")
    one.add_argument("--log", type=int, default=20, help="số dòng nhật ký")
    sub.add_parser("deploy", help="test, đưa lên Cloudflare, hỏi lại máy chủ")
    two = sub.add_parser("setup", help="tạo khoá xem tình trạng, chỉ cách báo sập")
    two.add_argument("--force", action="store_true", help="đặt khoá mới dù đã có")
    args = parser.parse_args(argv)
    if not args.url:
        print("THIẾU địa chỉ máy trung chuyển (config.NET_RELAY_URL trống): dùng --url.")
        return 1
    return {"status": cmd_status, "deploy": cmd_deploy, "setup": cmd_setup}[args.cmd](args)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    sys.exit(main())
