"""Light effects: rings of light where balls hit, the wave over the whole table when a ball drops,
the shrinking ball, screen shake. Time-driven, no randomness: the same time gives the same picture.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import pygame as pg

from game.config import (
    BALL_RIPPLE_PX,
    MAX_RIPPLES,
    POCKET_ANIM_S,
    POCKETS,
    RIPPLE_S,
    SHAKE_PX,
    SHAKE_S,
    TABLE_WAVE_BAND,
    TABLE_WAVE_S,
    TABLE_WAVE_SPEED,
)
from game.render import palette as C
from game.render.draw import Aa, BallSprites, blit_pm
from game.render.layout import BALL_PX, OUTER_H, OUTER_W, OUTER_X, OUTER_Y, to_px
from game.render.table import neon_paths
from game.render.view import View

# kind -> (colour, how far it spreads (logical px), how long it lasts (s), rings in the train)
KINDS: dict[str, tuple[tuple[int, int, int], float, float, int]] = {
    "ball": (C.CYAN, BALL_RIPPLE_PX, RIPPLE_S, 2),  # two balls met
    "cushion": ((150, 120, 255), BALL_RIPPLE_PX * 0.8, RIPPLE_S, 2),  # a ball met the cushion
}
RING_LAG = 0.16  # each ring of a train starts this much (of the whole time) after the one before


def ball_colour(number: int) -> tuple[int, int, int]:
    """The light of a ball (a stripe shines in the colour of its band)."""
    return C.BALL_COLORS[number if number <= 8 else number - 8]


@dataclass
class _Ripple:
    x: float  # metres
    y: float
    kind: str
    age: float = 0.0


@dataclass
class _Drop:
    number: int
    x: float
    y: float
    pocket: int
    age: float = 0.0


@dataclass
class _Wave:
    """A ball fell in: a ring in its colour spreads from the pocket over the whole table."""

    pocket: int
    colour: tuple[int, int, int]
    age: float = 0.0

    def radius(self) -> float:
        return TABLE_WAVE_SPEED * self.age  # logical px

    def fade(self) -> float:
        return max(0.0, 1.0 - self.age / TABLE_WAVE_S) ** 1.2


class Fx:
    def __init__(self) -> None:
        self.ripples: list[_Ripple] = []
        self.drops: list[_Drop] = []
        self.waves: list[_Wave] = []
        self._shake_age = SHAKE_S  # >= SHAKE_S means idle
        self._shake_k = 1.0
        self._layer: pg.Surface | None = None  # the light of the waves, over the table
        self._layer_key: tuple | None = None
        self._paths: list[np.ndarray] = []  # the table's neon lines, device px in the layer

    def add_ripple(self, x: float, y: float, kind: str = "ball") -> None:
        self.ripples.append(_Ripple(x, y, kind))
        del self.ripples[:-MAX_RIPPLES]

    def add_drop(self, number: int, x: float, y: float, pocket: int) -> None:
        self.drops.append(_Drop(number, x, y, pocket))
        self.waves.append(_Wave(pocket, ball_colour(number)))

    def shake(self, strength: float = 1.0) -> None:
        """Shake the screen; a stronger hit while shaking keeps the stronger shake."""
        if self._shake_age < SHAKE_S and self._shake_k >= strength:
            return
        self._shake_age, self._shake_k = 0.0, min(1.5, max(0.2, strength))

    def clear(self) -> None:
        self.ripples.clear()
        self.drops.clear()
        self.waves.clear()
        self._shake_age = SHAKE_S

    def update(self, dt: float) -> None:
        for r in self.ripples:
            r.age += dt
        for d in self.drops:
            d.age += dt
        for w in self.waves:
            w.age += dt
        self.ripples = [r for r in self.ripples if r.age < KINDS[r.kind][2]]
        self.drops = [d for d in self.drops if d.age < POCKET_ANIM_S]
        self.waves = [w for w in self.waves if w.age < TABLE_WAVE_S]
        self._shake_age = min(SHAKE_S, self._shake_age + dt)

    def shake_offset(self) -> tuple[float, float]:
        """Logical-pixel offset for the whole canvas; (0, 0) when idle."""
        if self._shake_age >= SHAKE_S:
            return 0.0, 0.0
        k = (1.0 - self._shake_age / SHAKE_S) ** 2 * SHAKE_PX * self._shake_k
        return math.sin(self._shake_age * 90) * k, math.cos(self._shake_age * 110) * k

    def draw(self, canvas: pg.Surface, v: View, sprites: BallSprites) -> None:
        if self.waves:
            self._draw_waves(canvas, v)
        for d in self.drops:
            t = d.age / POCKET_ANIM_S
            px, py, _ = POCKETS[d.pocket]
            x, y = v.pt(to_px(d.x + (px - d.x) * t, d.y + (py - d.y) * t))
            size = max(2, round(sprites.size * (1.0 - t * t)))
            sprite = pg.transform.smoothscale(sprites.get(d.number), (size, size))
            blit_pm(canvas, sprite, (x - size / 2, y - size / 2))
        for r in self.ripples:
            self._draw_ripple(canvas, v, r)

    # --- the wave over the table -------------------------------------------------------------
    def _prepare(self, v: View) -> pg.Rect:
        box = v.rect(OUTER_X - 8, OUTER_Y - 8, OUTER_W + 16, OUTER_H + 16)
        key = (round(v.s, 4), box.topleft, box.size)
        if key != self._layer_key:
            self._layer = pg.Surface(box.size)
            self._layer_key = key
            self._paths = [
                np.array([v.pt(p) for p in path]) - np.array(box.topleft) for path in neon_paths()
            ]
        return box

    def _draw_waves(self, canvas: pg.Surface, v: View) -> None:
        """Each wave: a ring of the ball's colour spreading over the table, and the table's own
        lines flaring up where the ring passes them. Pure light, added on top."""
        box = self._prepare(v)
        layer = self._layer
        layer.fill((0, 0, 0))
        band = v.n(TABLE_WAVE_BAND)
        for w in self.waves:
            fade = w.fade()
            if fade <= 0.01:
                continue
            px, py, _ = POCKETS[w.pocket]
            cx, cy = v.pt(to_px(px, py))
            c = (cx - box.x, cy - box.y)
            r = v.n(w.radius())
            for width, k in ((band * 1.4, 0.12), (band * 0.55, 0.3), (max(1.5, v.n(2.0)), 0.9)):
                if r > width / 2:
                    pg.draw.circle(layer, C.scale(w.colour, k * fade), c, r, max(1, round(width)))
            for path in self._paths:  # the lines of the table light up where the ring passes
                d = np.hypot(path[:, 0] - c[0], path[:, 1] - c[1])
                near = np.abs(d - r) < band
                if not near.any():
                    continue
                edges = np.flatnonzero(np.diff(np.concatenate(([0], near.astype(int), [0]))))
                for a, b in zip(edges[::2], edges[1::2], strict=True):
                    if b - a < 2:
                        continue
                    seg = path[a:b].tolist()
                    pg.draw.lines(layer, C.scale(w.colour, 0.35 * fade), False, seg, round(v.n(7)))
                    lit = C.lerp(w.colour, C.WHITE, 0.6)
                    pg.draw.lines(layer, C.scale(lit, fade), False, seg, max(1, round(v.n(2.4))))
        canvas.blit(layer, box.topleft, special_flags=pg.BLEND_RGB_ADD)

    @staticmethod
    def _draw_ripple(canvas: pg.Surface, v: View, r: _Ripple) -> None:
        """A train of rings of light spreading from a point: bright thin core, soft wide halo."""
        look = C.LOOK
        colour, reach, seconds, rings = KINDS[r.kind]
        start = BALL_PX * 0.9
        c = to_px(r.x, r.y)
        far = start + reach
        layer = Aa(
            canvas, v, v.rect(c[0] - far - 8, c[1] - far - 8, 2 * far + 16, 2 * far + 16), ss=3
        )
        for k in range(rings):
            t = r.age / seconds - k * RING_LAG
            if not 0.0 < t < 1.0:
                continue
            radius = start + reach * (1 - (1 - t) ** 2)
            fade = (1 - t) ** 1.3
            centre, n = layer.pt(c), layer.n
            pg.draw.circle(
                layer.surf,
                (*colour, min(255, round(70 * fade * look.glow))),
                centre,
                n(radius),
                max(1, round(n(7 * look.reach))),
            )
            pg.draw.circle(
                layer.surf,
                (*colour, round(235 * fade)),
                centre,
                n(radius),
                max(1, round(n(2.0 * look.line))),
            )
        layer.done()
