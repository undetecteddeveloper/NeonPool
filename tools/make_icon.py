"""Draw the game's icon: the cue ball, ringed by waves of synthwave light.

    .venv\\Scripts\\python.exe tools\\make_icon.py

Writes assets/icon.png (256 px, for the game window) and assets/icon.ico (16..256 px, for the
program file, its shortcut and the taskbar; build_exe.py puts it on NeonPool.exe). The picture is
drawn once big (1024 px) and shrunk for every size, so the small ones stay clean.
Exit: 0 = written.
"""

from __future__ import annotations

import io
import math
import os
import struct
import sys
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pygame as pg  # noqa: E402

from game.render import palette as C  # noqa: E402

BIG = 1024
SIZES = (16, 24, 32, 48, 64, 128, 256)
CENTRE = BIG // 2
BALL_R = 185
STRANDS = 6  # the ribbons round the ball, as in the menu
RING_R0, RING_GAP, WAVE_AMP, WAVES, STAGGER, LINE_W = 255, 27, 15, 6, 0.45, 8
CORNER = 190  # the rounded square's corner


def _blur(surf: pg.Surface, k: int) -> pg.Surface:
    w, h = surf.get_size()
    return pg.transform.smoothscale(pg.transform.smoothscale(surf, (w // k, h // k)), (w, h))


def _night() -> pg.Surface:
    s = pg.Surface((BIG, BIG))
    for y in range(BIG):
        pg.draw.line(s, C.lerp((8, 3, 22), (58, 12, 84), (y / BIG) ** 1.6), (0, y), (BIG, y))
    return s


def _glow(img: pg.Surface, lights: pg.Surface) -> None:
    for k, gain in ((16, 2), (6, 1)):
        soft = _blur(lights, k)
        for _ in range(gain):
            img.blit(soft, (0, 0), special_flags=pg.BLEND_RGB_ADD)
    img.blit(lights, (0, 0), special_flags=pg.BLEND_RGB_ADD)


def draw_big() -> pg.Surface:
    """The icon at 1024 px, with transparent corners."""
    img, lights = _night(), pg.Surface((BIG, BIG))
    for i in range(STRANDS):  # a wavy ring each, cyan on the inside to hot pink outside
        pts = []
        for deg in range(0, 362, 2):
            t = math.radians(deg)
            r = RING_R0 + i * RING_GAP + WAVE_AMP * math.sin(WAVES * t + i * STAGGER)
            pts.append((CENTRE + r * math.cos(t), CENTRE + r * math.sin(t)))
        col = C.lerp(C.CYAN, C.MAGENTA, i / (STRANDS - 1))
        pg.draw.lines(lights, C.scale(col, 0.35), True, pts, LINE_W * 3)
        pg.draw.lines(lights, C.lerp(col, C.WHITE, 0.3), True, pts, LINE_W)
    _glow(img, lights)
    c = (CENTRE, CENTRE)
    pg.draw.circle(img, C.OUTLINE, c, BALL_R + 24)  # the ball's edge is the dark ink, not cyan
    pg.draw.circle(img, C.WHITE, c, BALL_R)
    pg.draw.circle(
        img, (214, 224, 248), (CENTRE + BALL_R // 4, CENTRE + BALL_R // 4), int(BALL_R * 0.62)
    )
    pg.draw.circle(img, C.WHITE, (CENTRE - BALL_R // 5, CENTRE - BALL_R // 5), int(BALL_R * 0.7))
    mask = pg.Surface((BIG, BIG), pg.SRCALPHA)
    pg.draw.rect(mask, (255, 255, 255, 255), (0, 0, BIG, BIG), border_radius=CORNER)
    out = pg.Surface((BIG, BIG), pg.SRCALPHA)
    out.blit(img, (0, 0))
    out.blit(mask, (0, 0), special_flags=pg.BLEND_RGBA_MIN)
    return out


def png_bytes(surf: pg.Surface) -> bytes:
    buf = io.BytesIO()
    pg.image.save(surf, buf, "icon.png")
    return buf.getvalue()


def ico_bytes(images: dict[int, bytes]) -> bytes:
    """An .ico holding one PNG per size (Windows has read PNG inside .ico since Vista)."""
    head = struct.pack("<HHH", 0, 1, len(images))
    offset = 6 + 16 * len(images)
    entries, data = b"", b""
    for size, png in images.items():
        wh = 0 if size >= 256 else size  # 0 means 256
        entries += struct.pack("<BBBBHHII", wh, wh, 0, 0, 1, 32, len(png), offset + len(data))
        data += png
    return head + entries + data


def main() -> int:
    pg.init()
    big = draw_big()
    pngs = {s: png_bytes(pg.transform.smoothscale(big, (s, s))) for s in SIZES}
    assets = ROOT / "assets"
    (assets / "icon.png").write_bytes(pngs[256])
    (assets / "icon.ico").write_bytes(ico_bytes(pngs))
    print(f"đã ghi {assets / 'icon.png'} và {assets / 'icon.ico'} ({len(SIZES)} cỡ)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
