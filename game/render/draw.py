"""Drawing helpers at device resolution: balls, aim, pull bar, glass panels (table: table.py).

Smooth edges: shapes with transparency are painted on a bigger surface, converted to
premultiplied alpha, shrunk with smoothscale and blitted with BLEND_PREMULTIPLIED (plain
smoothscale on straight alpha leaves dark fringes). Opaque layers are just shrunk.
Light: every lit shape gets a halo from render/glow.py, sized by the chosen palette.LOOK.
"""

from __future__ import annotations

import math

import pygame as pg

from game.config import (
    BALL_R,
)
from game.render import fonts
from game.render import palette as C
from game.render.glow import halo, lit
from game.render.layout import (
    BALL_PX,
    to_px,
)
from game.render.table import build_table
from game.render.view import View

RING_PX = 1.8  # the lit ring of a ball (logical px), centred on the physical edge
HALO_PX = 6.0  # how far a ball's light reaches past its edge (logical px, before the look)
RIM = BALL_PX + RING_PX / 2 + 0.6  # where the aim line and the bar start: just outside the ring
SS_BALL = 4  # sprites are painted at 4x
BAR_HALF_W = 4.5  # half width of the pull bar (logical px)


# --- smooth-shape plumbing -------------------------------------------------------------
def shrink_pm(big: pg.Surface, size: tuple[int, int]) -> pg.Surface:
    """Premultiply, then shrink: the result must be blitted with BLEND_PREMULTIPLIED."""
    return pg.transform.smoothscale(big.premul_alpha(), size)


def blit_pm(dst: pg.Surface, spr: pg.Surface, pos: tuple[float, float]) -> None:
    dst.blit(spr, (round(pos[0]), round(pos[1])), special_flags=pg.BLEND_PREMULTIPLIED)


def blit_add(dst: pg.Surface, spr: pg.Surface, pos: tuple[float, float]) -> None:
    """Add light (the surface's RGB, premultiplied by its alpha) on top of a dark ground."""
    dst.blit(spr, (round(pos[0]), round(pos[1])), special_flags=pg.BLEND_RGB_ADD)


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


# --- glass panels and dots ---------------------------------------------------------------
_rr_cache: dict[tuple, tuple[pg.Surface, int]] = {}
_dot_cache: dict[tuple, tuple[pg.Surface, int]] = {}
FILL_ALPHA = 232  # glass: a little of the night behind shows through


def _halo_px(glow: float) -> int:
    """Logical px of room a lit shape needs round it for its halo (0 when unlit)."""
    return math.ceil(7 * glow * C.LOOK.reach) if glow > 0 else 0


def rrect_sprite(
    v: View, w: float, h: float, radius: float, fill, edge: float, edge_color, glow: float
) -> tuple[pg.Surface, int]:
    """A glass rounded rectangle (logical w x h) with a lit edge and its halo, premultiplied.

    Returns (sprite, pad): the sprite reaches `pad` logical px past the rectangle on every side.
    """
    key = (round(v.s, 4), w, h, radius, fill, edge, edge_color, round(glow, 3))
    if key not in _rr_cache:
        if len(_rr_cache) > 96:
            _rr_cache.clear()
        pad = _halo_px(glow) + math.ceil(edge) + 1
        bv = v.scaled(v.ss())
        ow, oh = w + 2 * pad, h + 2 * pad
        body = bv.rect(pad, pad, w, h)
        r = bv.i(radius)
        plate = pg.Surface((bv.i(ow), bv.i(oh)), pg.SRCALPHA)
        pg.draw.rect(plate, (*fill, FILL_ALPHA), body, border_radius=r)
        out = plate.premul_alpha()
        if edge > 0:
            line = pg.Surface(plate.get_size(), pg.SRCALPHA)
            width = max(1, bv.i(edge * C.LOOK.line))
            pg.draw.rect(line, edge_color, body, width, border_radius=r)
            line = line.premul_alpha()
            if glow > 0:
                light = halo(line, bv.n(_halo_px(glow)) * 0.55, 1.6 * glow * C.LOOK.glow)
                out.blit(light, (0, 0), special_flags=pg.BLEND_RGBA_ADD)
            out.blit(line, (0, 0), special_flags=pg.BLEND_PREMULTIPLIED)
        _rr_cache[key] = (pg.transform.smoothscale(out, (v.i(ow), v.i(oh))), pad)
    return _rr_cache[key]


def blit_rrect(
    canvas: pg.Surface,
    v: View,
    x: float,
    y: float,
    w: float,
    h: float,
    radius: float,
    fill=C.PANEL,
    edge: float = 1.5,
    edge_color=C.CYAN_DIM,
    glow: float = 0.0,
) -> None:
    spr, pad = rrect_sprite(v, w, h, radius, fill, edge, edge_color, glow)
    blit_pm(canvas, spr, v.pt((x - pad, y - pad)))


def blit_dot(
    canvas: pg.Surface, v: View, centre: tuple[float, float], r: float, color, glow: float = 0.0
) -> None:
    """A small lit disc (page dots, switches) with its halo, centred on a logical point."""
    key = (round(v.s, 4), r, color, round(glow, 3))
    if key not in _dot_cache:
        if len(_dot_cache) > 64:
            _dot_cache.clear()
        pad = _halo_px(glow) + 1
        bv = v.scaled(v.ss())
        size = 2 * (r + pad)
        disc = pg.Surface((bv.i(size), bv.i(size)), pg.SRCALPHA)
        pg.draw.circle(disc, color, (disc.get_width() / 2, disc.get_height() / 2), bv.n(r))
        disc = disc.premul_alpha()
        out = lit(disc, bv.n(pad) * 0.6, 1.4 * glow * C.LOOK.glow) if glow > 0 else disc
        _dot_cache[key] = (pg.transform.smoothscale(out, (v.i(size), v.i(size))), pad)
    spr, pad = _dot_cache[key]
    blit_pm(canvas, spr, v.pt((centre[0] - r - pad, centre[1] - r - pad)))


# --- balls -----------------------------------------------------------------------------
class BallSprites:
    """Cached premultiplied ball sprites at this view's resolution.

    A ball is a dark body with a lit ring and a lit number, like a lamp; a stripe has a lit band
    across the body, the cue ball is one lit disc. `get` has the halo, `core` does not (the small
    balls in the side panel).
    """

    def __init__(self, v: View) -> None:
        self.v = v
        self.core_size = math.ceil(2 * (BALL_PX + RING_PX) * v.s) + 2
        self.size = math.ceil(2 * (BALL_PX + HALO_PX * C.LOOK.reach) * v.s) + 2
        self._cache: dict[tuple[int, bool], pg.Surface] = {}

    def get(self, number: int) -> pg.Surface:
        return self._get(number, True)

    def core(self, number: int) -> pg.Surface:
        return self._get(number, False)

    def _get(self, number: int, with_halo: bool) -> pg.Surface:
        key = (number, with_halo)
        if key not in self._cache:
            self._cache[key] = self._make(number, with_halo)
        return self._cache[key]

    def _make(self, number: int, with_halo: bool) -> pg.Surface:
        bv = self.v.scaled(SS_BALL)
        size = self.size if with_halo else self.core_size
        big = size * SS_BALL
        c = big / 2
        r = BALL_PX * bv.s
        ring = max(2.0, RING_PX * C.LOOK.line * bv.s)
        base = number if number <= 8 else number - 8
        color = C.BALL_COLORS[base]

        light = pg.Surface((big, big), pg.SRCALPHA)  # everything that gives light
        body = pg.Surface((big, big), pg.SRCALPHA)  # the dark body under it
        if number == 0:  # the cue ball: one lit disc
            pg.draw.circle(light, color, (c, c), r + ring / 2)
        else:
            pg.draw.circle(body, C.BODY, (c, c), r)
            if number > 8:  # a stripe: two lit chords with a faint glow between them
                band = pg.Surface((big, big), pg.SRCALPHA)
                pg.draw.rect(band, (*color, 60), (0, c - r * 0.52, big, r * 1.04))
                for sign in (-1, 1):
                    y = c + sign * r * 0.52
                    pg.draw.line(band, (*color, 255), (0, y), (big, y), max(1, round(ring * 0.7)))
                mask = pg.Surface((big, big), pg.SRCALPHA)
                pg.draw.circle(mask, (255, 255, 255, 255), (c, c), r)
                band.blit(mask, (0, 0), special_flags=pg.BLEND_RGBA_MIN)
                light.blit(band, (0, 0))
            pg.draw.circle(light, color, (c, c), r + ring / 2, round(ring))
            font = fonts.get(max(6, int(r * (1.0 if number < 10 else 0.82))), bold=True)
            text = font.render(str(number), True, C.WHITE if number > 8 else color)
            light.blit(text, text.get_rect(center=(c, c)))

        light_pm = light.premul_alpha()
        out = body.premul_alpha()
        if with_halo:
            glow = halo(light_pm, bv.n(HALO_PX * C.LOOK.reach) * 0.5, 1.3 * C.LOOK.glow)
            out.blit(glow, (0, 0), special_flags=pg.BLEND_RGBA_ADD)
        out.blit(light_pm, (0, 0), special_flags=pg.BLEND_PREMULTIPLIED)
        return pg.transform.smoothscale(out, (size, size))


def draw_balls(canvas: pg.Surface, v: View, balls, sprites: BallSprites) -> None:
    half = sprites.size / 2
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
    """A smooth ring around a logical point (the cue ball in hand)."""
    pad = radius + width + 2
    layer = Aa(canvas, v, v.rect(centre[0] - pad, centre[1] - pad, 2 * pad, 2 * pad))
    pg.draw.circle(
        layer.surf, color, layer.pt(centre), layer.n(radius), max(1, round(layer.n(width)))
    )
    layer.done()


# --- aiming: light line, ghost ball, arrow, pull bar ------------------------------------
def power_color(power: float) -> tuple[int, int, int]:
    """Cyan -> pink-violet as the shot gets harder."""
    return C.lerp(C.POWER_WEAK, C.POWER_STRONG, power)


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
    """Pull bar behind the cue ball (`bar_len` logical px, already capped by DragAim), light line
    to the first contact, ghost ball there and an arrow on a hit ball: one supersampled layer.
    """
    _paint_aim(canvas, v, cue, contact, shot_dir, bar_len, power).done()


def _alpha(base: float) -> int:
    return min(255, round(base * C.LOOK.glow))


def _paint_aim(canvas: pg.Surface, v: View, cue, contact, shot_dir, bar_len, power) -> Aa:
    look = C.LOOK
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

    # pull bar: a straight rectangle with square ends, lit in the colour of its power
    if bar_len > 6:
        colour = power_color(power)
        for grow, alpha in ((4.0 * look.reach, 40), (2.0 * look.reach, 90), (0.0, 255)):
            poly = _bar_polygon(
                layer.pt(bar0), (ux, uy), layer.n(bar_len), layer.n(BAR_HALF_W + grow)
            )
            pg.draw.polygon(surf, (*colour, _alpha(alpha) if grow else alpha), poly)
        core = _bar_polygon(layer.pt(bar0), (ux, uy), layer.n(bar_len), layer.n(BAR_HALF_W * 0.3))
        pg.draw.polygon(surf, (*C.lerp(colour, C.WHITE, 0.65), 255), core)  # the hot centre

    # light line from the ball's rim to the first contact
    ax, ay = end[0] - centre[0], end[1] - centre[1]
    alen = math.hypot(ax, ay)
    if alen > RIM:
        a = layer.pt((centre[0] + ax / alen * RIM, centre[1] + ay / alen * RIM))
        b = layer.pt(end)
        lines = (
            (13 * look.reach, (*C.AIM_GLOW, _alpha(40))),
            (7 * look.reach, (*C.AIM_GLOW, _alpha(95))),
            (2.6 * look.line, (*C.AIM, 255)),
        )
        for width, color in lines:
            pg.draw.line(surf, color, a, b, max(1, round(layer.n(width))))
            pg.draw.circle(surf, color, a, layer.n(width / 2))
            pg.draw.circle(surf, color, b, layer.n(width / 2))
    pg.draw.circle(
        surf, C.AIM, layer.pt(end), layer.n(BALL_PX), max(1, round(layer.n(2.2 * look.line)))
    )

    if obj is not None:  # arrow showing where the hit ball will go
        sx, sy, dx, dy = obj
        tail, head_base = layer.pt((sx, sy)), layer.pt((sx + dx * 26, sy + dy * 26))
        pg.draw.line(surf, (*C.ACCENT, _alpha(70)), tail, head_base, max(1, round(layer.n(9))))
        pg.draw.line(surf, C.ACCENT, tail, head_base, max(1, round(layer.n(3 * look.line))))
        nx, ny = -dy, dx
        hx, hy = sx + dx * 26, sy + dy * 26
        head = [
            layer.pt((hx + dx * 11, hy + dy * 11)),
            layer.pt((hx + nx * 8, hy + ny * 8)),
            layer.pt((hx - nx * 8, hy - ny * 8)),
        ]
        pg.draw.polygon(surf, C.ACCENT, head)
    return layer


__all__ = [
    "Aa",
    "BallSprites",
    "blit_add",
    "blit_dot",
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
