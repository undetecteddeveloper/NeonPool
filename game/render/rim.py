"""Two slow lights that run round the outer rim of the table: one cyan, one pink-violet.

Time-driven (the clock is the scene's own, so a photo of the scene is repeatable). The lights are
drawn as short lit segments on a black layer that is ADDED to the canvas: pure light, no outline.
"""

from __future__ import annotations

import math

import pygame as pg

from game.render import palette as C
from game.render.layout import OUTER_H, OUTER_W, OUTER_X, OUTER_Y
from game.render.table import FRAME_R
from game.render.view import View

SPEED = 110.0  # logical px per second along the rim: a lap takes about 27 s
STEP = 3.0  # distance between the points of the path (logical px)
COMET = 66  # points in one light's tail (about 200 px)
PAD = 10  # room round the table for the halo (logical px)
# (head colour, tail colour) of the two lights, half a lap apart
LIGHTS = (((214, 255, 255), C.CYAN, C.VIOLET), ((255, 214, 246), C.MAGENTA, C.VIOLET))


def _sample(a: tuple[float, float], b: tuple[float, float]) -> list[tuple[float, float]]:
    n = max(1, round(math.dist(a, b) / STEP))
    return [(a[0] + (b[0] - a[0]) * i / n, a[1] + (b[1] - a[1]) * i / n) for i in range(n)]


def _arc(cx: float, cy: float, r: float, a0: float, a1: float) -> list[tuple[float, float]]:
    n = max(2, round(r * math.radians(a1 - a0) / STEP))
    return [
        (
            cx + r * math.cos(math.radians(a0 + (a1 - a0) * i / n)),
            cy + r * math.sin(math.radians(a0 + (a1 - a0) * i / n)),
        )
        for i in range(n)
    ]


def rim_path() -> list[tuple[float, float]]:
    """The rim as a closed path, clockwise from the top-left corner, points STEP apart."""
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
    ]


def _palette() -> list[list[tuple[int, int, int, int]]]:
    """Per light: the (width px at 1x, r, g, b) of every segment of every pass, tail to head.

    The colours depend only on where a segment sits in the tail, so they are made once."""
    look = C.LOOK
    out = []
    for head_c, mid_c, tail_c in LIGHTS:
        passes = []
        for width, level in ((7.0 * look.reach, 0.22), (3.6, 0.5), (1.8 * look.line, 1.0)):
            for j in range(COMET - 1, -1, -1):
                f = 1.0 - j / COMET
                colour = C.lerp(C.lerp(tail_c, mid_c, min(1.0, f * 1.8)), head_c, f**7)
                k_lit = level * f**1.6 * min(1.0, 0.55 + 0.45 * look.glow)
                passes.append((j, width, *(round(c * k_lit) for c in colour)))
        out.append(passes)
    return out


class RimRunner:
    def __init__(self, v: View) -> None:
        self.v = v
        self.path = rim_path()
        self.box = v.rect(OUTER_X - PAD, OUTER_Y - PAD, OUTER_W + 2 * PAD, OUTER_H + 2 * PAD)
        self.layer = pg.Surface(self.box.size)
        self.layer.fill((0, 0, 0))
        self._drawn: list[pg.Rect] = []  # where the lights were last frame: only that is cleared
        self._lines = [
            [(j, max(1, v.i(w)), (r, g, b)) for j, w, r, g, b in passes] for passes in _palette()
        ]

    def _dev(self, p: tuple[float, float]) -> tuple[float, float]:
        x, y = self.v.pt(p)
        return x - self.box.x, y - self.box.y

    def draw(self, canvas: pg.Surface, t: float) -> None:
        n_path = len(self.path)
        for rect in self._drawn:
            self.layer.fill((0, 0, 0), rect)
        self._drawn = []
        reach = self.v.i(7.0 * C.LOOK.reach) + 2
        bounds = self.layer.get_rect()
        for k, lines in enumerate(self._lines):
            head = (t * SPEED / STEP + k * n_path / 2) % n_path
            pts = [self._dev(self.path[int(head - j) % n_path]) for j in range(COMET + 1)]
            for j, width, rgb in lines:  # tail first within a pass, so the head is drawn on top
                pg.draw.line(self.layer, rgb, pts[j + 1], pts[j], width)
            xs, ys = [p[0] for p in pts], [p[1] for p in pts]
            rect = pg.Rect(
                round(min(xs)) - reach,
                round(min(ys)) - reach,
                round(max(xs) - min(xs)) + 2 * reach,
                round(max(ys) - min(ys)) + 2 * reach,
            ).clip(bounds)
            at = (self.box.x + rect.x, self.box.y + rect.y)
            canvas.blit(self.layer, at, area=rect, special_flags=pg.BLEND_RGB_ADD)
            self._drawn.append(rect)
