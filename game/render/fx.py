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
from game.render.draw import BallSprites
from game.render.layout import BALL_PX, to_px


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

    def draw(self, canvas: pg.Surface, sprites: BallSprites) -> None:
        for d in self.drops:
            t = d.age / POCKET_ANIM_S
            px, py, _ = POCKETS[d.pocket]
            x, y = to_px(d.x + (px - d.x) * t, d.y + (py - d.y) * t)
            size = max(2, round(sprites.size * (1.0 - t * t)))
            sprite = pg.transform.smoothscale(sprites.get(d.number), (size, size))
            canvas.blit(sprite, (round(x - size / 2), round(y - size / 2)))
        for r in self.ripples:
            t = r.age / RIPPLE_S
            radius = BALL_PX * (0.9 + 1.6 * (1 - (1 - t) ** 2))
            size = math.ceil(radius * 2 + 6)
            layer = pg.Surface((size, size), pg.SRCALPHA)
            pg.draw.circle(
                layer, (255, 255, 255, round(190 * (1 - t))), (size / 2, size / 2), radius, 2
            )
            cx, cy = to_px(r.x, r.y)
            canvas.blit(layer, (round(cx - size / 2), round(cy - size / 2)))
