"""Subtle effects: impact ripples, pocket shrink, screen shake. Time-driven, no randomness."""

from __future__ import annotations

import math
from dataclasses import dataclass

import pygame as pg

from game.config import (
    MAX_RIPPLES,
    POCKET_ANIM_S,
    POCKETS,
    RIPPLE_S,
    SHAKE_PX,
    SHAKE_S,
)
from game.render.draw import Aa, BallSprites, blit_pm
from game.render.layout import BALL_PX, to_px
from game.render.view import View


@dataclass
class _Ripple:
    x: float  # metres
    y: float
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

    def add_ripple(self, x: float, y: float) -> None:
        self.ripples.append(_Ripple(x, y))
        del self.ripples[:-MAX_RIPPLES]

    def add_drop(self, number: int, x: float, y: float, pocket: int) -> None:
        self.drops.append(_Drop(number, x, y, pocket))

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
        self.ripples = [r for r in self.ripples if r.age < RIPPLE_S]
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
            t = r.age / RIPPLE_S
            radius = BALL_PX * (0.9 + 1.6 * (1 - (1 - t) ** 2))
            c = to_px(r.x, r.y)
            layer = Aa(
                canvas,
                v,
                v.rect(c[0] - radius - 4, c[1] - radius - 4, 2 * radius + 8, 2 * radius + 8),
                ss=3,
            )
            pg.draw.circle(
                layer.surf,
                (255, 255, 255, round(190 * (1 - t))),
                layer.pt(c),
                layer.n(radius),
                max(1, round(layer.n(2))),
            )
            layer.done()
