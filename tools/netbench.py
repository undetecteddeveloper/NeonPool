"""Đo độ trễ và băng thông của lớp mạng (Chặng 0), trên mạng GIẢ LẬP.

    .venv\\Scripts\\python.exe tools\\netbench.py            # đầy đủ (vài giây)
    .venv\\Scripts\\python.exe tools\\netbench.py --quick    # ít vòng (test dùng)

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
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from game import config  # noqa: E402
from game.net import protocol as p  # noqa: E402
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
    print("   1) Hai máy cùng wifi, cùng bản game (git checkout nhánh feat/multiplayer).")
    print("   2) Máy A: menu > Chơi mạng > Tạo phòng (cho phép tường lửa Windows nếu hỏi).")
    print("   3) Máy B: menu > Chơi mạng > Vào phòng > gõ địa chỉ máy A.")
    print("   4) Bật Cài đặt > Hiện FPS; đánh 20 cú ở mỗi máy; ghi cảm giác trễ và số 'lệch'.")
    print("   5) Đo số ms: chạy tools\\netbench.py --tcp trên MỘT máy (loopback) rồi hai máy.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--quick", action="store_true", help="few shots (tests)")
    args = parser.parse_args(argv)
    shots = 200 if args.quick else 4000
    report(run(shots), shots)
    return 0


if __name__ == "__main__":
    sys.exit(main())
