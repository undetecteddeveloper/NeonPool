"""Smoke headless: bật App, chạy N khung hình, báo ms/khung. Hợp đồng App: docs/ARCHITECTURE.md.

Exit: 0 = chạy xong; 1 = lỗi/ngoại lệ; 3 = chưa có game/app.py (không có gì để chạy).
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

DEFAULT_SIZE = (1280, 720)
FRAME_BUDGET_MS = 1000 / 60


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--frames", type=int, default=300)
    args = parser.parse_args()

    if not (ROOT / "game" / "app.py").exists():
        print("CHƯA CÓ game/app.py — không có gì để chạy smoke.")
        return 3

    import pygame as pg

    from game import config
    from game.app import App

    pg.init()
    screen = pg.display.set_mode(getattr(config, "WINDOW_SIZE", DEFAULT_SIZE))
    app = App(screen)
    dt = 1 / 60
    times: list[float] = []
    for _ in range(args.frames):
        t0 = time.perf_counter()
        app.update(dt)
        app.draw()
        times.append((time.perf_counter() - t0) * 1000)
    pg.quit()

    mean = sum(times) / len(times)
    worst = max(times)
    print(
        f"smoke: {args.frames} khung, TB {mean:.2f} ms, tệ nhất {worst:.2f} ms "
        f"(ngân sách 60 FPS = {FRAME_BUDGET_MS:.1f} ms)"
    )
    if mean > FRAME_BUDGET_MS:
        print("CẢNH BÁO: trung bình vượt ngân sách 60 FPS (headless, chưa tính present).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
