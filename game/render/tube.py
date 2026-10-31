"""The look of an old tube, as two small tools.

`Bulge`: the picture is bowed out like the glass of a TV or an arcade monitor. Rows in the middle
fill the screen, rows towards the top and bottom are a little narrower, so the sides bulge; the
corners are rounded and dark, the top and bottom edges bow, and a soft reflection sits high up on
the left. The rows are scaled in bands of a few device px straight into the screen (no copy of the
whole picture, no remap of every pixel), at the real resolution of the window.

`Fringe`: the red and the blue of a part of the picture slip apart, one to each side.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pygame as pg


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
