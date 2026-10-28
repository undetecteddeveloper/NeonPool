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

    pg.init()
    screen = pg.display.set_mode(config.LOGICAL_SIZE)
    app = App(screen)

    idle = measure(app, 60)

    # full-power break: press the cue ball, pull MAX_DRAG_PX to the left, release
    cx, cy = (round(v) for v in to_px(*config.HEAD_SPOT))
    pull = (cx - config.MAX_DRAG_PX, cy)
    app.handle_event(pg.event.Event(pg.MOUSEBUTTONDOWN, pos=(cx, cy), button=1))
    app.handle_event(pg.event.Event(pg.MOUSEMOTION, pos=pull, rel=(0, 0), buttons=(1, 0, 0)))
    app.handle_event(pg.event.Event(pg.MOUSEBUTTONUP, pos=pull, button=1))
    if app.scene.rules.shots != 1:  # never report OK for a break that did not happen
        print("smoke: cú phá KHÔNG xảy ra (kéo thả không tạo cú đánh) — đo vô nghĩa")
        return 1
    breaking = measure(app, args.frames)
    pg.quit()

    ok = report("đứng yên", idle) & report("cú phá", breaking)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
