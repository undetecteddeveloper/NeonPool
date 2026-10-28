"""Drawing helpers at device resolution: table, balls, aim, pull bar, power bar, grid.

Smooth edges: shapes with transparency are painted on a bigger surface, converted to
premultiplied alpha, shrunk with smoothscale and blitted with BLEND_PREMULTIPLIED (plain
smoothscale on straight alpha leaves dark fringes). Opaque layers are just shrunk.
"""

from __future__ import annotations

import math

import pygame as pg

from game.config import (
    BALL_R,
    POCKETS,
    PX_PER_M,
    TABLE_L,
    TABLE_W,
)
from game.render import fonts
from game.render import palette as C
from game.render.layout import (
    BALL_PX,
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

OUT_PX = 2.4  # thick cartoon outline of a ball (logical px)
SS_BALL = 4  # sprites are painted at 4x
RIM = BALL_PX + OUT_PX


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

    def done(self) -> None:
        if self.box.w > 0 and self.box.h > 0:
            blit_pm(self.canvas, shrink_pm(self.surf, self.box.size), self.box.topleft)


def box_around(v: View, points: list[tuple[float, float]], pad: float) -> pg.Rect:
    xs, ys = [p[0] for p in points], [p[1] for p in points]
    return v.rect(
        min(xs) - pad, min(ys) - pad, max(xs) - min(xs) + 2 * pad, max(ys) - min(ys) + 2 * pad
    )


_rr_cache: dict[tuple, pg.Surface] = {}


def rrect_sprite(v: View, w: float, h: float, radius: float, fill, edge: float) -> pg.Surface:
    """Outlined rounded rectangle (logical w x h inside an `edge` black border), premultiplied."""
    key = (round(v.s, 4), w, h, radius, fill, edge)
    if key not in _rr_cache:
        if len(_rr_cache) > 96:
            _rr_cache.clear()
        bv = v.scaled(v.ss())
        ow, oh = w + 2 * edge, h + 2 * edge
        big = pg.Surface((bv.i(ow), bv.i(oh)), pg.SRCALPHA)
        pg.draw.rect(big, C.OUTLINE, big.get_rect(), border_radius=bv.i(radius + edge))
        pg.draw.rect(big, fill, bv.rect(edge, edge, w, h), border_radius=bv.i(radius))
        _rr_cache[key] = shrink_pm(big, (v.i(ow), v.i(oh)))
    return _rr_cache[key]


def blit_rrect(
    canvas: pg.Surface, v: View, x: float, y: float, w: float, h: float, radius: float, fill, edge=5
) -> None:
    blit_pm(canvas, rrect_sprite(v, w, h, radius, fill, edge), v.pt((x - edge, y - edge)))


# --- static table ----------------------------------------------------------------------
def _paint_table(s: pg.Surface, v: View) -> None:
    s.fill(C.BG)
    pg.draw.rect(
        s,
        C.OUTLINE,
        v.rect(OUTER_X - 5, OUTER_Y - 5, OUTER_W + 10, OUTER_H + 10),
        border_radius=v.i(24),
    )
    pg.draw.rect(s, C.RAIL, v.rect(OUTER_X, OUTER_Y, OUTER_W, OUTER_H), border_radius=v.i(18))
    pg.draw.rect(
        s,
        C.OUTLINE,
        v.rect(FIELD_X - 5, FIELD_Y - 5, FIELD_W + 10, FIELD_H + 10),
        border_radius=v.i(4),
    )
    sq = FIELD_W / 20
    s.set_clip(v.rect(FIELD_X, FIELD_Y, FIELD_W, FIELD_H))
    for iy in range(math.ceil(FIELD_H / sq)):
        for ix in range(20):
            color = C.CLOTH_A if (ix + iy) % 2 == 0 else C.CLOTH_B
            s.fill(color, v.rect(FIELD_X + ix * sq, FIELD_Y + iy * sq, sq, sq))
    s.set_clip(None)
    for px, py, pr in POCKETS:
        pg.draw.circle(s, C.POCKET, v.pt(to_px(px, py)), v.n(pr * PX_PER_M))


def build_table(v: View) -> pg.Surface:
    """Background + rails + checkered cloth + pockets: painted at 3x, shrunk once (smooth edges)."""
    k = v.ss()
    big = pg.Surface(v.scaled(k).size)
    _paint_table(big, v.scaled(k))
    return pg.transform.smoothscale(big, v.size)


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
            blit_pm(canvas, sprites.shadow, (x - half + v.n(2), y - half + v.n(3)))
    for b in balls:
        if b.in_play:
            x, y = v.pt(to_px(b.x, b.y))
            blit_pm(canvas, sprites.get(b.number), (x - half, y - half))


# --- aiming: glow line, ghost ball, arrow, pull bar ------------------------------------
def power_color(power: float) -> tuple[int, int, int]:
    """Yellow -> orange as the shot gets harder."""
    return 250, round(232 - 118 * power), round(60 - 20 * power)


def _object_center(contact) -> tuple[float, float]:
    """Centre of the ball that will be hit: contact point + 2R along object_dir."""
    dx, dy = contact.object_dir
    return contact.point[0] + dx * 2 * BALL_R, contact.point[1] + dy * 2 * BALL_R


def _bar_polygon(p0, d, length: float, w0: float, w1: float):
    """Tapered bar from p0 along unit d: half-width w0 at p0 growing to w1 at the far end."""
    nx, ny = -d[1], d[0]
    p1 = (p0[0] + d[0] * length, p0[1] + d[1] * length)
    return [
        (p0[0] + nx * w0, p0[1] + ny * w0),
        (p1[0] + nx * w1, p1[1] + ny * w1),
        (p1[0] - nx * w1, p1[1] - ny * w1),
        (p0[0] - nx * w0, p0[1] - ny * w0),
    ], p1


def draw_aim(
    canvas: pg.Surface, v: View, cue, contact, shot_dir, bar_len: float, power: float
) -> None:
    """Pull bar behind the cue ball (`bar_len` logical px, already capped by DragAim), glow line
    to the first contact, ghost ball there and an arrow on a hit ball: one supersampled layer.
    """
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

    # pull bar: black outline, power-coloured fill, round butt
    if bar_len > 6:
        poly, tip = _bar_polygon(
            layer.pt(bar0), (ux, uy), layer.n(bar_len), layer.n(2.4), layer.n(5.5)
        )
        outline, _ = _bar_polygon(
            layer.pt((bar0[0] - ux * 2.4, bar0[1] - uy * 2.4)),
            (ux, uy),
            layer.n(bar_len + 4.8),
            layer.n(2.4 + 2.4),
            layer.n(5.5 + 2.4),
        )
        pg.draw.polygon(surf, C.OUTLINE, outline)
        pg.draw.circle(surf, C.OUTLINE, tip, layer.n(5.5 + 2.4))
        pg.draw.polygon(surf, power_color(power), poly)
        pg.draw.circle(surf, power_color(power), tip, layer.n(5.5))

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
    layer.done()


# --- coordinate grid -------------------------------------------------------------------
def build_grid(v: View) -> pg.Surface:
    """Grid over the canvas, origin at the table centre, x right, y UP (maths), metres.

    Hairlines sit on whole device pixels; labels use fonts sized for this view (always crisp).
    """
    layer = pg.Surface(v.size, pg.SRCALPHA)
    cx, cy = TABLE_L / 2, TABLE_W / 2
    field = v.rect(FIELD_X, FIELD_Y, FIELD_W, FIELD_H)
    font = fonts.get(max(8, v.i(12)))

    def label(s: str, pos: tuple[float, float]) -> None:
        surf = font.render(s, True, (255, 255, 255))
        surf.set_alpha(170)
        layer.blit(surf, (round(pos[0]), round(pos[1])))

    for k in range(-13, 14):
        x = cx + k * 0.1
        if not 0.0 <= x <= TABLE_L:
            continue
        px = round(v.pt(to_px(x, 0.0))[0])
        major = k % 5 == 0
        alpha = 150 if k == 0 else 62 if major else 26
        pg.draw.line(layer, (255, 255, 255, alpha), (px, field.top), (px, field.bottom), 1)
        if major and k != 0:
            label(f"{k * 0.1:g}", (px + v.n(3), v.pt(to_px(0.0, cy))[1] + v.n(2)))
    for k in range(-7, 8):
        y = cy - k * 0.1  # y up
        if not 0.0 <= y <= TABLE_W:
            continue
        py = round(v.pt(to_px(0.0, y))[1])
        major = k % 5 == 0
        alpha = 150 if k == 0 else 62 if major else 26
        pg.draw.line(layer, (255, 255, 255, alpha), (field.left, py), (field.right, py), 1)
        if major and k != 0:
            label(f"{k * 0.1:g}", (v.pt(to_px(cx, 0.0))[0] + v.n(4), py - v.n(14)))
    return layer


__all__ = [
    "Aa",
    "BallSprites",
    "blit_pm",
    "blit_rrect",
    "build_grid",
    "build_table",
    "draw_aim",
    "draw_balls",
    "power_color",
    "rrect_sprite",
    "shrink_pm",
]
