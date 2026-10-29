"""Drawing helpers at device resolution: balls, aim, the neon cue, solid panels (table: table.py).

Smooth edges: shapes with transparency are painted on a bigger surface, converted to
premultiplied alpha, shrunk with smoothscale and blitted with BLEND_PREMULTIPLIED (plain
smoothscale on straight alpha leaves dark fringes). Opaque layers are just shrunk.
Light: every lit shape gets a halo from render/glow.py, sized by the chosen palette.LOOK.
"""

from __future__ import annotations

import math

import pygame as pg

from game.config import BALL_R, CUE_SHOW_PULL
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
        x, y = self.v.pt(p)
        return (x - self.box.x) * self.ss, (y - self.box.y) * self.ss

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
FILL_ALPHA = 255  # solid panels: nothing behind ever shows through the text


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
        if len(_rr_cache) > 320:
            _rr_cache.clear()
        pad = _halo_px(glow) + math.ceil(edge) + 1
        bv = v.framed().scaled(v.ss())
        ow, oh = w + 2 * pad, h + 2 * pad
        body = bv.rect(pad, pad, w, h)
        r = bv.i(radius)
        plate = pg.Surface((bv.i(ow), bv.i(oh)), pg.SRCALPHA)
        if fill is not None:  # None: only the lit edge (a frame that glides over buttons)
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
        bv = v.framed().scaled(v.ss())
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
        bv = self.v.framed().scaled(SS_BALL)
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


# --- aiming: light line, ghost ball, arrow, and the neon cue ------------------------------
STICK_LEN = 250.0  # the neon cue (logical px)
STICK_TIP_W = 2.4  # half width at the tip ...
STICK_BUTT_W = 4.2  # ... and at the butt: a cue narrows to its tip
STICK_GAP = 3.0  # the tip rests this far behind the ball's ring when not pulled
LUNGE_S = 0.07  # after the shot the cue darts to the ball ...
FADE_S = 0.2  # ... and then goes out
CUE_FADE_IN_S = 0.18  # the pointer comes onto the cue ball: the cue fades in this fast ...
CUE_FADE_OUT_S = 0.25  # ... and out again when the pointer leaves
# the colour of the cue as the pull tightens: cold to hot (power 0 .. 1)
HEAT = (
    (0.0, C.CYAN),
    (0.35, C.VIOLET),
    (0.6, C.MAGENTA),
    (0.85, (255, 120, 40)),
    (1.0, (255, 236, 150)),
)


def power_color(power: float) -> tuple[int, int, int]:
    """The heat of the pull: cyan (gentle) through violet and pink to orange and white-hot."""
    p = min(1.0, max(0.0, power))
    for (p0, c0), (p1, c1) in zip(HEAT, HEAT[1:], strict=False):
        if p <= p1:
            return C.lerp(c0, c1, (p - p0) / (p1 - p0))
    return HEAT[-1][1]


def _object_center(contact) -> tuple[float, float]:
    """Centre of the ball that will be hit: contact point + 2R along object_dir."""
    dx, dy = contact.object_dir
    return contact.point[0] + dx * 2 * BALL_R, contact.point[1] + dy * 2 * BALL_R


def stick_outline(tip, u, length: float = STICK_LEN, grow: float = 0.0):
    """The cue as a quad from its tip (on the ball side) along unit u; `grow` widens it."""
    nx, ny = -u[1], u[0]
    t0 = (tip[0] - u[0] * grow, tip[1] - u[1] * grow)
    t1 = (tip[0] + u[0] * (length + grow), tip[1] + u[1] * (length + grow))
    w0, w1 = STICK_TIP_W + grow, STICK_BUTT_W + grow
    return [
        (t0[0] + nx * w0, t0[1] + ny * w0),
        (t1[0] + nx * w1, t1[1] + ny * w1),
        (t1[0] - nx * w1, t1[1] - ny * w1),
        (t0[0] - nx * w0, t0[1] - ny * w0),
    ]


def cue_tip(centre, shot_dir, pull: float, power: float = 0.0, clock: float = 0.0):
    """Where the tip of the cue is (logical px), and the unit vector from the tip to the butt.

    `pull` is how far the hand pulled; the cue shows CUE_SHOW_PULL of it (the power does not
    change, only how far the cue travels on screen)."""
    u = (-shot_dir[0], -shot_dir[1])  # the cue lies on the far side from where the ball goes
    nx, ny = -u[1], u[0]
    shake = math.sin(clock * 70.0) * 0.7 if power >= 0.999 else 0.0  # full power: it trembles
    d0 = RIM + STICK_GAP + pull * CUE_SHOW_PULL  # the cue moves less than the hand
    return (centre[0] + u[0] * d0 + nx * shake, centre[1] + u[1] * d0 + ny * shake), u


def draw_cue(
    canvas: pg.Surface,
    v: View,
    centre: tuple[float, float],
    shot_dir: tuple[float, float],
    pull: float,
    power: float,
    clock: float,
    alpha: float = 1.0,
) -> None:
    """The neon cue behind the ball at `centre` (logical px), pulled back with the hand; the
    harder the pull, the hotter its colour. `alpha` fades it in, and out after a shot."""
    tip, u = cue_tip(centre, shot_dir, pull, power, clock)
    butt = (tip[0] + u[0] * STICK_LEN, tip[1] + u[1] * STICK_LEN)
    layer = Aa(canvas, v, box_around(v, [tip, butt], 14), ss=2)
    surf, look = layer.surf, C.LOOK
    colour = power_color(power)
    a = max(0.0, min(1.0, alpha))

    def rgba(c, k: float) -> tuple[int, int, int, int]:
        return (*c, max(0, min(255, round(255 * k * a))))

    def quad(*args, **kw):
        return [layer.pt(p) for p in stick_outline(*args, **kw)]

    # a neon tube: a soft halo (stronger as it heats up), a body lit from inside, a bright core
    heat = 0.8 + 0.6 * power
    for grow, k in ((6.0, 0.05), (4.2, 0.07), (2.6, 0.1), (1.3, 0.16)):  # soft, in steps
        glow_k = k * look.glow * heat
        pg.draw.polygon(surf, rgba(colour, glow_k), quad(tip, u, grow=grow * look.reach))
    pg.draw.polygon(surf, rgba(C.lerp(C.PANEL, colour, 0.45), 1.0), quad(tip, u))
    core = C.lerp(colour, C.WHITE, 0.55)
    pg.draw.line(surf, rgba(core, 1.0), layer.pt(tip), layer.pt(butt), max(1, round(layer.n(1.4))))
    back = (tip[0] + u[0] * (STICK_LEN - 46), tip[1] + u[1] * (STICK_LEN - 46))
    pg.draw.polygon(surf, rgba(C.lerp(colour, C.PANEL, 0.25), 1.0), quad(back, u, 46))  # the butt
    pg.draw.polygon(surf, rgba(C.WHITE, 1.0), quad(tip, u, 8.0))  # the white tip
    layer.done()


def draw_aim(canvas: pg.Surface, v: View, cue, contact, shot_dir) -> None:
    """Light line from the cue ball to the first contact, a ghost ball there and an arrow on a hit
    ball: one supersampled layer."""
    look = C.LOOK
    centre = to_px(cue.x, cue.y)
    end = to_px(*contact.point)
    pts = [centre, end]
    obj = None
    if contact.kind == "ball" and contact.object_dir is not None:
        ox, oy = to_px(*_object_center(contact))
        dx, dy = contact.object_dir
        obj = (ox + dx * (RIM + 3), oy + dy * (RIM + 3), dx, dy)
        pts.append((obj[0] + dx * 40, obj[1] + dy * 40))
    layer = Aa(canvas, v, box_around(v, pts, 26), ss=2)
    surf = layer.surf

    ax, ay = end[0] - centre[0], end[1] - centre[1]
    alen = math.hypot(ax, ay)
    if alen > RIM:
        a = layer.pt((centre[0] + ax / alen * RIM, centre[1] + ay / alen * RIM))
        b = layer.pt(end)
        lines = (
            (11 * look.reach, (*C.AIM_GLOW, _alpha(36))),
            (6 * look.reach, (*C.AIM_GLOW, _alpha(85))),
            (2.2 * look.line, (*C.AIM, 255)),
        )
        for width, color in lines:
            pg.draw.line(surf, color, a, b, max(1, round(layer.n(width))))
            pg.draw.circle(surf, color, a, layer.n(width / 2))
            pg.draw.circle(surf, color, b, layer.n(width / 2))
    pg.draw.circle(
        surf, C.AIM, layer.pt(end), layer.n(BALL_PX), max(1, round(layer.n(2.0 * look.line)))
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
    layer.done()


def _alpha(base: float) -> int:
    return min(255, round(base * C.LOOK.glow))


__all__ = [
    "Aa",
    "BallSprites",
    "blit_add",
    "blit_dot",
    "blit_pm",
    "blit_rrect",
    "build_table",
    "draw_aim",
    "draw_cue",
    "draw_balls",
    "draw_ring",
    "power_color",
    "rrect_sprite",
    "shrink_pm",
]
