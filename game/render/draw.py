"""Drawing helpers at device resolution: balls, aim, pull bar (the table is in table.py).

Smooth edges: shapes with transparency are painted on a bigger surface, converted to
premultiplied alpha, shrunk with smoothscale and blitted with BLEND_PREMULTIPLIED (plain
smoothscale on straight alpha leaves dark fringes). Opaque layers are just shrunk.
"""

from __future__ import annotations

import math

import pygame as pg

from game.config import (
    BALL_R,
)
from game.render import fonts
from game.render import palette as C
from game.render.layout import (
    BALL_PX,
    to_px,
)
from game.render.table import build_table
from game.render.view import View

OUT_PX = 2.4  # thick cartoon outline of a ball (logical px)
SS_BALL = 4  # sprites are painted at 4x
RIM = BALL_PX + OUT_PX
SHADOW_DROP = 3.5  # a ball's shadow sits this far straight below it (logical px)
BAR_HALF_W = 4.5  # half width of the pull bar (logical px)
BAR_EDGE = 2.4  # black outline of the pull bar


# --- smooth-shape plumbing -------------------------------------------------------------
def shrink_pm(big: pg.Surface, size: tuple[int, int]) -> pg.Surface:
    """Premultiply, then shrink: the result must be blitted with BLEND_PREMULTIPLIED."""
    return pg.transform.smoothscale(big.premul_alpha(), size)


def blit_pm(dst: pg.Surface, spr: pg.Surface, pos: tuple[float, float]) -> None:
    dst.blit(spr, (round(pos[0]), round(pos[1])), special_flags=pg.BLEND_PREMULTIPLIED)


class Aa:
    """A transparent supersampled layer over a device-pixel box; `done()` shrinks it onto canvas."""

    def __init__(self, canvas: pg.Surface, v: View, box: pg.Rect, ss: int = 2) -> None:
        self.canvas, self.v, self.ss = canvas, v, ss
        self.box = box.clip(canvas.get_rect())
        self.surf = pg.Surface((max(1, self.box.w * ss), max(1, self.box.h * ss)), pg.SRCALPHA)

    def pt(self, p: tuple[float, float]) -> tuple[float, float]:
        """Logical point -> coordinates on the big surface."""
        return (p[0] * self.v.s - self.box.x) * self.ss, (p[1] * self.v.s - self.box.y) * self.ss

    def n(self, length: float) -> float:
        return length * self.v.s * self.ss

    def result(self) -> tuple[pg.Surface, tuple[int, int]] | None:
        """The finished (premultiplied surface, top-left), or None for an empty box."""
        if self.box.w > 0 and self.box.h > 0:
            return shrink_pm(self.surf, self.box.size), self.box.topleft
        return None

    def done(self) -> None:
        res = self.result()
        if res is not None:
            blit_pm(self.canvas, *res)


def box_around(v: View, points: list[tuple[float, float]], pad: float) -> pg.Rect:
    xs, ys = [p[0] for p in points], [p[1] for p in points]
    return v.rect(
        min(xs) - pad, min(ys) - pad, max(xs) - min(xs) + 2 * pad, max(ys) - min(ys) + 2 * pad
    )


_rr_cache: dict[tuple, pg.Surface] = {}


def rrect_sprite(
    v: View, w: float, h: float, radius: float, fill, edge: float, edge_color=C.OUTLINE
) -> pg.Surface:
    """Outlined rounded rectangle (logical w x h inside an `edge` black border), premultiplied."""
    key = (round(v.s, 4), w, h, radius, fill, edge, edge_color)
    if key not in _rr_cache:
        if len(_rr_cache) > 96:
            _rr_cache.clear()
        bv = v.scaled(v.ss())
        ow, oh = w + 2 * edge, h + 2 * edge
        big = pg.Surface((bv.i(ow), bv.i(oh)), pg.SRCALPHA)
        pg.draw.rect(big, edge_color, big.get_rect(), border_radius=bv.i(radius + edge))
        pg.draw.rect(big, fill, bv.rect(edge, edge, w, h), border_radius=bv.i(radius))
        _rr_cache[key] = shrink_pm(big, (v.i(ow), v.i(oh)))
    return _rr_cache[key]


def blit_rrect(
    canvas: pg.Surface,
    v: View,
    x: float,
    y: float,
    w: float,
    h: float,
    radius: float,
    fill,
    edge: float = 5,
    edge_color=C.OUTLINE,
) -> None:
    spr = rrect_sprite(v, w, h, radius, fill, edge, edge_color)
    blit_pm(canvas, spr, v.pt((x - edge, y - edge)))


# --- balls -----------------------------------------------------------------------------
class BallSprites:
    """Cached premultiplied ball sprites at this view's resolution, plus one shared shadow."""

    def __init__(self, v: View) -> None:
        self.v = v
        self.size = math.ceil(2 * (BALL_PX + OUT_PX) * v.s) + 2
        self._cache: dict[int, pg.Surface] = {}
        self.shadow = self._make_shadow()

    def get(self, number: int) -> pg.Surface:
        if number not in self._cache:
            self._cache[number] = self._make(number)
        return self._cache[number]

    def _make_shadow(self) -> pg.Surface:
        big = pg.Surface((self.size * SS_BALL, self.size * SS_BALL), pg.SRCALPHA)
        c = self.size * SS_BALL / 2
        pg.draw.circle(big, (0, 0, 0, 58), (c, c), (BALL_PX + OUT_PX) * self.v.s * SS_BALL)
        return shrink_pm(big, (self.size, self.size))

    def _make(self, number: int) -> pg.Surface:
        bv = self.v.scaled(SS_BALL)
        big_size = self.size * SS_BALL
        c = big_size / 2
        r = BALL_PX * bv.s
        surf = pg.Surface((big_size, big_size), pg.SRCALPHA)
        pg.draw.circle(surf, C.OUTLINE, (c, c), r + OUT_PX * bv.s)
        base = number if number <= 8 else number - 8
        pg.draw.circle(surf, C.BALL_COLORS[base], (c, c), r)

        if number > 8:  # stripe: a white band across the middle, clipped to the ball
            band = pg.Surface((big_size, big_size), pg.SRCALPHA)
            pg.draw.rect(band, C.WHITE, (0, c - r * 0.46, big_size, r * 0.92))
            mask = pg.Surface((big_size, big_size), pg.SRCALPHA)
            pg.draw.circle(mask, (255, 255, 255, 255), (c, c), r)
            band.blit(mask, (0, 0), special_flags=pg.BLEND_RGBA_MIN)
            surf.blit(band, (0, 0))

        if number != 0:  # white dot with the number
            pg.draw.circle(surf, C.OUTLINE, (c, c), r * 0.56)
            pg.draw.circle(surf, C.WHITE, (c, c), r * 0.50)
            font = fonts.get(max(6, int(r * (1.0 if number < 10 else 0.8))), bold=True)
            text = font.render(str(number), True, C.OUTLINE)
            surf.blit(text, text.get_rect(center=(c, c)))

        return shrink_pm(surf, (self.size, self.size))


def draw_balls(canvas: pg.Surface, v: View, balls, sprites: BallSprites) -> None:
    half = sprites.size / 2
    for b in balls:
        if b.in_play:
            x, y = v.pt(to_px(b.x, b.y))
            # light comes from straight above the screen: the shadow falls straight down
            blit_pm(canvas, sprites.shadow, (x - half, y - half + v.n(SHADOW_DROP)))
    for b in balls:
        if b.in_play:
            x, y = v.pt(to_px(b.x, b.y))
            blit_pm(canvas, sprites.get(b.number), (x - half, y - half))


def draw_ring(
    canvas: pg.Surface,
    v: View,
    centre: tuple[float, float],
    radius: float,
    color: tuple[int, int, int, int],
    width: float = 3,
) -> None:
    """A smooth ring around a logical point (the cue ball in hand, ."""
    pad = radius + width + 2
    layer = Aa(canvas, v, v.rect(centre[0] - pad, centre[1] - pad, 2 * pad, 2 * pad))
    pg.draw.circle(
        layer.surf, color, layer.pt(centre), layer.n(radius), max(1, round(layer.n(width)))
    )
    layer.done()


# --- aiming: glow line, ghost ball, arrow, pull bar ------------------------------------
def power_color(power: float) -> tuple[int, int, int]:
    """Yellow -> orange as the shot gets harder."""
    return 250, round(232 - 118 * power), round(60 - 20 * power)


def _object_center(contact) -> tuple[float, float]:
    """Centre of the ball that will be hit: contact point + 2R along object_dir."""
    dx, dy = contact.object_dir
    return contact.point[0] + dx * 2 * BALL_R, contact.point[1] + dy * 2 * BALL_R


def _bar_polygon(p0, d, length: float, half_w: float):
    """Straight bar from p0 along unit d: a plain rectangle with square corners."""
    nx, ny = -d[1], d[0]
    p1 = (p0[0] + d[0] * length, p0[1] + d[1] * length)
    return [
        (p0[0] + nx * half_w, p0[1] + ny * half_w),
        (p1[0] + nx * half_w, p1[1] + ny * half_w),
        (p1[0] - nx * half_w, p1[1] - ny * half_w),
        (p0[0] - nx * half_w, p0[1] - ny * half_w),
    ]


def draw_aim(
    canvas: pg.Surface,
    v: View,
    cue,
    contact,
    shot_dir,
    bar_len: float,
    power: float,
) -> None:
    """Pull bar behind the cue ball (`bar_len` logical px, already capped by DragAim), glow line
    to the first contact, ghost ball there and an arrow on a hit ball: one supersampled layer.
    """
    _paint_aim(canvas, v, cue, contact, shot_dir, bar_len, power).done()


def _paint_aim(canvas: pg.Surface, v: View, cue, contact, shot_dir, bar_len, power) -> Aa:
    centre = to_px(cue.x, cue.y)
    end = to_px(*contact.point)
    ux, uy = -shot_dir[0], -shot_dir[1]  # the bar points AWAY from where the ball will go
    bar0 = (centre[0] + ux * (RIM + 3), centre[1] + uy * (RIM + 3))
    bar1 = (bar0[0] + ux * bar_len, bar0[1] + uy * bar_len)

    pts = [centre, end, bar1]
    obj = None
    if contact.kind == "ball" and contact.object_dir is not None:
        ox, oy = to_px(*_object_center(contact))
        dx, dy = contact.object_dir
        obj = (ox + dx * (RIM + 3), oy + dy * (RIM + 3), dx, dy)
        pts.append((obj[0] + dx * 40, obj[1] + dy * 40))
    layer = Aa(canvas, v, box_around(v, pts, 26), ss=2 if v.s <= 1.3 else 1)
    surf = layer.surf

    # pull bar: a straight rectangle, black outline, power-coloured fill, square ends
    if bar_len > 6:
        outline = _bar_polygon(
            layer.pt((bar0[0] - ux * BAR_EDGE, bar0[1] - uy * BAR_EDGE)),
            (ux, uy),
            layer.n(bar_len + 2 * BAR_EDGE),
            layer.n(BAR_HALF_W + BAR_EDGE),
        )
        poly = _bar_polygon(layer.pt(bar0), (ux, uy), layer.n(bar_len), layer.n(BAR_HALF_W))
        pg.draw.polygon(surf, C.OUTLINE, outline)
        pg.draw.polygon(surf, power_color(power), poly)

    # glow line from the ball's rim to the first contact
    ax, ay = end[0] - centre[0], end[1] - centre[1]
    alen = math.hypot(ax, ay)
    if alen > RIM:
        a = layer.pt((centre[0] + ax / alen * RIM, centre[1] + ay / alen * RIM))
        b = layer.pt(end)
        for width, color in ((13, (*C.AIM_GLOW, 46)), (8, (*C.AIM_GLOW, 96)), (3, (*C.AIM, 255))):
            pg.draw.line(surf, color, a, b, max(1, round(layer.n(width))))
            pg.draw.circle(surf, color, a, layer.n(width / 2))
            pg.draw.circle(surf, color, b, layer.n(width / 2))
    pg.draw.circle(surf, C.AIM, layer.pt(end), layer.n(BALL_PX), max(1, round(layer.n(3))))

    if obj is not None:  # arrow showing where the hit ball will go
        sx, sy, dx, dy = obj
        tail, head_base = layer.pt((sx, sy)), layer.pt((sx + dx * 26, sy + dy * 26))
        pg.draw.line(surf, C.OUTLINE, tail, head_base, max(1, round(layer.n(9))))
        pg.draw.line(surf, C.ACCENT, tail, head_base, max(1, round(layer.n(4))))
        nx, ny = -dy, dx
        hx, hy = sx + dx * 26, sy + dy * 26
        head = [
            layer.pt((hx + dx * 11, hy + dy * 11)),
            layer.pt((hx + nx * 8, hy + ny * 8)),
            layer.pt((hx - nx * 8, hy - ny * 8)),
        ]
        pg.draw.polygon(surf, C.ACCENT, head)
        pg.draw.polygon(surf, C.OUTLINE, head, max(1, round(layer.n(3))))
    return layer


__all__ = [
    "Aa",
    "BallSprites",
    "blit_pm",
    "blit_rrect",
    "build_table",
    "draw_aim",
    "draw_balls",
    "draw_ring",
    "power_color",
    "rrect_sprite",
    "shrink_pm",
]
