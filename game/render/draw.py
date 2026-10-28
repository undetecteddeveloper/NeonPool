"""Drawing helpers: static table, ball sprites, aim line, power bar, coordinate grid."""

from __future__ import annotations

import math

import pygame as pg

from game.config import BALL_R, LOGICAL_SIZE, POCKETS, PX_PER_M, TABLE_L, TABLE_W
from game.render import fonts
from game.render import palette as C
from game.render.layout import (
    BALL_PX,
    BAR_H,
    BAR_W,
    BAR_X,
    BAR_Y,
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

SS = 4  # sprites are drawn at 4x then scaled down: smooth edges without per-frame cost
OUT_PX = 2.4  # thick cartoon outline of a ball


def build_table() -> pg.Surface:
    """Window background + rails + checkered cloth + pockets, drawn once."""
    s = pg.Surface(LOGICAL_SIZE)
    s.fill(C.BG)
    outer = pg.Rect(OUTER_X, OUTER_Y, OUTER_W, OUTER_H)
    pg.draw.rect(s, C.OUTLINE, outer.inflate(10, 10), border_radius=24)
    pg.draw.rect(s, C.RAIL, outer, border_radius=18)

    field = pg.Rect(FIELD_X, FIELD_Y, FIELD_W, FIELD_H)
    pg.draw.rect(s, C.OUTLINE, field.inflate(10, 10), border_radius=4)
    s.set_clip(field)
    sq = FIELD_W / 20
    for iy in range(math.ceil(FIELD_H / sq)):
        for ix in range(20):
            color = C.CLOTH_A if (ix + iy) % 2 == 0 else C.CLOTH_B
            s.fill(
                color,
                (round(FIELD_X + ix * sq), round(FIELD_Y + iy * sq), math.ceil(sq), math.ceil(sq)),
            )
    s.set_clip(None)

    for px, py, pr in POCKETS:
        cx, cy = to_px(px, py)
        pg.draw.circle(s, C.POCKET, (cx, cy), pr * PX_PER_M)
    return s


class BallSprites:
    """Cached ball sprites (outlined, solid/stripe, numbered) plus one shared shadow."""

    def __init__(self) -> None:
        self._cache: dict[int, pg.Surface] = {}
        self.size = math.ceil(2 * (BALL_PX + OUT_PX)) + 2
        self.shadow = self._make_shadow()

    def get(self, number: int) -> pg.Surface:
        if number not in self._cache:
            self._cache[number] = self._make(number)
        return self._cache[number]

    def _make_shadow(self) -> pg.Surface:
        s = pg.Surface((self.size, self.size), pg.SRCALPHA)
        pg.draw.circle(s, (0, 0, 0, 58), (self.size / 2, self.size / 2), BALL_PX + OUT_PX)
        return s

    def _make(self, number: int) -> pg.Surface:
        r = BALL_PX
        big = self.size * SS
        c = big / 2
        surf = pg.Surface((big, big), pg.SRCALPHA)
        pg.draw.circle(surf, C.OUTLINE, (c, c), (r + OUT_PX) * SS)
        base = number if number <= 8 else number - 8
        pg.draw.circle(surf, C.BALL_COLORS[base], (c, c), r * SS)

        if number > 8:  # stripe: a white band across the middle, clipped to the ball
            band = pg.Surface((big, big), pg.SRCALPHA)
            pg.draw.rect(band, C.WHITE, (0, c - r * SS * 0.46, big, r * SS * 0.92))
            mask = pg.Surface((big, big), pg.SRCALPHA)
            pg.draw.circle(mask, (255, 255, 255, 255), (c, c), r * SS)
            band.blit(mask, (0, 0), special_flags=pg.BLEND_RGBA_MIN)
            surf.blit(band, (0, 0))

        if number != 0:  # white dot with the number
            pg.draw.circle(surf, C.OUTLINE, (c, c), r * SS * 0.56)
            pg.draw.circle(surf, C.WHITE, (c, c), r * SS * 0.50)
            font = fonts.get(int(r * SS * (1.0 if number < 10 else 0.8)), bold=True)
            text = font.render(str(number), True, C.OUTLINE)
            surf.blit(text, text.get_rect(center=(c, c)))

        return pg.transform.smoothscale(surf, (self.size, self.size))


def draw_balls(canvas: pg.Surface, balls, sprites: BallSprites) -> None:
    half = sprites.size / 2
    for b in balls:
        if b.in_play:
            x, y = to_px(b.x, b.y)
            canvas.blit(sprites.shadow, (round(x - half + 2), round(y - half + 3)))
    for b in balls:
        if b.in_play:
            x, y = to_px(b.x, b.y)
            canvas.blit(sprites.get(b.number), (round(x - half), round(y - half)))


def draw_glow_line(canvas: pg.Surface, a: tuple[float, float], b: tuple[float, float]) -> None:
    pad = 16
    x0, y0 = min(a[0], b[0]) - pad, min(a[1], b[1]) - pad
    w, h = abs(a[0] - b[0]) + 2 * pad, abs(a[1] - b[1]) + 2 * pad
    layer = pg.Surface((math.ceil(w), math.ceil(h)), pg.SRCALPHA)
    pa, pb = (a[0] - x0, a[1] - y0), (b[0] - x0, b[1] - y0)
    for width, color in ((13, (*C.AIM_GLOW, 46)), (8, (*C.AIM_GLOW, 96)), (3, (*C.AIM, 255))):
        pg.draw.line(layer, color, pa, pb, width)
        pg.draw.circle(layer, color, pa, width / 2)
        pg.draw.circle(layer, color, pb, width / 2)
    canvas.blit(layer, (x0, y0))


def draw_arrow(
    canvas: pg.Surface, start: tuple[float, float], d: tuple[float, float], length: float
) -> None:
    ex, ey = start[0] + d[0] * length, start[1] + d[1] * length
    nx, ny = -d[1], d[0]
    pg.draw.line(canvas, C.OUTLINE, start, (ex, ey), 9)
    pg.draw.line(canvas, C.ACCENT, start, (ex, ey), 4)
    head = [
        (ex + d[0] * 11, ey + d[1] * 11),
        (ex + nx * 8, ey + ny * 8),
        (ex - nx * 8, ey - ny * 8),
    ]
    pg.draw.polygon(canvas, C.ACCENT, head)
    pg.draw.polygon(canvas, C.OUTLINE, head, 3)


def draw_aim(canvas: pg.Surface, cue, contact, pointer_px: tuple[float, float]) -> None:
    """Glow line from the cue ball to its first contact, ghost ball there, arrow on a hit ball."""
    # Drawn AFTER the balls (else they hide the arrow), so every line starts at a ball's rim.
    rim = BALL_PX + OUT_PX
    centre = to_px(cue.x, cue.y)
    end = to_px(*contact.point)

    sx, sy = pointer_px[0] - centre[0], pointer_px[1] - centre[1]
    slen = math.hypot(sx, sy)
    if slen > rim:  # the pulled-back "string"
        string_start = (centre[0] + sx / slen * rim, centre[1] + sy / slen * rim)
        pg.draw.line(canvas, C.OUTLINE, string_start, pointer_px, 3)
        pg.draw.circle(canvas, C.OUTLINE, pointer_px, 5)

    ax, ay = end[0] - centre[0], end[1] - centre[1]
    alen = math.hypot(ax, ay)
    if alen > rim:
        line_start = (centre[0] + ax / alen * rim, centre[1] + ay / alen * rim)
        draw_glow_line(canvas, line_start, end)
    pg.draw.circle(canvas, C.AIM, end, BALL_PX, 3)  # ghost cue ball at the first contact

    if contact.kind == "ball" and contact.object_dir is not None:
        ox, oy = to_px(*_object_center(contact))
        dx, dy = contact.object_dir
        draw_arrow(canvas, (ox + dx * (rim + 3), oy + dy * (rim + 3)), contact.object_dir, 26)


def _object_center(contact) -> tuple[float, float]:
    """Centre of the ball that will be hit: contact point + 2R along object_dir."""
    dx, dy = contact.object_dir
    return contact.point[0] + dx * 2 * BALL_R, contact.point[1] + dy * 2 * BALL_R


def draw_power_bar(canvas: pg.Surface, power: float) -> None:
    outer = pg.Rect(BAR_X, BAR_Y, BAR_W, BAR_H)
    pg.draw.rect(canvas, C.OUTLINE, outer, border_radius=BAR_W // 2)
    inner = outer.inflate(-10, -10)
    pg.draw.rect(canvas, (40, 46, 62), inner, border_radius=inner.w // 2)
    if power > 0.0:
        h = max(inner.w, round(inner.h * power))
        color = (
            250,
            round(232 - 118 * power),
            round(60 - 20 * power),
        )  # yellow -> orange as the shot gets harder
        pg.draw.rect(
            canvas, color, (inner.x, inner.bottom - h, inner.w, h), border_radius=inner.w // 2
        )


def build_grid() -> pg.Surface:
    """Coordinate grid, origin at the table centre, x right, y UP (maths convention), in metres."""
    layer = pg.Surface(LOGICAL_SIZE, pg.SRCALPHA)
    cx, cy = TABLE_L / 2, TABLE_W / 2
    field = pg.Rect(FIELD_X, FIELD_Y, FIELD_W, FIELD_H)
    font = fonts.get(12)

    for k in range(-13, 14):
        x = cx + k * 0.1
        if not 0.0 <= x <= TABLE_L:
            continue
        px = to_px(x, 0.0)[0]
        major = k % 5 == 0
        alpha = 150 if k == 0 else 62 if major else 26
        pg.draw.line(layer, (255, 255, 255, alpha), (px, field.top), (px, field.bottom), 1)
        if major and k != 0:
            label = font.render(f"{k * 0.1:g}", True, (255, 255, 255, 170))
            layer.blit(label, (px + 3, to_px(0.0, cy)[1] + 2))
    for k in range(-7, 8):
        y = cy - k * 0.1  # y up
        if not 0.0 <= y <= TABLE_W:
            continue
        py = to_px(0.0, y)[1]
        major = k % 5 == 0
        alpha = 150 if k == 0 else 62 if major else 26
        pg.draw.line(layer, (255, 255, 255, alpha), (field.left, py), (field.right, py), 1)
        if major and k != 0:
            label = font.render(f"{k * 0.1:g}", True, (255, 255, 255, 170))
            layer.blit(label, (to_px(cx, 0.0)[0] + 4, py - 14))
    return layer
