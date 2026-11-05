"""Marks drawn on top of real game pictures for the how-to-play screen.

The pictures themselves are taken from the game (scenes/help_pictures.py); this module only adds
what a screenshot cannot show: step numbers, arrows, tick and cross badges, rings, labels.
Points are in GAME logical coordinates (the 1280x720 canvas); `origin` is the top-left of the
cropped picture in those coordinates, so a mark lands exactly on the thing it points at.
"""

from __future__ import annotations

import math

import pygame as pg

from game.render import palette as C
from game.render.draw import Aa, blit_rrect, box_around
from game.render.hud import text, text_width
from game.render.view import View

Point = tuple[float, float]


class Annot:
    """Draws smooth marks on `surf` (an opaque picture rendered at view `v`)."""

    def __init__(self, surf: pg.Surface, v: View, origin: Point = (0.0, 0.0)) -> None:
        self.surf, self.v, self.origin = surf, v, origin

    def _t(self, p: Point) -> Point:
        return p[0] - self.origin[0], p[1] - self.origin[1]

    def _layer(self, pts: list[Point], pad: float) -> Aa:
        box = box_around(self.v, [self._t(p) for p in pts], pad)
        return Aa(self.surf, self.v, box, ss=2)

    # --- shapes ------------------------------------------------------------------------
    def disc(self, c: Point, r: float, color, width: float = 0) -> None:
        layer = self._layer([c], r + 3)
        w = max(1, round(layer.n(width))) if width else 0
        pg.draw.circle(layer.surf, color, layer.pt(self._t(c)), layer.n(r), w)
        layer.done()

    def ring(self, c: Point, r: float, color, width: float = 3) -> None:
        self.disc(c, r, color, width)

    def line(self, a: Point, b: Point, width: float, color) -> None:
        layer = self._layer([a, b], width + 2)
        pa, pb = layer.pt(self._t(a)), layer.pt(self._t(b))
        pg.draw.line(layer.surf, color, pa, pb, max(1, round(layer.n(width))))
        for p in (pa, pb):
            pg.draw.circle(layer.surf, color, p, layer.n(width / 2))
        layer.done()

    def dashed(self, a: Point, b: Point, width: float, color, dash: float = 9, gap: float = 7):
        length = math.dist(a, b)
        ux, uy = (b[0] - a[0]) / length, (b[1] - a[1]) / length
        pos = 0.0
        while pos < length:
            end = min(pos + dash, length)
            start = (a[0] + ux * pos, a[1] + uy * pos)
            self.line(start, (a[0] + ux * end, a[1] + uy * end), width, color)
            pos += dash + gap

    def polygon(self, pts: list[Point], fill, outline=C.OUTLINE, outline_w: float = 2) -> None:
        layer = self._layer(pts, outline_w + 2)
        lp = [layer.pt(self._t(p)) for p in pts]
        pg.draw.polygon(layer.surf, fill, lp)
        if outline:
            pg.draw.polygon(layer.surf, outline, lp, max(1, round(layer.n(outline_w))))
        layer.done()

    def panel(self, x: float, y: float, w: float, h: float, fill=C.BG, radius: float = 8) -> None:
        tx, ty = self._t((x, y))
        blit_rrect(self.surf, self.v, tx, ty, w, h, radius, fill, 1.2, C.CYAN_DIM)

    def text(
        self, s: str, pos: Point, size: int = 14, color=C.TEXT, bold=False, center=False,
        optical=False,
    ):  # fmt: skip
        text(self.surf, self.v, s, size, color, self._t(pos), bold=bold, center=center,
             optical=optical)  # fmt: skip

    # --- marks -----------------------------------------------------------------------------
    def arrow(self, a: Point, b: Point, fill=C.ACCENT, dashed: bool = False) -> None:
        """Arrow from a to b, lit like the game's own arrows (a soft halo under a bright core)."""
        length = math.dist(a, b)
        dx, dy = (b[0] - a[0]) / length, (b[1] - a[1]) / length
        base = (b[0] - dx * 11, b[1] - dy * 11)
        if dashed:
            self.dashed(a, base, 3, fill)
        else:
            self.line(a, base, 9, (*fill, 70))
            self.line(a, base, 3, fill)
        nx, ny = -dy, dx
        head = [b, (base[0] + nx * 8, base[1] + ny * 8), (base[0] - nx * 8, base[1] - ny * 8)]
        self.polygon(head, fill, outline=None)

    def arc_arrow(self, c: Point, r: float, a0: float, a1: float, color=C.ACCENT) -> None:
        """A curved arrow round `c` from angle a0 to a1 (degrees, clockwise on screen): "turn"."""
        steps = 24
        pts = [
            (c[0] + r * math.cos(math.radians(a0 + (a1 - a0) * i / steps)),
             c[1] + r * math.sin(math.radians(a0 + (a1 - a0) * i / steps)))
            for i in range(steps + 1)
        ]  # fmt: skip
        for a, b in zip(pts, pts[1:], strict=False):
            self.line(a, b, 7, (*color, 60))
        for a, b in zip(pts, pts[1:], strict=False):
            self.line(a, b, 2.6, color)
        end = math.radians(a1)
        d = 1 if a1 > a0 else -1
        tx, ty = -math.sin(end) * d, math.cos(end) * d  # along the arc at its end
        nx, ny = math.cos(end), math.sin(end)
        tip = (pts[-1][0] + tx * 9, pts[-1][1] + ty * 9)
        head = [
            tip,
            (pts[-1][0] + nx * 6, pts[-1][1] + ny * 6),
            (pts[-1][0] - nx * 6, pts[-1][1] - ny * 6),
        ]
        self.polygon(head, color, outline=None)

    def cursor(self, c: Point) -> None:
        """A mouse pointer with its tip at `c`."""
        shape = [(0, 0), (0, 17), (4.2, 13.2), (7.4, 20), (10.2, 18.8), (7.1, 12.4), (12.5, 12.4)]
        self.polygon([(c[0] + x, c[1] + y) for x, y in shape], C.WHITE, C.OUTLINE, 1.6)

    def step(self, n: int, c: Point) -> None:
        """A numbered marker; the same number stands in front of the matching sentence."""
        self.disc(c, 13, (*C.ACCENT, 80))
        self.disc(c, 10, C.ACCENT)
        self.text(str(n), c, 15, C.OUTLINE, bold=True, center=True, optical=True)

    def mark(self, c: Point, ok: bool, r: float = 11) -> None:
        """A mint tick (right) or a red cross (wrong), each in a soft halo."""
        self.disc(c, r + 3, (*(C.OK if ok else C.ERROR), 80))
        self.disc(c, r, C.OK if ok else C.ERROR)
        k = r * 0.46
        if ok:
            tick = [(c[0] - k, c[1] + 0.05 * r), (c[0] - 0.1 * k, c[1] + k * 0.85)]
            self.line(tick[0], tick[1], 3, C.WHITE)
            self.line(tick[1], (c[0] + k, c[1] - k * 0.8), 3, C.WHITE)
        else:
            self.line((c[0] - k, c[1] - k), (c[0] + k, c[1] + k), 3, C.WHITE)
            self.line((c[0] - k, c[1] + k), (c[0] + k, c[1] - k), 3, C.WHITE)

    def tag(self, s: str, centre: Point, target: Point | None = None) -> None:
        """A label in a dark pill, with a thin line and a dot to the thing it names."""
        w = text_width(self.v, s, 15, True) + 22
        if target is not None:  # the line stops at the rim of the ball, so the number stays visible
            dx, dy = centre[0] - target[0], centre[1] - target[1]
            n = math.hypot(dx, dy) or 1.0
            rim = (target[0] + dx / n * 13, target[1] + dy / n * 13)
            self.line(centre, rim, 2, C.CYAN)
            self.disc(rim, 3.5, C.CYAN)
        self.panel(centre[0] - w / 2, centre[1] - 14, w, 28, C.BG, 10)
        self.text(s, centre, 15, C.TEXT, bold=True, center=True)
