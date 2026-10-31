"""The table, painted once per resolution, drawn with as few neon strokes as can still be played:

- one flat dark plate (the table), so the balls stand out from the night;
- one cyan line round the outside (a wave runs along it when a ball drops, see fx.py);
- one cyan line where the cloth meets the cushions: the edge the balls bounce off, its ends
  curling into the pocket mouths;
- six pink rings with black inside: the pockets, exactly where the physics has them.
No wood, no diamonds, no shading. Three steps: the plate (painted at k x, shrunk), the halo of
every line (one soft layer, added), then the lines themselves (painted at k x, shrunk).
"""

from __future__ import annotations

import math
from functools import cache

import pygame as pg

from game.config import POCKETS, PX_PER_M
from game.render import backdrop, crt, glow
from game.render import palette as C
from game.render.layout import (
    FIELD_H,
    FIELD_W,
    FIELD_X,
    FIELD_Y,
    OUTER_H,
    OUTER_W,
    OUTER_X,
    OUTER_Y,
    to_px,
)
from game.render.view import View

CUSHION_PX = 12  # the cushion band between the cloth and the rail (geometry of the cushion ends)
FRAME_R = 20  # outer corner radius of the table
CORNER_ARM = POCKETS[0][2] * PX_PER_M  # the cushion face starts this far from the corner
CUSHION_END_R = 12.0  # both ends of a cushion line curl into the pocket with this radius
CUSHION_TUCK = -2.0  # a cushion starts this far inside the pocket circle (negative: short of it)
LIP_PX = 1.4  # the pocket ring sits this far outside the hole
GLOW_DOWN = 2  # the halo layer is built at 1/2 of the device size, then stretched smoothly


# --- geometry (logical px; shared with the tests) ------------------------------------------
def cushion_outline(length: float, e: float = 0.0, steps: int = 10) -> list[tuple[float, float]]:
    """One cushion in its own axes: s along the strip, d from the cloth face (0) to the
    rail (CUSHION_PX). Both face-side corners are rounded; `e` > 0 grows the face side.
    """
    r, r2 = CUSHION_END_R, CUSHION_END_R + e
    pts = [(0.0, CUSHION_PX), (0.0, r)]
    for i in range(1, steps + 1):  # left end: from straight down the end to straight along the face
        a = math.pi + (math.pi / 2) * i / steps
        pts.append((r2 + r2 * math.cos(a), r + r2 * math.sin(a)))
    for i in range(steps + 1):  # right end
        a = 1.5 * math.pi + (math.pi / 2) * i / steps
        pts.append((length - r2 + r2 * math.cos(a), r + r2 * math.sin(a)))
    pts.append((length, CUSHION_PX))
    return pts


def cushion_strips() -> list[tuple[tuple[float, float], tuple[float, float], tuple[int, int]]]:
    """(start, end, out) of the six cushions: along the cloth edge, `out` points at the rail.

    Each strip stops CUSHION_TUCK px inside the pocket circle on both ends (negative: short of it),
    so the curled ends show next to the pocket ring.
    """
    cx = FIELD_X + FIELD_W / 2
    c, m = CORNER_ARM - CUSHION_TUCK, POCKETS[4][2] * PX_PER_M - CUSHION_TUCK
    right, bottom = FIELD_X + FIELD_W, FIELD_Y + FIELD_H
    strips = []
    for top in (True, False):
        y, out = (FIELD_Y, (0, -1)) if top else (bottom, (0, 1))
        strips += [((FIELD_X + c, y), (cx - m, y), out), ((cx + m, y), (right - c, y), out)]
    for left in (True, False):
        x, out = (FIELD_X, (-1, 0)) if left else (right, (1, 0))
        strips.append(((x, FIELD_Y + c), (x, bottom - c), out))
    return strips


def cushion_line(a, b, out) -> list[tuple[float, float]]:
    """The lit edge of one cushion on the table: along the cloth, curling out at both ends."""
    length = math.dist(a, b)
    tx, ty = (b[0] - a[0]) / length, (b[1] - a[1]) / length
    pts = cushion_outline(length)[1:-1]
    return [(a[0] + s * tx + d * out[0], a[1] + s * ty + d * out[1]) for s, d in pts]


RIM_STEP = 3.0  # distance between the points of the rim path (logical px)


def _sample(a: tuple[float, float], b: tuple[float, float]) -> list[tuple[float, float]]:
    n = max(1, round(math.dist(a, b) / RIM_STEP))
    return [(a[0] + (b[0] - a[0]) * i / n, a[1] + (b[1] - a[1]) * i / n) for i in range(n)]


def _arc(cx: float, cy: float, r: float, a0: float, a1: float) -> list[tuple[float, float]]:
    n = max(2, round(r * math.radians(a1 - a0) / RIM_STEP))
    angles = [math.radians(a0 + (a1 - a0) * i / n) for i in range(n)]
    return [(cx + r * math.cos(a), cy + r * math.sin(a)) for a in angles]


def rim_path() -> list[tuple[float, float]]:
    """The outer neon line as a closed path, clockwise from the top-left, points RIM_STEP apart."""
    x0, y0, x1, y1, r = OUTER_X, OUTER_Y, OUTER_X + OUTER_W, OUTER_Y + OUTER_H, FRAME_R
    return [
        *_sample((x0 + r, y0), (x1 - r, y0)),
        *_arc(x1 - r, y0 + r, r, -90, 0),
        *_sample((x1, y0 + r), (x1, y1 - r)),
        *_arc(x1 - r, y1 - r, r, 0, 90),
        *_sample((x1 - r, y1), (x0 + r, y1)),
        *_arc(x0 + r, y1 - r, r, 90, 180),
        *_sample((x0, y1 - r), (x0, y0 + r)),
        *_arc(x0 + r, y0 + r, r, 180, 270),
        (x0 + r, y0),  # closed
    ]


def neon_paths() -> list[list[tuple[float, float]]]:
    """Every neon line of the table as a polyline (logical px): the rim, then the six cushions.
    A wave over the table lights these up where it passes."""
    return [rim_path()] + [cushion_line(a, b, out) for a, b, out in cushion_strips()]


# --- the three steps ---------------------------------------------------------------------------
def _paint_plate(s: pg.Surface, v: View) -> None:
    """The table: one flat dark plate with rounded corners."""
    pg.draw.rect(s, C.TABLE, v.rect(OUTER_X, OUTER_Y, OUTER_W, OUTER_H), border_radius=v.i(FRAME_R))


def _glow_pass(dev: pg.Surface, v: View) -> None:
    """Add the soft light round every line: one small layer, blurred, stretched, added."""
    look = C.LOOK
    lv = View(v.s / GLOW_DOWN, v.ox // GLOW_DOWN, v.oy // GLOW_DOWN)
    w, h = dev.get_size()
    layer = pg.Surface((max(1, w // GLOW_DOWN), max(1, h // GLOW_DOWN)))

    def lit(color, f: float) -> tuple[int, int, int]:
        return tuple(min(255, round(c * f * look.glow)) for c in color)

    rim = lv.rect(OUTER_X, OUTER_Y, OUTER_W, OUTER_H)
    for width, f in ((11, 0.30), (6, 0.55), (2.5, 0.85)):
        pg.draw.rect(layer, lit(C.CYAN, f), rim, max(1, lv.i(width)), border_radius=lv.i(FRAME_R))
    for a, b, out in cushion_strips():
        pts = [lv.pt(p) for p in cushion_line(a, b, out)]
        for width, f in ((8, 0.32), (3.5, 0.6)):
            pg.draw.lines(layer, lit(C.CUSHION_NOSE, f), False, pts, max(1, lv.i(width)))
    for px, py, pr in POCKETS:
        c, r = lv.pt(to_px(px, py)), pr * PX_PER_M + LIP_PX
        for width, f in ((10, 0.30), (5, 0.60), (2.4, 0.9)):
            pg.draw.circle(layer, lit(C.POCKET_RING, f), c, lv.n(r + width / 2), lv.i(width))
    soft = glow.blur_pm(layer, 4.5 * look.reach)
    dev.blit(pg.transform.smoothscale(soft, dev.get_size()), (0, 0), special_flags=pg.BLEND_RGB_ADD)


def _paint_lines(s: pg.Surface, v: View) -> None:
    """The cores of the lines, and the black inside of the pockets."""
    line = C.LOOK.line
    rim = v.rect(OUTER_X, OUTER_Y, OUTER_W, OUTER_H)
    pg.draw.rect(s, C.CYAN, rim, max(1, v.i(2.0 * line)), border_radius=v.i(FRAME_R))
    for a, b, out in cushion_strips():
        pts = [v.pt(p) for p in cushion_line(a, b, out)]
        pg.draw.lines(s, C.CUSHION_NOSE, False, pts, max(1, v.i(1.9 * line)))
    for px, py, pr in POCKETS:
        c = v.pt(to_px(px, py))
        r = pr * PX_PER_M
        pg.draw.circle(s, C.POCKET, c, v.n(r + LIP_PX))
        ring = max(1, v.i(2.0 * line))
        pg.draw.circle(s, C.POCKET_RING, c, v.n(r + LIP_PX) + ring / 2, ring)


def _shrink(big: pg.Surface, size: tuple[int, int]) -> pg.Surface:
    return pg.transform.smoothscale(big.premul_alpha(), size)


@cache
def build_table(v: View) -> pg.Surface:
    """The finished table for this view's canvas: painted at 3x (2x when big), shrunk once.

    Remembered per view, so the how-to-play pictures and the game share one table: never draw on
    the result, only blit it. The two big layers only cover the table, not the whole canvas.
    """
    k = v.ss()
    box = v.rect(OUTER_X - 3, OUTER_Y - 3, OUTER_W + 6, OUTER_H + 6)  # device px
    big = v.scaled(k).shifted(box.x * k, box.y * k)
    layer_size = (box.w * k, box.h * k)

    dev = backdrop.night(v.canvas).copy()
    crt.darken_corners(dev)
    plate = pg.Surface(layer_size, pg.SRCALPHA)
    _paint_plate(plate, big)
    dev.blit(_shrink(plate, box.size), box.topleft, special_flags=pg.BLEND_PREMULTIPLIED)
    del plate
    _glow_pass(dev, v)
    lines = pg.Surface(layer_size, pg.SRCALPHA)
    _paint_lines(lines, big)
    dev.blit(_shrink(lines, box.size), box.topleft, special_flags=pg.BLEND_PREMULTIPLIED)
    return dev
