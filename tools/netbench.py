"""Đo độ trễ và băng thông của lớp mạng (Chặng 0), trên mạng GIẢ LẬP.

    .venv\\Scripts\\python.exe tools\\netbench.py            # đầy đủ (vài giây)
    .venv\\Scripts\\python.exe tools\\netbench.py --quick    # ít vòng (test dùng)
    .venv\\Scripts\\python.exe tools\\netbench.py --relay    # qua máy trung chuyển trên máy này
    .venv\\Scripts\\python.exe tools\\netbench.py --relay wss://...  # qua máy trung chuyển thật

Mạng là `NetSim` (thời gian ảo: trễ, jitter, mất gói có hạt giống); phần việc của GAME (mã hoá,
đưa vào hàng đợi, giải mã, áp cú đánh vào World) được đo bằng đồng hồ thật của máy này. Số ra
chỉ có nhãn "giả lập (đã đo)": con số trên hai máy thật CHƯA ĐO, kịch bản chạy ở cuối bản in.

Một chiều "thả chuột ở A -> B bắt đầu chạy cú" được báo ở ba mức, mỗi mức thêm một thứ:
  hàng đợi  = game ở A gửi (mã hoá + gửi) + mạng + game ở B nhận (lấy ra + giải mã + áp cú)
  + khung B = B chỉ lấy tin ở đầu mỗi khung hình (60 FPS, pha ngẫu nhiên)
  + khung A = sự kiện thả chuột ở A cũng chỉ được game thấy ở đầu khung hình của A
Exit 0 khi chạy xong.
"""

from __future__ import annotations

import argparse
import os
import random
import sys
import time
from collections import deque
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from game import config  # noqa: E402
from game.net import protocol as p  # noqa: E402
from game.net import relay, tcp  # noqa: E402
from game.net.transport import NetSim  # noqa: E402
from game.physics import Shot, World  # noqa: E402
from game.rules.two_player import Match  # noqa: E402

FRAME_S = 1 / 60
SIM_LABEL = "giả lập (đã đo)"
REAL_LABEL = "hai máy thật: CHƯA ĐO"
# (tên, trễ một chiều ms, jitter ms, mất gói %): RTT = 2 × trễ một chiều
SCENARIOS = (
    ("LAN tốt", 1, 0.5, 0.0),
    ("VN thường (RTT 40)", 20, 2, 0.0),
    ("VN xấu vừa (RTT 40, jitter 10, mất 2%)", 20, 10, 2.0),
    ("xa (RTT 80, jitter 20, mất 5%)", 40, 20, 5.0),
)
LIMIT_P95_MS = 50.0  # mục tiêu một chiều ở điều kiện thường
LIMIT_GAME_MS = 5.0  # phần game tự cộng


def percentile(values: list[float], q: float) -> float:
    s = sorted(values)
    return s[min(len(s) - 1, round(q / 100 * (len(s) - 1)))]


def stats(values: list[float]) -> tuple[float, float, float]:
    return percentile(values, 50), percentile(values, 95), percentile(values, 99)


def one_way(latency_ms: float, jitter_ms: float, loss_pct: float, shots: int, seed: int) -> dict:
    """`shots` cú đánh từ A sang B qua một mạng giả lập; trả các danh sách mili-giây."""
    sim = NetSim(latency_ms / 1000, jitter_ms / 1000, loss_pct / 100, seed=seed)
    rng = random.Random(seed + 1)  # pha khung hình của hai máy
    world = World(seed=0)
    queue_ms, with_b_ms, with_ab_ms, game_ms = [], [], [], []
    for n in range(shots):
        shot = Shot(rng.uniform(0, 6.28), rng.random(), rng.randint(-32, 32) / 32)
        t0 = time.perf_counter()
        frame = p.encode(p.ShotMsg.from_shot(n & 0xFFFF, p.snap_shot(shot)))
        sim.a.send(frame)
        game_a = time.perf_counter() - t0
        wait = sim.until_next(1)  # mạng: thời gian ảo trôi tới lúc tin tới B
        sim.advance(wait)
        net = wait
        t1 = time.perf_counter()
        got = sim.b.poll()
        world.apply(p.decode(got[0]).to_shot())
        game_b = time.perf_counter() - t1
        game = game_a + game_b
        queue = net + game
        to_next_b = rng.uniform(0, FRAME_S)  # B lấy tin ở đầu khung kế tiếp
        to_next_a = rng.uniform(0, FRAME_S)  # A thấy sự kiện thả chuột ở đầu khung của A
        queue_ms.append(queue * 1000)
        with_b_ms.append((queue + to_next_b) * 1000)
        with_ab_ms.append((queue + to_next_b + to_next_a) * 1000)
        game_ms.append(game * 1000)
        sim.advance(0.5)  # cú sau cách nhau, hàng đợi trống
        sim.a.poll()
    return {"queue": queue_ms, "frame_b": with_b_ms, "frame_ab": with_ab_ms, "game": game_ms}


def cue_bandwidth(seconds: float = 10.0) -> dict:
    """Băng thông người ngắm cơ: AIM `NET_AIM_HZ` gói/s trong `seconds` giây."""
    sim = NetSim()
    n = 0
    for i in range(round(seconds * config.NET_AIM_HZ)):
        aim = p.Aim(i & 0xFF, p.AIM_PULLING, (i * 997) & 0xFFFF, i & 0xFF)
        sim.a.send(p.encode(aim), reliable=False)
        n += 1
    app_bytes = sim.a.bytes_sent / seconds
    return {
        "packets_per_s": n / seconds,
        "app_bytes_per_s": app_bytes,
        # TCP/IPv4 thêm ~40 byte mỗi gói (không tính ACK): cận trên cho băng thông trên dây
        "wire_bytes_per_s": app_bytes + 40 * n / seconds,
    }


def checkpoint_bytes() -> int:
    """Kích thước một điểm kiểm thật: 16 bi của bàn mới xếp + trạng thái luật sau một cú."""
    balls = tuple(
        p.BallPos(b.in_play, -1 if b.pocket is None else b.pocket, b.x, b.y)
        for b in World(seed=0).balls
    )
    match = Match()
    match.on_shot()
    match.finish_shot()
    return len(p.encode(p.Checkpoint(1, 0, balls, match.snapshot())))


class _Stamped(deque):
    """The receiving queue of a TcpTransport, remembering when each frame was put in it."""

    def __init__(self) -> None:
        super().__init__()
        self.stamps: deque[float] = deque()
        self.last = 0.0

    def extend(self, frames) -> None:
        now = time.perf_counter()
        for frame in frames:
            self.stamps.append(now)
            self.append(frame)

    def popleft(self):
        frame = super().popleft()
        self.last = self.stamps.popleft()
        return frame


def _spin(seconds: float) -> None:
    """Pure Python work, like a frame being drawn: it holds the interpreter as a frame would."""
    end = time.perf_counter() + seconds
    n = 0
    while time.perf_counter() < end:
        n += 1


def tcp_loopback(shots: int, busy: bool, interval: float) -> list[float]:
    """Real sockets on 127.0.0.1 between two transports in this process: ms from `send` until the
    frame is in the receiver's queue. `busy`: the main thread is doing frame-sized Python work
    (4 ms slices) the whole time; `interval`: the interpreter's thread switch interval (s)."""
    listener = tcp.TcpListener(0, "127.0.0.1")
    conn = tcp.Connector("127.0.0.1", listener.port)
    client = server = None
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline and (client is None or server is None):
        client = client or conn.result()
        server = server or listener.accept()
        time.sleep(0.001)
    if client is None or server is None:
        raise RuntimeError("loopback connection failed")
    server._in = _Stamped()
    old = sys.getswitchinterval()
    sys.setswitchinterval(interval)
    frame = p.encode(p.ShotMsg.from_shot(1, Shot(1.0, 0.5, 0.0)))
    out = []
    try:
        for _ in range(shots):
            t0 = time.perf_counter()
            client.send(frame)
            while True:
                _spin(0.004) if busy else time.sleep(0.0003)
                if server.poll():
                    break
            out.append((server._in.last - t0) * 1000)
            time.sleep(0.004)
    finally:
        sys.setswitchinterval(old)
        client.close()
        listener.close()
    return out


def report_tcp(shots: int) -> dict[str, float]:
    label = "cùng máy, ổ cắm thật (đã đo)"
    print(f"== Từ `send` tới hàng đợi của bên nhận, {label}: {shots} cú (ms)")
    print(
        f"   {'luồng chính / chu kỳ chuyển luồng của Python':58} {'p50':>7} {'p95':>7} {'p99':>7}"
    )
    rows = (
        ("rảnh", False, tcp.SWITCH_INTERVAL_S),
        ("bận (khung 4 ms), 5 ms (mặc định của Python)", True, 0.005),
        ("bận (khung 4 ms), 1 ms", True, 0.001),
        ("bận (khung 4 ms), 0,2 ms  <- game dùng", True, tcp.SWITCH_INTERVAL_S),
    )
    p95s = {}
    for name, busy, interval in rows:
        p50, p95, p99 = stats(tcp_loopback(shots, busy, interval))
        p95s[name] = p95
        print(f"   {name:58} {p50:7.2f} {p95:7.2f} {p99:7.2f}")
    print(f"   (mục tiêu phần game ≤ {LIMIT_GAME_MS:.0f} ms p95; đây CHƯA phải hai máy thật)")
    print(
        "   Windows làm tròn thời gian chờ GIL lên một nhịp đồng hồ; dưới 1 ms thì bàn giao ngay."
    )
    return p95s


def relay_loopback(url: str, shots: int) -> tuple[list[float], list[float]]:
    """Both ends in this process, meeting by code through the relay at `url` (no straight door):
    ms from `send` until the frame is in the other end's queue, guest -> host and host -> guest,
    with the main thread busy as while drawing. Both ends are on this machine, so through a relay
    on the internet each frame goes there and back: what two players far apart would see."""
    room = relay.HostRoom(url, door=False)
    deadline = time.monotonic() + 10
    while room.state == relay.CONNECTING and time.monotonic() < deadline:
        time.sleep(0.01)
    if room.state != relay.READY:
        raise RuntimeError(f"no room from the relay ({room.error})")
    join = relay.Join(room.code, url)
    guest = host = None
    while time.monotonic() < deadline and (guest is None or host is None):
        guest = guest or join.result()
        host = host or room.accept()
        time.sleep(0.001)
    if guest is None or host is None:
        raise RuntimeError(f"could not join the room ({join.error})")
    host._in, guest._in = _Stamped(), _Stamped()
    frame = p.encode(p.ShotMsg.from_shot(1, Shot(1.0, 0.5, 0.0)))
    ways: tuple[list[float], list[float]] = ([], [])
    try:
        for n in range(2 * shots):
            sender, receiver = (guest, host) if n % 2 == 0 else (host, guest)
            t0 = time.perf_counter()
            sender.send(frame)
            end = time.monotonic() + 5
            while time.monotonic() < end:
                _spin(0.004)
                if receiver.poll():
                    break
            else:
                raise RuntimeError("a frame did not come through the relay")
            ways[n % 2].append((receiver._in.last - t0) * 1000)
            time.sleep(0.004)
    finally:
        guest.close()
        room.close()
    return ways


def report_relay(url: str, shots: int) -> None:
    local = url.startswith("ws://127.") or url.startswith("ws://localhost")
    label = "máy trung chuyển trên máy này (đã đo)" if local else f"qua {url} (đã đo, thật)"
    print(f"== Từ `send` tới hàng đợi bên kia, {label}: {shots} khung mỗi chiều (ms)")
    print(f"   {'chiều':40} {'p50':>7} {'p95':>7} {'p99':>7}")
    to_host, to_guest = relay_loopback(url, shots)
    for name, values in (("khách -> chủ phòng", to_host), ("chủ phòng -> khách", to_guest)):
        p50, p95, p99 = stats(values)
        print(f"   {name:40} {p50:7.2f} {p95:7.2f} {p99:7.2f}")
    print(f"   (+ chờ đầu khung B ~8 ms TB, 16,7 ms tệ nhất; mục tiêu ≤ {LIMIT_P95_MS:.0f} ms)")
    if not local:
        print("   Hai đầu cùng ở máy này: mỗi khung đi máy này -> máy trung chuyển -> máy này,")
        print("   đúng quãng đường giữa hai người cùng ở xa máy trung chuyển như máy này.")


def run(shots: int) -> dict:
    results = {"scenarios": [], "cue": cue_bandwidth(), "checkpoint": checkpoint_bytes()}
    for i, (name, lat, jit, loss) in enumerate(SCENARIOS):
        results["scenarios"].append((name, lat, jit, loss, one_way(lat, jit, loss, shots, 10 + i)))
    return results


def report(results: dict, shots: int) -> None:
    print(f"== Độ trễ một chiều, mạng {SIM_LABEL}: {shots} cú mỗi kịch bản (ms)")
    print(f"   {'kịch bản':42} {'':9} {'p50':>7} {'p95':>7} {'p99':>7}")
    for name, _lat, _jit, _loss, r in results["scenarios"]:
        for key, label in (
            ("queue", "hàng đợi"),
            ("frame_b", "+ khung B"),
            ("frame_ab", "+ khung A"),
            ("game", "phần game"),
        ):
            p50, p95, p99 = stats(r[key])
            shown = name if key == "queue" else ""
            print(f"   {shown:42} {label:9} {p50:7.2f} {p95:7.2f} {p99:7.2f}")
    normal = results["scenarios"][1][4]
    q95 = percentile(normal["frame_b"], 95)
    g95 = percentile(normal["game"], 95)
    verdict_way = "ĐẠT" if q95 <= LIMIT_P95_MS else "KHÔNG ĐẠT"
    verdict_game = "ĐẠT" if g95 <= LIMIT_GAME_MS else "KHÔNG ĐẠT"
    print(
        f"-- VN thường, p95: một chiều tới khung B {q95:.1f} ms (mục tiêu ≤ {LIMIT_P95_MS:.0f}) "
        f"{verdict_way}; phần game {g95:.3f} ms "
        f"(mục tiêu ≤ {LIMIT_GAME_MS:.0f}) {verdict_game}  [{SIM_LABEL}]"
    )
    cue = results["cue"]
    print(
        f"== Cơ đối thủ, {SIM_LABEL}: {cue['packets_per_s']:.0f} gói/s, "
        f"{cue['app_bytes_per_s']:.0f} byte/s nội dung (mục tiêu < 2048), "
        f"~{cue['wire_bytes_per_s']:.0f} byte/s kể cả tiêu đề TCP/IP"
    )
    print(f"== Điểm kiểm sau mỗi cú: {results['checkpoint']} byte")
    print(f"== {REAL_LABEL}. Kịch bản chạy khi nhờ được bạn:")
    print("   1) Hai máy cùng bản game; cùng wifi (nối thẳng) hoặc hai nhà (qua máy chủ).")
    print("   2) Máy A: Chơi > Chơi đôi > Tạo phòng (cho phép tường lửa Windows nếu hỏi).")
    print("   3) Máy B: Chơi > Chơi đôi > Vào phòng > gõ mã 4 chữ của máy A.")
    print("   4) Bật Cài đặt > Hiện FPS; đánh 20 cú ở mỗi máy; ghi cảm giác trễ và số 'lệch'.")
    print("   5) Đo ms qua máy trung chuyển thật: tools\\netbench.py --relay wss://... (một máy).")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--quick", action="store_true", help="few shots (tests)")
    parser.add_argument("--tcp", action="store_true", help="real sockets on 127.0.0.1 only")
    parser.add_argument(
        "--relay",
        nargs="?",
        const="local",
        help="through a relay: its ws(s):// address, or none for one on this machine",
    )
    args = parser.parse_args(argv)
    if args.relay:
        shots = 40 if args.quick else 300
        if args.relay == "local":
            from server.local_relay import Relay

            server = Relay()
            try:
                report_relay(server.url, shots)
            finally:
                server.close()
        else:
            report_relay(args.relay.rstrip("/"), shots)
        return 0
    if args.tcp:
        report_tcp(40 if args.quick else 400)
        return 0
    shots = 200 if args.quick else 4000
    report(run(shots), shots)
    return 0


if __name__ == "__main__":
    sys.exit(main())
