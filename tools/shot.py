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
os.environ.setdefault("NEONPOOL_NO_MUSIC", "1")  # no background thread while measuring

ROOT = Path(__file__).resolve().parent.parent
# the default settings, never the player's own file
os.environ.setdefault("NEONPOOL_SETTINGS", str(ROOT / "tools" / "_out" / "tool-settings.json"))
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


def _stage_practice(app, args) -> None:
    """Put the Practice run in the state asked for (no waiting for it to come about)."""
    from game.rules.eight_ball import WON
    from game.rules.practice import ShotResult

    scene, rules = app.practice, app.practice.rules
    if args.skip_wait or args.end or args.broken:
        scene._ready_left = 0.0
        scene._dim_k = 0.0
    if args.broken:
        from game.physics import Shot

        scene.fire(Shot(0.0, 0.9, 0.0))
        for _ in range(60 * 60):  # (a minute at most: the balls come to rest)
            app.update(1 / 60)
            if not scene._live:
                break
    if args.time and args.mode == "sprint":
        rules.time_left = args.time
    if args.end == "won":
        rules.pocketed, rules.streak, rules.phase = set(range(1, 16)), 15, WON
        rules.last = ShotResult(True, (), None, WON)
        scene._finish_run(rules.last)
    elif args.end == "lost":
        rules.streak, rules.lives, rules.shots = args.streak, 1, args.streak + 2
        if args.mode == "sprint":
            scene._finish_run(rules.tick(1e6))
        else:
            scene._finish_run(rules.timeout())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--frames", type=int, default=60)
    parser.add_argument("--out", default="tools/_out/shot.png")
    parser.add_argument("--size", default="1280x720")
    parser.add_argument(
        "--scene",
        choices=("menu", "play", "practice", "practice-menu", "help", "splash", "intro"),
        default="play",
        help="practice-menu: the Play panel open on its Practice step",
    )
    parser.add_argument(
        "--mode", choices=("ghost", "call", "sprint"), default="ghost", help="for --scene practice"
    )
    parser.add_argument("--page", type=int, default=0)
    parser.add_argument(
        "--skip-wait",
        action="store_true",
        help="--scene practice: end the 7 s dark countdown before the frames start",
    )
    parser.add_argument(
        "--broken",
        action="store_true",
        help="--scene practice: play the opening break first (so a target is called)",
    )
    parser.add_argument(
        "--time", type=float, default=0.0, help="--scene practice --mode sprint: seconds left"
    )
    parser.add_argument(
        "--end",
        choices=("won", "lost"),
        default="",
        help="--scene practice: end the run now (the result card; --streak sets the score)",
    )
    parser.add_argument("--streak", type=int, default=7)
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
    if args.scene == "practice":
        app.go_practice(args.mode)
    if args.scene == "practice-menu":
        from game.scenes import play_panel as pp

        panel = app.menu.play_panel
        panel.open()
        panel._goto(pp.PRACTICE)
        panel.k = 1.0  # (open, not opening)
    if args.scene == "intro":
        app.menu.start_intro()  # --frames N = N sixtieths of a second after the menu opened
    if args.scene == "splash":
        app.start_splash()  # --frames N = N sixtieths of a second after it opened
    if args.scene == "help":
        # the how-to-play card over the menu (over the table: --scene play --do "key h")
        app.open_help()
        app.help.page = args.page
    app.skip_transition()  # photograph the scene itself, not the switch
    if args.scene == "practice":
        _stage_practice(app, args)
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
