"""Smoke headless: bật App, đo ms/khung lúc bi đứng yên rồi lúc cú phá full lực.

Hợp đồng App: docs/ARCHITECTURE.md. Exit: 0 = chạy xong và trung bình mỗi giai đoạn trong
ngân sách 60 FPS; 1 = ngoại lệ hoặc vượt ngân sách; 3 = chưa có game/app.py.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

ROOT = Path(__file__).resolve().parent.parent
# the default settings, never the player's own file
os.environ.setdefault("NEONPOOL_SETTINGS", str(ROOT / "tools" / "_out" / "tool-settings.json"))
sys.path.insert(0, str(ROOT))

FRAME_BUDGET_MS = 1000 / 60


def measure(app, frames: int, dt: float = 1 / 60) -> list[float]:
    times: list[float] = []
    for _ in range(frames):
        t0 = time.perf_counter()
        app.update(dt)
        app.draw()
        times.append((time.perf_counter() - t0) * 1000)
    return times


def report(name: str, times: list[float]) -> bool:
    mean = sum(times) / len(times)
    ok = mean <= FRAME_BUDGET_MS
    print(
        f"smoke {name}: {len(times)} khung, TB {mean:.2f} ms, tệ nhất {max(times):.2f} ms "
        f"(ngân sách {FRAME_BUDGET_MS:.1f} ms) {'OK' if ok else 'VƯỢT NGÂN SÁCH'}"
    )
    return ok


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--frames", type=int, default=300, help="frames in the break phase")
    args = parser.parse_args()

    if not (ROOT / "game" / "app.py").exists():
        print("CHƯA CÓ game/app.py — không có gì để chạy smoke.")
        return 3

    import pygame as pg

    from game import config
    from game.app import App
    from game.render.layout import to_px
    from game.rules.eight_ball import LOST

    pg.init()
    screen = pg.display.set_mode(config.LOGICAL_SIZE)
    app = App(screen)
    app.go_play()  # the app opens on the menu

    idle = measure(app, 60)

    # aiming: the glow line, pull bar and ghost ball are redrawn smoothly every frame
    cx, cy = (round(v) for v in to_px(*config.HEAD_SPOT))
    app.handle_event(pg.event.Event(pg.MOUSEBUTTONDOWN, pos=(cx, cy), button=1))
    app.handle_event(
        pg.event.Event(pg.MOUSEMOTION, pos=(cx - 120, cy + 8), rel=(0, 0), buttons=(1, 0, 0))
    )
    aiming = measure(app, 60)

    # full-power break: pull MAX_DRAG_PX to the left of the (still pressed) cue ball, release
    pull = (cx - config.MAX_DRAG_PX, cy)
    app.handle_event(pg.event.Event(pg.MOUSEMOTION, pos=pull, rel=(0, 0), buttons=(1, 0, 0)))
    app.handle_event(pg.event.Event(pg.MOUSEBUTTONUP, pos=pull, button=1))
    if app.scene.rules.shots != 1:  # never report OK for a break that did not happen
        print("smoke: cú phá KHÔNG xảy ra (kéo thả không tạo cú đánh) — đo vô nghĩa")
        return 1
    breaking = measure(app, args.frames)

    # after a foul: the pulsing ring and the notice; at the end of a game: the dimmed result card
    app.play.new_game()
    app.play.rules.cue_in_hand = True
    in_hand = measure(app, 60)
    app.play.new_game()
    app.play.rules.phase = LOST
    card = measure(app, 60)
    # the how-to-play screen: the first frame of each page also makes its picture (ms, one-off)
    app.go_help()
    for page in range(6):
        app.help.page = page
        t0 = time.perf_counter()
        app.update(1 / 60)
        app.draw()
        first = (time.perf_counter() - t0) * 1000
        print(f"smoke hướng dẫn trang {page + 1}: khung đầu (làm hình) {first:.0f} ms")
    app.help.page = 2
    guide = measure(app, 60)
    pg.quit()

    ok = (
        report("đứng yên", idle)
        & report("đang ngắm", aiming)
        & report("cú phá", breaking)
        & report("bi trắng trong tay", in_hand)
        & report("bảng kết quả", card)
        & report("hướng dẫn", guide)
    )
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
