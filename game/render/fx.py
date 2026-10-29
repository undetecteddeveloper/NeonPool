"""Light effects: rings of light where balls hit, a wave out of a pocket, the shrinking ball, screen
shake. Time-driven, no randomness: the same frame time gives the same picture."""

from __future__ import annotations

import math
from dataclasses import dataclass

import pygame as pg

from game.config import (
    BALL_RIPPLE_PX,
    MAX_RIPPLES,
    POCKET_ANIM_S,
    POCKET_WAVE_PX,
    POCKET_WAVE_S,
    POCKETS,
    PX_PER_M,
    RIPPLE_S,
    SHAKE_PX,
    SHAKE_S,
)
from game.render import palette as C
from game.render.draw import Aa, BallSprites, blit_pm
from game.render.layout import BALL_PX, to_px
from game.render.view import View

# kind -> (colour, how far it spreads (logical px), how long it lasts (s), rings in the train)
KINDS: dict[str, tuple[tuple[int, int, int], float, float, int]] = {
    "ball": (C.CYAN, BALL_RIPPLE_PX, RIPPLE_S, 2),  # two balls met
    "cushion": ((150, 120, 255), BALL_RIPPLE_PX * 0.8, RIPPLE_S, 2),  # a ball met the cushion
    "pocket": (C.MAGENTA, POCKET_WAVE_PX, POCKET_WAVE_S, 3),  # a ball fell in a pocket
}
RING_LAG = 0.16  # each ring of a train starts this much (of the whole time) after the one before


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


class Fx:
    def __init__(self) -> None:
        self.ripples: list[_Ripple] = []
        self.drops: list[_Drop] = []
        self._shake_age = SHAKE_S  # >= SHAKE_S means idle

    def add_ripple(self, x: float, y: float, kind: str = "ball") -> None:
        self.ripples.append(_Ripple(x, y, kind))
        del self.ripples[:-MAX_RIPPLES]

    def add_drop(self, number: int, x: float, y: float, pocket: int) -> None:
        self.drops.append(_Drop(number, x, y, pocket))
        px, py, _ = POCKETS[pocket]
        self.add_ripple(px, py, "pocket")

    def shake(self) -> None:
        self._shake_age = 0.0

    def clear(self) -> None:
        self.ripples.clear()
        self.drops.clear()
        self._shake_age = SHAKE_S

    def update(self, dt: float) -> None:
        for r in self.ripples:
            r.age += dt
        for d in self.drops:
            d.age += dt
        self.ripples = [r for r in self.ripples if r.age < KINDS[r.kind][2]]
        self.drops = [d for d in self.drops if d.age < POCKET_ANIM_S]
        self._shake_age = min(SHAKE_S, self._shake_age + dt)

    def shake_offset(self) -> tuple[float, float]:
        """Logical-pixel offset for the whole canvas; (0, 0) when idle."""
        if self._shake_age >= SHAKE_S:
            return 0.0, 0.0
        k = (1.0 - self._shake_age / SHAKE_S) ** 2 * SHAKE_PX
        return math.sin(self._shake_age * 90) * k, math.cos(self._shake_age * 110) * k

    def draw(self, canvas: pg.Surface, v: View, sprites: BallSprites) -> None:
        for d in self.drops:
            t = d.age / POCKET_ANIM_S
            px, py, _ = POCKETS[d.pocket]
            x, y = v.pt(to_px(d.x + (px - d.x) * t, d.y + (py - d.y) * t))
            size = max(2, round(sprites.size * (1.0 - t * t)))
            sprite = pg.transform.smoothscale(sprites.get(d.number), (size, size))
            blit_pm(canvas, sprite, (x - size / 2, y - size / 2))
        for r in self.ripples:
            self._draw_ripple(canvas, v, r)

    @staticmethod
    def _draw_ripple(canvas: pg.Surface, v: View, r: _Ripple) -> None:
        """A train of rings of light spreading from a point: bright thin core, soft wide halo."""
        look = C.LOOK
        colour, reach, seconds, rings = KINDS[r.kind]
        start = BALL_PX * 0.9 if r.kind != "pocket" else 0.0
        if r.kind == "pocket":
            start = max(p[2] for p in POCKETS) * PX_PER_M * 0.6
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
