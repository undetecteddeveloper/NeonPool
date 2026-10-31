"""A very light old-tube look: thin dark scan lines over everything, and darker corners.

Kept faint on purpose (the user asked for "very light"): it must never make a ball hard to see.
The corners are darkened once, inside the backgrounds (`vignette`); the scan lines are dimmed
over the finished frame, one thin row at a time (`scanlines`), so the frame is never copied.
"""

from __future__ import annotations

import numpy as np
import pygame as pg

SCANLINE_DARK = 0.93  # a scan line keeps this much of the light
SCANLINE_PX = 3.0  # one dark line every this many device px at 1x (scaled with the view)
VIGNETTE = 0.78  # the very corners keep this much of the light

_cache: dict[tuple[int, int], pg.Surface] = {}


def period(scale: float) -> int:
    return max(2, round(SCANLINE_PX * scale))


def scanlines(screen: pg.Surface, scale: float = 1.0, dark: float = SCANLINE_DARK) -> None:
    """Dim every `period`-th row of the finished frame a little (`dark`: the light it keeps)."""
    w, h = screen.get_size()
    k = round(255 * dark)
    step = period(scale)
    for y in range(step - 1, h, step):
        screen.fill((k, k, k), (0, y, w, 1), special_flags=pg.BLEND_RGB_MULT)


def vignette(size: tuple[int, int]) -> pg.Surface:
    """The multiply layer that darkens the corners (blit it once onto a background)."""
    if size not in _cache:
        if len(_cache) > 4:
            _cache.clear()
        w, h = size
        nx = (np.arange(w) + 0.5) / w * 2 - 1
        ny = (np.arange(h) + 0.5) / h * 2 - 1
        r2 = nx[:, None] ** 2 * 0.55 + ny[None, :] ** 2 * 0.55
        k = 1.0 - (1.0 - VIGNETTE) * np.clip(r2 * 0.9, 0, 1) ** 1.5
        rgb = np.repeat((k * 255).astype(np.uint8)[:, :, None], 3, axis=2)
        _cache[size] = pg.surfarray.make_surface(rgb)
    return _cache[size]


def darken_corners(surf: pg.Surface) -> None:
    surf.blit(vignette(surf.get_size()), (0, 0), special_flags=pg.BLEND_RGB_MULT)
