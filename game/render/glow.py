"""Soft light for the neon look: a cheap blur and the halo round a lit shape.

Everything here works on PREMULTIPLIED surfaces (see draw.shrink_pm): they blur and add correctly,
and are blitted with BLEND_PREMULTIPLIED (over) or BLEND_RGB_ADD (pure light on a dark ground).
"""

from __future__ import annotations

import pygame as pg


def blur_pm(pm: pg.Surface, radius: float) -> pg.Surface:
    """A soft blur: shrink the surface, then grow it back (both smooth). `radius` in its pixels."""
    w, h = pm.get_size()
    k = max(1.0, radius / 1.5)
    if k <= 1.0:
        return pm.copy()
    small = pg.transform.smoothscale(pm, (max(1, round(w / k)), max(1, round(h / k))))
    return pg.transform.smoothscale(small, (w, h))


def halo(core_pm: pg.Surface, radius: float, gain: float) -> pg.Surface:
    """The light round `core_pm`: a blurred copy, `gain` times as strong (gain may exceed 1)."""
    soft = blur_pm(core_pm, radius)
    out = pg.Surface(soft.get_size(), pg.SRCALPHA)
    whole = int(gain)
    for _ in range(whole):
        out.blit(soft, (0, 0), special_flags=pg.BLEND_RGBA_ADD)
    rest = gain - whole
    if rest > 0.01:
        part = soft.copy()
        m = round(255 * rest)
        part.fill((m, m, m, m), special_flags=pg.BLEND_RGBA_MULT)
        out.blit(part, (0, 0), special_flags=pg.BLEND_RGBA_ADD)
    return out


def lit(core_pm: pg.Surface, radius: float, gain: float) -> pg.Surface:
    """`core_pm` with its halo behind it (premultiplied, same size: leave room round the shape)."""
    out = halo(core_pm, radius, gain)
    out.blit(core_pm, (0, 0), special_flags=pg.BLEND_PREMULTIPLIED)
    return out
