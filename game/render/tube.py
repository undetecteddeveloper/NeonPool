"""The look of an old tube, as two small tools.

`Bulge`: the picture is bowed out like the glass of a TV or an arcade monitor. Rows in the middle
fill the screen, rows towards the top and bottom are a little narrower, so the sides bulge; the
corners are rounded and dark, the top and bottom edges bow, and a soft reflection sits high up on
the left. The rows are scaled in bands of a few device px straight into the screen (no copy of the
whole picture, no remap of every pixel), at the real resolution of the window.

`Fringe`: the red and the blue of a part of the picture slip apart, one to each side.

`Monitor`: the whole look in one place, for the opening screens (loading and splash): a dark
ground with dark corners, a faint bright band crawling down, a sideways slip now and then, all
drawn flat on `pic` and then bowed onto the screen.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import pygame as pg

from game.render import crt
from game.render import palette as C
from game.render.view import View


@dataclass(frozen=True)
class Shape:
    k: float  # how much narrower the top and bottom rows are (0.18: 18% at the very edge)
    sag: float  # how far the top and bottom edges bow in at the sides (share of half the height)
    radius: float  # how big the rounded dark corners are (share of half the size)
    glare: int  # brightness of the reflection on the glass (0..255 added at its centre)


# The user chose this one by looking at pictures (2026-10-31): "MANH", like an old arcade monitor
# (the others were NHE 0.05 / 0.015 / 0.06 / 14 and VUA 0.10 / 0.03 / 0.10 / 20).
ARCADE = Shape(k=0.18, sag=0.05, radius=0.15, glare=26)
BAND_PX = 4  # rows are scaled this many device px at a time
BAR_PX, BAR_PEAK, BAR_SPEED = 150, 16, 0.28  # the faint band: height, brightness, screens/s
TEAR_EVERY_S, TEAR_S, TEAR_PX = 1.25, 0.06, 10  # now and then the picture slips sideways
EDGE_TILE = 32  # the glass edge is cut in tiles of this many px to find where it is dark


class Fringe:
    """Slip the red and the blue of a box of the canvas apart (the green stays)."""

    def __init__(self, size: tuple[int, int]) -> None:
        self._bufs = tuple(pg.Surface(size) for _ in range(3))  # three pictures, reused

    def apply(self, canvas: pg.Surface, box: pg.Rect, d: int) -> None:
        box = box.clip(canvas.get_rect())
        if d < 1 or box.w <= 0 or box.h <= 0:
            return
        if box.w > self._bufs[0].get_width() or box.h > self._bufs[0].get_height():
            self._bufs = tuple(pg.Surface(box.size) for _ in range(3))
        src, channel, out = (b.subsurface((0, 0, box.w, box.h)) for b in self._bufs)
        src.blit(canvas, (0, 0), area=box)
        out.fill((0, 0, 0))
        for mask, dx in (((255, 0, 0), d), ((0, 255, 0), 0), ((0, 0, 255), -d)):
            channel.blit(src, (0, 0))
            channel.fill(mask, special_flags=pg.BLEND_RGB_MULT)  # only this colour
            out.blit(channel, (dx, 0), special_flags=pg.BLEND_RGB_ADD)
        if box.w > 2 * d:  # (the columns at the two ends lack a colour once it has slipped)
            canvas.blit(out, (box.x + d, box.y), area=pg.Rect(d, 0, box.w - 2 * d, box.h))


class Bulge:
    """Draw a picture of `size` onto a screen of the same size, bowed out like a tube."""

    def __init__(self, size: tuple[int, int], shape: Shape = ARCADE) -> None:
        self.size, self.shape = size, shape
        w, h = size
        self._bands: list[tuple[pg.Rect, pg.Rect]] = []  # (rows of the picture, where they go)
        for y in range(0, h, BAND_PX):
            rows = min(BAND_PX, h - y)
            v = (y + rows / 2) / h * 2 - 1
            width = max(2, round(w * (1 - shape.k * v * v)))
            self._bands.append((pg.Rect(0, y, w, rows), pg.Rect((w - width) // 2, y, width, rows)))
        self._glare, self._glare_at = self._bake_glare()
        self._frame, self._frame_areas = self._bake_frame()
        self._subs: tuple[pg.Surface, pg.Surface, list, list] | None = None  # see _pieces

    def _bake_glare(self) -> tuple[pg.Surface, tuple[int, int]]:
        w, h = self.size
        gw, gh = round(w * 0.6), round(h * 0.36)
        gx, gy = (np.arange(gw) - gw / 2) / (w * 0.15), (np.arange(gh) - gh / 2) / (h * 0.09)
        k = np.exp(-(gx[:, None] ** 2 + gy[None, :] ** 2)) * self.shape.glare
        rgb = np.repeat(k.astype(np.uint8)[:, :, None], 3, axis=2)
        return pg.surfarray.make_surface(rgb), (round(w * 0.25 - gw / 2), round(h * 0.225 - gh / 2))

    def _bake_frame(self) -> tuple[pg.Surface, list[pg.Rect]]:
        """The black glass edge as one picture with transparency, and the rectangles of it that
        are not clear (only those are pasted every frame)."""
        w, h = self.size
        s = self.shape
        u = ((np.arange(w) + 0.5) / w * 2 - 1)[:, None]
        v = ((np.arange(h) + 0.5) / h * 2 - 1)[None, :]
        fw = 1 - s.k * v * v
        inside = np.abs(v) <= 1 - s.sag * u * u  # the top and bottom bow
        rx = np.maximum(np.abs(u) / fw - (1 - s.radius), 0)
        ry = np.maximum(np.abs(v) - (1 - s.radius), 0)
        soft = np.clip(1 - (np.hypot(rx, ry) / s.radius - 0.75) / 0.25, 0, 1)
        alpha = (255 * (1 - soft * inside)).astype(np.uint8)
        surf = pg.Surface(self.size, pg.SRCALPHA)
        surf.fill((0, 0, 0, 0))
        pg.surfarray.pixels_alpha(surf)[:] = alpha
        return surf, self._dark_areas(alpha != 0)

    @staticmethod
    def _dark_areas(dark: np.ndarray) -> list[pg.Rect]:
        """Rectangles that together cover every dark pixel of the glass edge (`dark`: [x, y]):
        the picture is cut in tiles and the tiles with any dark in them are joined into runs along
        each row of tiles, so only the edge of the screen is pasted every frame."""
        w, h = dark.shape
        areas: list[pg.Rect] = []
        for y in range(0, h, EDGE_TILE):
            run_from = None
            for x in range(0, w + EDGE_TILE, EDGE_TILE):
                has = x < w and bool(dark[x : x + EDGE_TILE, y : y + EDGE_TILE].any())
                if has and run_from is None:
                    run_from = x
                elif not has and run_from is not None:
                    areas.append(pg.Rect(run_from, y, min(x, w) - run_from, min(EDGE_TILE, h - y)))
                    run_from = None
        return areas

    def _pieces(self, src: pg.Surface, dst: pg.Surface):
        """The bands as subsurfaces of the two pictures, made once for these two surfaces."""
        if self._subs is None or self._subs[0] is not src or self._subs[1] is not dst:
            self._subs = (
                src,
                dst,
                [src.subsurface(a) for a, _ in self._bands],
                [dst.subsurface(b) for _, b in self._bands],
            )
        return self._subs[2], self._subs[3]

    def apply(self, src: pg.Surface, dst: pg.Surface) -> None:
        """Paint `src` bowed out onto `dst` (both of `size`)."""
        dst.fill((0, 0, 0))
        from_rows, to_rows = self._pieces(src, dst)
        for a, b in zip(from_rows, to_rows, strict=True):
            pg.transform.scale(a, b.get_size(), b)
        dst.blit(self._glare, self._glare_at, special_flags=pg.BLEND_RGB_ADD)
        for area in self._frame_areas:
            dst.blit(self._frame, area.topleft, area=area)


_bulges: dict[tuple[tuple[int, int], Shape], Bulge] = {}


def bulge_for(size: tuple[int, int], shape: Shape = ARCADE) -> Bulge:
    """The bowed-glass maker for a picture size, made once and shared (it takes ~0.1-0.4 s)."""
    key = (size, shape)
    if key not in _bulges:
        if len(_bulges) >= 3:
            _bulges.clear()
        _bulges[key] = Bulge(size, shape)
    return _bulges[key]


class Monitor:
    """An old arcade monitor's picture. `begin()` gives the flat picture to draw on (dark ground
    already on it); `present(screen, t)` adds the band and the slip and bows it onto `screen`."""

    def __init__(self, v: View) -> None:
        self.view = v
        self.pic = pg.Surface(v.canvas)  # the flat picture
        self._bg = pg.Surface(v.canvas)
        self._bg.fill(C.BG)
        crt.darken_corners(self._bg)
        w, _ = v.canvas
        rows = (np.sin(np.linspace(0, math.pi, v.i(BAR_PX))) ** 2 * BAR_PEAK).astype(np.uint8)
        self._bar = pg.surfarray.make_surface(np.repeat(np.tile(rows, (w, 1))[:, :, None], 3, 2))
        self.bulge = bulge_for(v.canvas)

    def begin(self) -> pg.Surface:
        self.pic.blit(self._bg, (0, 0))
        return self.pic

    def present(self, screen: pg.Surface, t: float, tear: bool = True) -> None:
        pic, v = self.pic, self.view
        if tear and t >= 2.0 and (t / TEAR_EVERY_S) % 1.0 < TEAR_S / TEAR_EVERY_S:
            w, h = pic.get_size()  # for a few frames a band of the picture slips sideways
            y, bh = int((t * 7.3 % 1.0) * h * 0.8), v.i(26)
            band = pic.subsurface((0, y, w, min(bh, h - y))).copy()
            pic.blit(band, (v.i(TEAR_PX * math.sin(t * 90)), y))
        y = int(((t * BAR_SPEED) % 1.3 - 0.15) * pic.get_height())
        pic.blit(self._bar, (0, y), special_flags=pg.BLEND_RGB_ADD)
        if screen.get_size() == pic.get_size():
            self.bulge.apply(pic, screen)
        else:  # (the window is being resized and the pictures are for the old size)
            screen.blit(pic, (0, 0))
