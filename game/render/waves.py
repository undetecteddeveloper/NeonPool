"""Slow ribbons of light that travel across the menu and the how-to-play screen.

A ribbon is a few sine strands a little out of step with each other, so it looks like a twisting
band of light. It is painted ONCE (a tile that is a whole number of wavelengths wide, with its
halo) and then only scrolled and added to the canvas: a travelling wave for the price of a blit.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import pygame as pg

from game.config import LOGICAL_SIZE
from game.render import palette as C
from game.render.draw import blit_add
from game.render.glow import lit
from game.render.view import View

SS = 2  # the tile is painted at 2x and shrunk (smooth lines)
POINT_PX = 5  # distance between the points of a strand (device px at 1x)


@dataclass(frozen=True)
class Ribbon:
    y: float  # logical y of the centre line
    wavelength: float  # logical px
    amplitude: float  # logical px
    strands: int
    twist: float  # phase step between neighbouring strands (radians)
    colors: tuple[tuple[int, int, int], tuple[int, int, int]]  # first strand -> last strand
    speed: float  # logical px per second; negative runs to the left


MENU = (
    Ribbon(285, 720, 30, 6, 0.46, (C.CYAN, C.VIOLET), 22),
    Ribbon(470, 520, 34, 5, 0.60, (C.VIOLET, C.MAGENTA), -30),
    Ribbon(652, 900, 22, 6, 0.40, (C.CYAN, C.MAGENTA), 14),
)
HELP = (
    Ribbon(76, 640, 9, 5, 0.45, (C.CYAN, C.VIOLET), 18),
    Ribbon(690, 760, 14, 5, 0.45, (C.VIOLET, C.MAGENTA), -22),
)


class Waves:
    """The ribbons of one screen, baked for one view. `strength` dims them (help: 0.5)."""

    def __init__(self, v: View, ribbons: tuple[Ribbon, ...], strength: float = 0.8) -> None:
        self.v = v
        self.ribbons = ribbons
        self._tiles = [self._bake(r, strength) for r in ribbons]

    def _bake(self, r: Ribbon, strength: float) -> tuple[pg.Surface, int, int]:
        """(tile, period in device px, top of the tile in device px)."""
        v, look = self.v, C.LOOK
        period = max(16, round(v.n(r.wavelength)))
        reps = math.ceil(LOGICAL_SIZE[0] * v.s / period) + 1
        pad = 16  # logical px for the halo above and below
        half = r.amplitude * 1.35 + pad
        w, h = period * reps, v.i(2 * half)
        big = pg.Surface((w * SS, h * SS), pg.SRCALPHA)
        step = POINT_PX * SS
        for i in range(r.strands):
            u = i / max(1, r.strands - 1)
            colour = C.lerp(r.colors[0], r.colors[1], u)
            ys = []
            for x in range(0, w * SS + step, step):
                th = 2 * math.pi * x / (period * SS)
                y = math.sin(th + i * r.twist) + 0.3 * math.sin(2 * th + 1.7 * i * r.twist)
                ys.append((x, h * SS / 2 + y * v.n(r.amplitude) * SS))
            width = max(1, round(v.n(1.3 * look.line) * SS))
            alpha = round(255 * strength * (0.55 + 0.45 * math.sin(math.pi * (0.15 + 0.7 * u))))
            pg.draw.lines(big, (*colour, alpha), False, ys, width)
        core = big.premul_alpha()
        tile = pg.transform.smoothscale(
            lit(core, v.n(8 * look.reach) * SS * 0.55, 1.2 * look.glow), (w, h)
        )
        return tile, period, v.i(r.y - half)

    def draw(self, canvas: pg.Surface, t: float) -> None:
        for r, (tile, period, top) in zip(self.ribbons, self._tiles, strict=True):
            x = int((t * r.speed * self.v.s) % period) - period
            blit_add(canvas, tile, (x, top))
