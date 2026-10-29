"""The table, painted once per resolution: a night-blue cloth inside a rail of light.

The rail is dark with a lit cyan rim, the cushions are dark with a lit edge facing the cloth (their
ends are rounded and hug the pockets), the pockets are deep holes ringed in pink-violet, and small
lit diamonds mark the rail. Three steps: the dark shapes (painted at k x, shrunk once), the halo
of every lit line (one soft layer, added), then the lit lines themselves (painted at k x, shrunk).
"""

from __future__ import annotations

import math
from functools import cache

import numpy as np
import pygame as pg

from game.config import POCKETS, PX_PER_M, RAIL_PX, TABLE_L, TABLE_W
from game.render import backdrop, glow
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
from game.render.view import CropView, View

CUSHION_PX = 12  # rubber between the cloth and the rail (the cloth edge is the cushion face)
WOOD_PX = RAIL_PX - CUSHION_PX  # depth of the rail itself
FRAME_R = 20  # outer corner radius of the table
PLATE_R = 8  # corner radius of the middle-pocket housings
CORNER_ARM = POCKETS[0][2] * PX_PER_M  # the cushion face starts this far from the corner
PLATE_MARGIN = 10  # how far a housing reaches past the pocket along the rail (under the cushion)
SIDE_HALF = POCKETS[4][2] * PX_PER_M + PLATE_MARGIN  # half width of a middle-pocket housing
CUSHION_END_R = 12.0  # both ends of a cushion are rounded with this radius
CUSHION_TUCK = -2.0  # a cushion starts this far inside the pocket circle (negative: short of it)
CUSHION_SHADOW = ((6.0, 12), (4.5, 28), (3.0, 44), (1.5, 62))  # (distance px, alpha) on the cloth
LIP_PX = 1.4  # the pocket ring sits this far outside the hole
HOLE_SHIFT = 0.16  # the dark hole is sunk this fraction of the radius towards the outside
SIGHT_R = 3.2  # half diagonal of a rail diamond
CLOTH_RES = (320, 160)  # the cloth gradient is built this small, then stretched smoothly
GLOW_DOWN = 2  # the halo layer is built at 1/2 of the device size, then stretched smoothly


def _lerp(a, b, t: float) -> tuple[int, int, int]:
    return tuple(round(x + (y - x) * t) for x, y in zip(a, b, strict=True))


def cloth_gradient(size: tuple[int, int]) -> pg.Surface:
    """Elliptical gradient: CLOTH_CENTRE in the middle, CLOTH_EDGE in the corners."""
    w, h = CLOTH_RES
    ys, xs = np.mgrid[0:h, 0:w]
    nx, ny = (xs + 0.5) / w * 2 - 1, (ys + 0.5) / h * 2 - 1
    u = np.clip(np.sqrt(nx * nx + ny * ny) / math.sqrt(2) * 1.15, 0.0, 1.0) ** 1.5
    centre, edge = np.array(C.CLOTH_CENTRE, float), np.array(C.CLOTH_EDGE, float)
    rgb = centre[None, None, :] + (edge - centre)[None, None, :] * u[:, :, None]
    small = pg.surfarray.make_surface(rgb.astype(np.uint8).transpose(1, 0, 2))
    return pg.transform.smoothscale(small, size)


# --- geometry (logical px; shared by the three steps and by the tests) ---------------------
def plate_rects() -> list[tuple[tuple[float, float, float, float], tuple[int, int, int, int]]]:
    """Six pocket housings (not drawn: they are the rail's colour, but the cushion bands and the
    diamonds are laid out round them): ((x, y, w, h), (corner radii: tl, tr, br, bl))."""
    arm = RAIL_PX + CORNER_ARM + PLATE_MARGIN
    right, bottom = OUTER_X + OUTER_W, OUTER_Y + OUTER_H
    mid = FIELD_X + FIELD_W / 2
    small = 4
    return [
        ((OUTER_X, OUTER_Y, arm, arm), (FRAME_R, small, small, small)),
        ((right - arm, OUTER_Y, arm, arm), (small, FRAME_R, small, small)),
        ((OUTER_X, bottom - arm, arm, arm), (small, small, small, FRAME_R)),
        ((right - arm, bottom - arm, arm, arm), (small, small, FRAME_R, small)),
        ((mid - SIDE_HALF, OUTER_Y, 2 * SIDE_HALF, RAIL_PX), (PLATE_R, PLATE_R, small, small)),
        (
            (mid - SIDE_HALF, bottom - RAIL_PX, 2 * SIDE_HALF, RAIL_PX),
            (small, small, PLATE_R, PLATE_R),
        ),
    ]


def cushion_outline(length: float, e: float = 0.0, steps: int = 10) -> list[tuple[float, float]]:
    """One cushion in its own axes: s along the strip, d from the cloth face (0) to the
    rail (CUSHION_PX). Both face-side corners are rounded; `e` > 0 grows the face side (shadow).
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
    so the rounded ends show next to the pocket ring.
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


def cushion_bands() -> list[tuple[float, float, float, float]]:
    """(x, y, w, h) of the four bands the cushions sit in, between the cloth and the rail.

    The corner squares are left out: there the housing belongs.
    """
    right, bottom = FIELD_X + FIELD_W, FIELD_Y + FIELD_H
    t = CUSHION_PX
    return [
        (FIELD_X, FIELD_Y - t, FIELD_W, t),
        (FIELD_X, bottom, FIELD_W, t),
        (FIELD_X - t, FIELD_Y, t, FIELD_H),
        (right, FIELD_Y, t, FIELD_H),
    ]


def _strip_points(a, b, out, e: float = 0.0) -> list[tuple[float, float]]:
    """cushion_outline mapped onto the table: s runs from a to b, d goes towards `out`."""
    length = math.dist(a, b)
    tx, ty = (b[0] - a[0]) / length, (b[1] - a[1]) / length
    return [
        (a[0] + s * tx + d * out[0], a[1] + s * ty + d * out[1])
        for s, d in cushion_outline(length, e)
    ]


def pocket_outward(px: float, py: float) -> tuple[float, float]:
    """Unit vector towards the outside of the table at a pocket: diagonal at a corner pocket,
    straight up/down at a middle pocket."""
    ux = (px > TABLE_L * 0.75) - (px < TABLE_L * 0.25)  # -1, 0 or +1
    uy = (py > TABLE_W * 0.75) - (py < TABLE_W * 0.25)
    n = math.hypot(ux, uy)
    return ux / n, uy / n


def sight_points() -> list[tuple[float, float]]:
    """Centres of the diamonds: every eighth of the long rails, every quarter of the short."""
    depth = WOOD_PX / 2
    top, bottom = OUTER_Y + depth, OUTER_Y + OUTER_H - depth
    left, right = OUTER_X + depth, OUTER_X + OUTER_W - depth
    pts = []
    for k in (1, 2, 3, 5, 6, 7):  # k = 4 is the middle pocket
        x = FIELD_X + FIELD_W * k / 8
        pts += [(x, top), (x, bottom)]
    for k in (1, 2, 3):
        y = FIELD_Y + FIELD_H * k / 4
        pts += [(left, y), (right, y)]
    return pts


# --- step 1: the dark shapes ---------------------------------------------------------------
def _paint_dark(s: pg.Surface, v: View) -> None:
    """Rail, cloth and cushions on a transparent surface (the night shows round them)."""
    pg.draw.rect(s, C.RAIL, v.rect(OUTER_X, OUTER_Y, OUTER_W, OUTER_H), border_radius=v.i(FRAME_R))
    field = v.rect(FIELD_X, FIELD_Y, FIELD_W, FIELD_H)
    s.blit(cloth_gradient(field.size), field.topleft)

    # the housings reach over the cushion band: cover that band first, so nothing peeks out
    # next to the rounded ends and the housings only show on the rail
    for x, y, w, h in cushion_bands():
        s.fill(C.CUSHION_BASE, v.rect(x, y, w, h))
    strips = cushion_strips()
    # the soft shadow on the cloth follows the rounded outline: widest ring first, then narrower
    shade = pg.Surface(v.rect(0, 0, OUTER_W, OUTER_H).size, pg.SRCALPHA)
    for dist, alpha in CUSHION_SHADOW:
        for a, b, out in strips:
            pts = [
                ((x - OUTER_X) * v.s, (y - OUTER_Y) * v.s)
                for x, y in _strip_points(a, b, out, dist)
            ]
            pg.draw.polygon(shade, (0, 0, 0, alpha), pts)
    s.blit(shade, v.pt((OUTER_X, OUTER_Y)))
    for a, b, out in strips:
        pts = _strip_points(a, b, out)
        pg.draw.polygon(s, C.CUSHION, [v.pt(p) for p in pts])
        pg.draw.line(s, C.CUSHION_BASE, v.pt(pts[0]), v.pt(pts[-1]), max(1, v.i(1.2)))


# --- step 2: the halo -------------------------------------------------------------------------
def _glow_pass(dev: pg.Surface, v: View) -> None:
    """Add the soft light round every lit line: one small layer, blurred, stretched, added."""
    look = C.LOOK
    lv = View(v.s / GLOW_DOWN)
    w, h = dev.get_size()
    layer = pg.Surface((max(1, w // GLOW_DOWN), max(1, h // GLOW_DOWN)))

    def lit(color, f: float) -> tuple[int, int, int]:
        return tuple(min(255, round(c * f * look.glow)) for c in color)

    rim = lv.rect(OUTER_X, OUTER_Y, OUTER_W, OUTER_H)
    for width, f in ((11, 0.30), (6, 0.55), (2.5, 0.85)):
        pg.draw.rect(layer, lit(C.CYAN, f), rim, max(1, lv.i(width)), border_radius=lv.i(FRAME_R))
    for a, b, out in cushion_strips():
        pts = [lv.pt(p) for p in _strip_points(a, b, out)[1:-1]]
        for width, f in ((7, 0.30), (3, 0.55)):
            pg.draw.lines(layer, lit(C.CUSHION_NOSE, f), False, pts, max(1, lv.i(width)))
    for px, py, pr in POCKETS:
        c, r = lv.pt(to_px(px, py)), pr * PX_PER_M + LIP_PX
        for width, f in ((10, 0.30), (5, 0.60), (2.4, 0.9)):
            pg.draw.circle(layer, lit(C.POCKET_RING, f), c, lv.n(r + width / 2), lv.i(width))
    for x, y in sight_points():
        pg.draw.circle(layer, lit(C.SIGHT, 0.5), lv.pt((x, y)), lv.n(SIGHT_R * 1.6))

    soft = glow.blur_pm(layer, 4.5 * look.reach)
    dev.blit(pg.transform.smoothscale(soft, dev.get_size()), (0, 0), special_flags=pg.BLEND_RGB_ADD)


# --- step 3: the lit lines --------------------------------------------------------------------
def _paint_lines(s: pg.Surface, v: View) -> None:
    """The cores of the lit lines and the pockets, on a transparent surface."""
    line = C.LOOK.line
    pg.draw.rect(
        s,
        C.CYAN,
        v.rect(OUTER_X, OUTER_Y, OUTER_W, OUTER_H),
        max(1, v.i(2.0 * line)),
        border_radius=v.i(FRAME_R),
    )
    for a, b, out in cushion_strips():
        pts = [v.pt(p) for p in _strip_points(a, b, out)[1:-1]]
        pg.draw.lines(s, C.CUSHION_NOSE, False, pts, max(1, v.i(1.8 * line)))

    for px, py, pr in POCKETS:  # a ring of light round a deep hole sunk towards the outside
        c = v.pt(to_px(px, py))
        r = pr * PX_PER_M
        ux, uy = pocket_outward(px, py)
        pg.draw.circle(s, C.POCKET_WALL, c, v.n(r + LIP_PX))
        steps = 6
        for i in range(steps):
            t = i / (steps - 1)
            shift = r * HOLE_SHIFT * t
            centre = (c[0] + ux * v.n(shift), c[1] + uy * v.n(shift))
            pg.draw.circle(s, _lerp(C.POCKET_WALL, C.POCKET, t), centre, v.n(r * (0.92 - 0.58 * t)))
        ring = max(1, v.i(2.0 * line))
        pg.draw.circle(s, C.POCKET_RING, c, v.n(r + LIP_PX) + ring / 2, ring)

    rr = SIGHT_R
    for x, y in sight_points():
        diamond = [v.pt((x, y - rr)), v.pt((x + rr, y)), v.pt((x, y + rr)), v.pt((x - rr, y))]
        pg.draw.polygon(s, C.SIGHT, diamond)


def _shrink(big: pg.Surface, size: tuple[int, int]) -> pg.Surface:
    return pg.transform.smoothscale(big.premul_alpha(), size)


@cache
def build_table(v: View) -> pg.Surface:
    """The finished table for this view's resolution: painted at 3x (2x when big), shrunk once.

    Remembered per resolution, so the how-to-play pictures and the game share one table: never draw
    on the result, only blit it. The two big layers only cover the table, not the whole canvas.
    """
    k = v.ss()
    box = v.rect(OUTER_X - 3, OUTER_Y - 3, OUTER_W + 6, OUTER_H + 6)  # device px
    big = CropView(v.s * k, box.x * k, box.y * k)
    layer_size = (box.w * k, box.h * k)

    dark = pg.Surface(layer_size, pg.SRCALPHA)
    _paint_dark(dark, big)
    dev = backdrop.night(v.size).copy()
    dev.blit(_shrink(dark, box.size), box.topleft, special_flags=pg.BLEND_PREMULTIPLIED)
    del dark
    _glow_pass(dev, v)
    lines = pg.Surface(layer_size, pg.SRCALPHA)
    _paint_lines(lines, big)
    dev.blit(_shrink(lines, box.size), box.topleft, special_flags=pg.BLEND_PREMULTIPLIED)
    return dev
