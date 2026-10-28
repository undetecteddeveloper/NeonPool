"""Chụp một khung hình của game (headless) ra PNG để Claude nhìn bằng Read.

    .venv\\Scripts\\python.exe tools\\shot.py --frames 60 --out tools\\_out\\a.png [--size 1280x720]

Exit: 0 = đã lưu ảnh; 1 = lỗi; 3 = chưa có game/app.py.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--frames", type=int, default=60)
    parser.add_argument("--out", default="tools/_out/shot.png")
    parser.add_argument("--size", default="1280x720")
    args = parser.parse_args()

    if not (ROOT / "game" / "app.py").exists():
        print("CHƯA CÓ game/app.py — không có gì để chụp.")
        return 3

    import pygame as pg

    from game.app import App

    width, height = (int(v) for v in args.size.lower().split("x"))
    pg.init()
    screen = pg.display.set_mode((width, height))
    app = App(screen)
    for _ in range(args.frames):
        app.update(1 / 60)
        app.draw()

    out = Path(args.out)
    out = out if out.is_absolute() else ROOT / out
    out.parent.mkdir(parents=True, exist_ok=True)
    pg.image.save(screen, str(out))
    pg.quit()
    print(f"đã lưu {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
