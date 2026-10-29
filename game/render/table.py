"""The table, painted once per resolution after the reference picture.

Wooden frame with grain, brass plates at the corners and middle pockets, cloth that is bright in
the centre and deep green at the edges, cushions whose ends are rounded and hug the pockets, deep
pockets (light lip, wall, dark hole sunk towards the outside) and gold diamonds on the rails.
No checkers: the old chessboard cloth is gone. Painted at k x and shrunk once (smooth edges).
"""

from __future__ import annotations

import math

import numpy as np
import pygame as pg

from game.config import POCKETS, PX_PER_M, RAIL_PX, TABLE_L, TABLE_W
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

CUSHION_PX = 12  # rubber between the cloth and the wood (the cloth edge is the cushion face)
WOOD_PX = RAIL_PX - CUSHION_PX
FRAME_R = 20  # outer corner radius of the frame
PLATE_R = 8  # corner radius of the middle-pocket plates
CORNER_ARM = POCKETS[0][2] * PX_PER_M  # the cushion face starts this far from the corner
PLATE_MARGIN = 10  # how far a plate reaches past the pocket along the rail (under the cushion)
SIDE_HALF = POCKETS[4][2] * PX_PER_M + PLATE_MARGIN  # half width of a middle-pocket plate
CUSHION_END_R = 12.0  # both ends of a cushion are rounded with this radius (as in the reference)
CUSHION_TUCK = -2.0  # a cushion starts this far inside the pocket circle (negative: short of it)
CUSHION_SHADOW = ((6.0, 10), (4.5, 24), (3.0, 38), (1.5, 56))  # (distance px, alpha) on the cloth
LIP_PX = 3.0  # the light metal lip around each pocket
WALL_PX = 1.4  # dark ring between the lip and the pocket wall
HOLE_SHIFT = 0.16  # the dark hole is sunk this fraction of the radius towards the outside
SIGHT_R = 3.6  # half diagonal of a rail diamond
CLOTH_RES = (320, 160)  # the cloth gradient is built this small, then stretched smoothly


def _lerp(a, b, t: float) -> tuple[int, int, int]:
    return tuple(round(x + (y - x) * t) for x, y in zip(a, b, strict=True))


def wood_color(depth: float) -> tuple[int, int, int]:
    """Wood colour `depth` logical px in from the outer edge of the frame."""
    t = min(1.0, max(0.0, depth / WOOD_PX))
    stops = C.WOOD_STOPS
    for (t0, c0), (t1, c1) in zip(stops, stops[1:], strict=False):
        if t <= t1:
            return _lerp(c0, c1, (t - t0) / (t1 - t0))
    return stops[-1][1]


def _hash(i: int, salt: float) -> float:
    """Repeatable pseudo-random number in [0, 1) (the picture must not change between runs)."""
    return abs(math.sin(i * 12.9898 + salt * 78.233) * 43758.5453) % 1.0


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


# --- parts -------------------------------------------------------------------------------
def _paint_wood(s: pg.Surface, v: View) -> None:
    pg.draw.rect(
        s,
        wood_color(WOOD_PX),
        v.rect(OUTER_X, OUTER_Y, OUTER_W, OUTER_H),
        border_radius=v.i(FRAME_R),
    )
    band = max(2, v.i(1) + 1)  # a ring is a bit wider than its step so rings never leave gaps
    for i in range(WOOD_PX):
        rect = v.rect(OUTER_X + i, OUTER_Y + i, OUTER_W - 2 * i, OUTER_H - 2 * i)
        pg.draw.rect(s, wood_color(i + 0.5), rect, band, border_radius=max(2, v.i(FRAME_R - i)))


def _paint_grain(s: pg.Surface, v: View) -> None:
    """Long faint streaks along each rail: lines in a slightly lighter/darker wood colour."""
    width = max(1, v.i(1))
    for rail in range(4):
        horizontal = rail < 2
        span0 = (OUTER_X if horizontal else OUTER_Y) + 36
        span1 = (OUTER_X + OUTER_W if horizontal else OUTER_Y + OUTER_H) - 36
        for j in range(26):
            depth = 2 + _hash(j, rail) * (WOOD_PX - 4)
            start = span0 + _hash(j, rail + 10) * (span1 - span0 - 60)
            end = min(span1, start + 50 + _hash(j, rail + 20) * 190)
            shade = 0.18 if _hash(j, rail + 30) > 0.45 else -0.14
            base = wood_color(depth)
            target = (255, 214, 150) if shade > 0 else (30, 12, 4)
            color = _lerp(base, target, abs(shade))
            if rail == 0:  # top
                a, b = (start, OUTER_Y + depth), (end, OUTER_Y + depth)
            elif rail == 1:  # bottom
                a, b = (start, OUTER_Y + OUTER_H - depth), (end, OUTER_Y + OUTER_H - depth)
            elif rail == 2:  # left
                a, b = (OUTER_X + depth, start), (OUTER_X + depth, end)
            else:  # right
                a, b = (OUTER_X + OUTER_W - depth, start), (OUTER_X + OUTER_W - depth, end)
            pg.draw.line(s, color, v.pt(a), v.pt(b), width)


def plate_rects() -> list[tuple[tuple[float, float, float, float], tuple[int, int, int, int]]]:
    """Six brass plates: ((x, y, w, h), (top-left, top-right, bottom-right, bottom-left radius))."""
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


def _paint_plates(s: pg.Surface, v: View) -> None:
    for (x, y, w, h), (tl, tr, br, bl) in plate_rects():
        for inset, color, width in ((0, C.PLATE_EDGE, 0), (2, C.PLATE, 0), (5, C.PLATE_INNER, 1)):
            rect = v.rect(x + inset, y + inset, w - 2 * inset, h - 2 * inset)
            pg.draw.rect(
                s,
                color,
                rect,
                max(1, v.i(width)) if width else 0,
                border_top_left_radius=max(1, v.i(tl - inset)),
                border_top_right_radius=max(1, v.i(tr - inset)),
                border_bottom_right_radius=max(1, v.i(br - inset)),
                border_bottom_left_radius=max(1, v.i(bl - inset)),
            )


def _paint_cloth(s: pg.Surface, v: View) -> None:
    field = v.rect(FIELD_X, FIELD_Y, FIELD_W, FIELD_H)
    s.blit(cloth_gradient(field.size), field.topleft)


def cushion_outline(length: float, e: float = 0.0, steps: int = 10) -> list[tuple[float, float]]:
    """One cushion in its own axes: s along the strip, d from the cloth face (0) to the
    wood (CUSHION_PX). Both face-side corners are rounded; `e` > 0 grows the face side (shadow).
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
    """(start, end, out) of the six cushions: along the cloth edge, `out` points at the wood.

    Each strip stops CUSHION_TUCK px inside the pocket circle on both ends (negative: short of it),
    so the rounded ends show next to the pocket lip.
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


def _strip_points(a, b, out, e: float = 0.0) -> list[tuple[float, float]]:
    """cushion_outline mapped onto the table: s runs from a to b, d goes towards `out`."""
    length = math.dist(a, b)
    tx, ty = (b[0] - a[0]) / length, (b[1] - a[1]) / length
    return [
        (a[0] + s * tx + d * out[0], a[1] + s * ty + d * out[1])
        for s, d in cushion_outline(length, e)
    ]


def _paint_cushions(s: pg.Surface, v: View) -> None:
    """Rubber strips along the cloth edge (the face is the cloth edge), rounded at both ends."""
    strips = cushion_strips()
    # the soft shadow on the cloth follows the rounded outline: widest ring first, then narrower
    ox, oy = OUTER_X, OUTER_Y
    shade = pg.Surface(v.rect(0, 0, OUTER_W, OUTER_H).size, pg.SRCALPHA)
    for dist, alpha in CUSHION_SHADOW:
        for a, b, out in strips:
            pts = [v.pt((x - ox, y - oy)) for x, y in _strip_points(a, b, out, dist)]
            pg.draw.polygon(shade, (0, 0, 0, alpha), pts)
    s.blit(shade, v.pt((ox, oy)))
    for a, b, out in strips:
        pts = _strip_points(a, b, out)
        pg.draw.polygon(s, C.CUSHION, [v.pt(p) for p in pts])
        pg.draw.line(s, C.CUSHION_BASE, v.pt(pts[0]), v.pt(pts[-1]), max(1, v.i(1.2)))
        pg.draw.lines(s, C.CUSHION_NOSE, False, [v.pt(p) for p in pts[1:-1]], max(1, v.i(1.6)))


def _blend_circle(s: pg.Surface, v: View, centre, radius: float, color) -> None:
    """A translucent disc (pygame's own draw would overwrite the pixels, not blend them)."""
    n = v.n(radius)
    layer = pg.Surface((2 * math.ceil(n) + 2,) * 2, pg.SRCALPHA)
    pg.draw.circle(layer, color, (layer.get_width() / 2, layer.get_height() / 2), n)
    s.blit(layer, (centre[0] - layer.get_width() / 2, centre[1] - layer.get_height() / 2))


def pocket_outward(px: float, py: float) -> tuple[float, float]:
    """Unit vector towards the outside of the table at a pocket: diagonal at a corner pocket,
    straight up/down at a middle pocket."""
    ux = (px > TABLE_L * 0.75) - (px < TABLE_L * 0.25)  # -1, 0 or +1
    uy = (py > TABLE_W * 0.75) - (py < TABLE_W * 0.25)
    n = math.hypot(ux, uy)
    return ux / n, uy / n


def _paint_pockets(s: pg.Surface, v: View) -> None:
    """Each pocket: a soft shadow on the plate, a light lip, a dark ring, the wall and a deep hole.

    The hole is a stack of ever smaller, darker discs sunk towards the outside of the table, so the
    near wall shows as a crescent: that is what gives the pocket its depth.
    """
    for px, py, pr in POCKETS:
        c = v.pt(to_px(px, py))
        r = pr * PX_PER_M
        ux, uy = pocket_outward(px, py)
        for extra, alpha in ((7.0, 18), (5.0, 30), (3.0, 46)):
            _blend_circle(s, v, c, r + LIP_PX + extra * 0.6, (0, 0, 0, alpha))
        pg.draw.circle(s, C.POCKET_LIP, c, v.n(r + LIP_PX))
        pg.draw.circle(s, C.POCKET_RIM, c, v.n(r + WALL_PX))
        pg.draw.circle(s, C.POCKET_WALL, c, v.n(r))
        steps = 6
        for i in range(steps):
            t = i / (steps - 1)
            shift = r * HOLE_SHIFT * t
            centre = (c[0] + ux * v.n(shift), c[1] + uy * v.n(shift))
            color = _lerp(C.POCKET_WALL, C.POCKET, t)
            pg.draw.circle(s, color, centre, v.n(r * (0.92 - 0.58 * t)))


def sight_points() -> list[tuple[float, float]]:
    """Centres of the gold diamonds: every eighth of the long rails, every quarter of the short."""
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


def _paint_sights(s: pg.Surface, v: View) -> None:
    r = SIGHT_R
    for x, y in sight_points():
        diamond = [v.pt((x, y - r)), v.pt((x + r, y)), v.pt((x, y + r)), v.pt((x - r, y))]
        pg.draw.polygon(s, C.SIGHT_EDGE, diamond)
        inner = [v.pt((x, y - r * 0.72)), v.pt((x + r * 0.72, y)), v.pt((x, y + r * 0.72))]
        pg.draw.polygon(s, C.SIGHT, [*inner, v.pt((x - r * 0.72, y))])


def paint_table(s: pg.Surface, v: View) -> None:
    s.fill(C.BG)
    _paint_wood(s, v)
    _paint_grain(s, v)
    _paint_plates(s, v)
    _paint_cloth(s, v)
    _paint_cushions(s, v)
    _paint_pockets(s, v)
    _paint_sights(s, v)


def build_table(v: View) -> pg.Surface:
    """The finished table for this view's resolution: painted at 3x (2x when big), shrunk once."""
    k = v.ss()
    big = pg.Surface(v.scaled(k).size)
    paint_table(big, v.scaled(k))
    return pg.transform.smoothscale(big, v.size)
