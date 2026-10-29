"""View: logical canvas units -> device pixels. Everything is drawn at the real window resolution.

Layout and game code stay in logical units (1280x720, the "frame"); only drawing multiplies by `s`
and adds the frame's offset (ox, oy) inside the canvas. The canvas is the WHOLE window: the frame
sits in its middle at the right aspect ratio, and backgrounds fill the rest (no black bars).
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
    ox: int = 0  # where the logical frame starts inside the canvas (device px; may be negative)
    oy: int = 0
    cw: int = 0  # size of the canvas in device px; 0 = just the frame
    ch: int = 0

    def n(self, v: float) -> float:
        return v * self.s

    def i(self, v: float) -> int:
        return round(v * self.s)

    def pt(self, p: tuple[float, float]) -> tuple[float, float]:
        return p[0] * self.s + self.ox, p[1] * self.s + self.oy

    def ipt(self, p: tuple[float, float]) -> tuple[int, int]:
        return round(p[0] * self.s) + self.ox, round(p[1] * self.s) + self.oy

    def rect(self, x: float, y: float, w: float, h: float) -> pg.Rect:
        """Rounded per edge (not per size), so neighbouring rects leave no gap."""
        x0, y0 = round(x * self.s), round(y * self.s)
        return pg.Rect(
            x0 + self.ox, y0 + self.oy, round((x + w) * self.s) - x0, round((y + h) * self.s) - y0
        )

    def scaled(self, k: float) -> View:
        return View(
            self.s * k,
            round(self.ox * k),
            round(self.oy * k),
            round(self.cw * k),
            round(self.ch * k),
        )

    def shifted(self, dx: int, dy: int) -> View:
        """The same scale for a surface whose top-left corner is the canvas point (dx, dy)."""
        return View(self.s, self.ox - dx, self.oy - dy)

    def framed(self) -> View:
        """The same scale with no margins: for surfaces that hold only the frame."""
        return View(self.s)

    @property
    def size(self) -> tuple[int, int]:
        """The logical frame in device px."""
        return round(LOGICAL_SIZE[0] * self.s), round(LOGICAL_SIZE[1] * self.s)

    @property
    def canvas(self) -> tuple[int, int]:
        """The whole canvas (the window) in device px."""
        fw, fh = self.size
        return (self.cw or fw), (self.ch or fh)

    def logical_bounds(self) -> tuple[float, float, float, float]:
        """(left, top, right, bottom) of the whole canvas in logical units (wider or taller than
        the 1280x720 frame when the window has another shape)."""
        cw, ch = self.canvas
        return (
            -self.ox / self.s,
            -self.oy / self.s,
            (cw - self.ox) / self.s,
            (ch - self.oy) / self.s,
        )

    @staticmethod
    def for_window(window: tuple[int, int]) -> View:
        _, x, y, w, _ = fit(window, LOGICAL_SIZE)
        return View(w / LOGICAL_SIZE[0], x, y, window[0], window[1])

    def same_as(self, other: View) -> bool:
        return abs(self.s - other.s) < 1e-3 and self.canvas == other.canvas

    def ss(self) -> int:
        """Supersampling factor: 3x on small views, 2x on big ones (memory)."""
        return 3 if self.s <= 1.15 else 2
