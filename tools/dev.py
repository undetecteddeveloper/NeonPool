"""Công cụ dev: mở game THẬT với bảng chọn trạng thái, không cần mạng hay người chơi thứ hai.

    .venv\\Scripts\\python.exe tools\\dev.py                  # cửa sổ game + bảng dev (F1)
    .venv\\Scripts\\python.exe tools\\dev.py --state "thắng"  # vào thẳng một trạng thái
    .venv\\Scripts\\python.exe tools\\dev.py --list           # in danh sách trạng thái
    .venv\\Scripts\\python.exe tools\\dev.py --check          # chạy MỌI trạng thái không cửa sổ

F1 mở/đóng bảng: ↑↓ chọn, Enter chạy. F2 chạy lại, F3 bot tự chơi, F4 cắt/nối mạng, F5 bot đánh
một cú, F6 đồng hồ còn 10 giây, F7 xem lại đoạn mở ván (tung xu). Trạng thái ván hai người dùng một
ĐỐI THỦ GIẢ nối bằng một đường truyền giả lập (cắt, nối, câm, trễ được): không mở cổng, không chạm
mạng thật. Cài đặt dùng file riêng `tools/_out/dev-settings.json`, không bao giờ là file của người
chơi.
Thêm trạng thái: viết hàm trong tools/devkit/states.py (mô tả ở đầu file đó).
Exit (--check): 0 = mọi trạng thái chạy; 1 = có trạng thái lỗi.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--size", default="1280x720", help="cỡ cửa sổ, ví dụ 1920x1080")
    parser.add_argument("--lang", choices=("vi", "en"), default="")
    parser.add_argument(
        "--state", default="", help="tên (hoặc một phần tên) trạng thái để vào ngay"
    )
    parser.add_argument("--list", action="store_true", help="in danh sách trạng thái rồi thoát")
    parser.add_argument("--check", action="store_true", help="chạy mọi trạng thái không cửa sổ")
    parser.add_argument(
        "--frames", type=int, default=45, help="số khung mỗi trạng thái khi --check"
    )
    args = parser.parse_args(argv)

    # the developer never touches the player's real settings
    os.environ["NEONPOOL_SETTINGS"] = str(ROOT / "tools" / "_out" / "dev-settings.json")
    if args.check:
        os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
        os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
        os.environ.setdefault("NEONPOOL_NO_MUSIC", "1")
    (ROOT / "tools" / "_out").mkdir(parents=True, exist_ok=True)

    from tools.devkit.states import STATES, by_name

    if args.list:
        group = None
        for st in STATES:
            if st.group != group:
                group = st.group
                print(f"\n{group}")
            print(f"  {st.name}")
        return 0

    import pygame as pg

    from game import i18n
    from game.app import App, _enable_dpi_awareness

    width, height = (int(v) for v in args.size.lower().split("x"))
    logging.basicConfig(level=logging.INFO)
    if not args.check:
        _enable_dpi_awareness()
    pg.init()
    pg.display.set_caption("NeonPool — DEV")
    screen = pg.display.set_mode((width, height), pg.RESIZABLE)
    app = App(screen)
    if args.lang:
        app.change_settings(lang=args.lang)
        i18n.set_lang(args.lang)

    if args.check:
        from tools.devkit.check import run_check

        bad = run_check(app, count=args.frames)
        for name, error in bad:
            print(f"LỖI  {name}: {error}")
        print(f"dev --check: {len(STATES) - len(bad)}/{len(STATES)} trạng thái chạy được")
        pg.quit()
        return 1 if bad else 0

    from tools.devkit.harness import Harness
    from tools.devkit.overlay import DevPanel

    harness = Harness(app)
    panel = DevPanel(harness)
    if args.state:
        found = by_name(args.state)
        if found is None:
            print(f"không có trạng thái nào tên '{args.state}' (xem --list)")
            pg.quit()
            return 1
        panel.run(STATES.index(found))
        app.skip_transition()
    clock = pg.time.Clock()
    while app.running:
        dt = clock.tick(60) / 1000 * harness.speed
        for e in pg.event.get():
            if not panel.handle_event(e, screen.get_size()):
                app.handle_event(e)
        harness.tick(dt)
        app.update(dt)
        app.draw()
        panel.draw(pg.display.get_surface())
        pg.display.flip()
    pg.quit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
