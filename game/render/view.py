"""View: logical canvas units -> device pixels. Everything is drawn at the real window resolution.

Layout and game code stay in logical units (1280x720); only drawing multiplies by `s`.
Smooth shapes are drawn on a bigger surface (`scaled(k)`) and shrunk: supersampling.
"""

from __future__ import annotations

from dataclasses import dataclass

import pygame as pg

from game.config import LOGICAL_SIZE
from game.render.viewport import fit


@dataclass(frozen=True)
class View:
    s: float  # device pixels per logical unit

    def n(self, v: float) -> float:
        return v * self.s

    def i(self, v: float) -> int:
        return round(v * self.s)

    def pt(self, p: tuple[float, float]) -> tuple[float, float]:
        return p[0] * self.s, p[1] * self.s

    def ipt(self, p: tuple[float, float]) -> tuple[int, int]:
        return round(p[0] * self.s), round(p[1] * self.s)

    def rect(self, x: float, y: float, w: float, h: float) -> pg.Rect:
        """Rounded per edge (not per size), so neighbouring rects leave no gap."""
        x0, y0 = round(x * self.s), round(y * self.s)
        return pg.Rect(x0, y0, round((x + w) * self.s) - x0, round((y + h) * self.s) - y0)

    def scaled(self, k: float) -> View:
        return View(self.s * k)

    @property
    def size(self) -> tuple[int, int]:
        return round(LOGICAL_SIZE[0] * self.s), round(LOGICAL_SIZE[1] * self.s)

    @staticmethod
    def for_window(window: tuple[int, int]) -> View:
        _, _, _, w, _ = fit(window, LOGICAL_SIZE)
        return View(w / LOGICAL_SIZE[0])

    def same_as(self, other: View) -> bool:
        return abs(self.s - other.s) < 1e-3

    def ss(self) -> int:
        """Supersampling factor: 3x on small views, 2x on big ones (memory)."""
        return 3 if self.s <= 1.15 else 2
