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


def parse_action(pg, action: str):
    kind, _, arg = action.partition(" ")
    if kind == "key":
        keys = {"esc": pg.K_ESCAPE, "f11": pg.K_F11}
        key = keys.get(arg.lower()) or pg.key.key_code(arg.lower())
        return pg.event.Event(pg.KEYDOWN, key=key)
    x, y = (int(v) for v in arg.split(","))
    if kind == "down":
        return pg.event.Event(pg.MOUSEBUTTONDOWN, pos=(x, y), button=1)
    if kind == "up":
        return pg.event.Event(pg.MOUSEBUTTONUP, pos=(x, y), button=1)
    if kind == "move":
        return pg.event.Event(pg.MOUSEMOTION, pos=(x, y), rel=(0, 0), buttons=(1, 0, 0))
    raise SystemExit(f"unknown --do action: {action!r}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--frames", type=int, default=60)
    parser.add_argument("--out", default="tools/_out/shot.png")
    parser.add_argument("--size", default="1280x720")
    parser.add_argument("--scene", choices=("menu", "play", "help"), default="play")
    parser.add_argument("--page", type=int, default=0)
    parser.add_argument("--lang", choices=("vi", "en"), default="")
    parser.add_argument(
        "--do",
        default="",
        help='scripted input before the frames, e.g. "down 338,359; move 238,359; key g". '
        "Actions: down|move|up x,y (left button, window pixels) and key <letter|1|2|3|esc>.",
    )
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
    if args.scene == "play":
        app.go_play()
    if args.scene == "help":
        app.go_help()
        app.help.page = args.page
    if args.lang:
        from game import i18n

        i18n.set_lang(args.lang)
    for action in filter(None, (a.strip() for a in args.do.split(";"))):
        app.handle_event(parse_action(pg, action))
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
