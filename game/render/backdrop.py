"""The night behind the table: deep indigo, a little lighter in the middle."""

from __future__ import annotations

import math

import numpy as np
import pygame as pg

from game.render import palette as C

_RES = (160, 90)  # the gradient is built this small, then stretched smoothly
_cache: dict[tuple[int, int], pg.Surface] = {}


def night(size: tuple[int, int]) -> pg.Surface:
    """An opaque surface of `size`. Cached: blit it, never draw on it."""
    if size not in _cache:
        if len(_cache) > 4:
            _cache.clear()
        w, h = _RES
        ys, xs = np.mgrid[0:h, 0:w]
        nx, ny = (xs + 0.5) / w * 2 - 1, (ys + 0.5) / h * 2 - 1
        u = np.clip(np.sqrt(nx * nx + (ny * 1.3) ** 2) / math.sqrt(2), 0.0, 1.0)
        centre, edge = np.array((17, 8, 40), float), np.array(C.BG, float)
        rgb = centre[None, None, :] + (edge - centre)[None, None, :] * u[:, :, None]
        small = pg.surfarray.make_surface(rgb.astype(np.uint8).transpose(1, 0, 2))
        _cache[size] = pg.transform.smoothscale(small, size)
    return _cache[size]
