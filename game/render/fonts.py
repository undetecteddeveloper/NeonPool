"""Fonts with Vietnamese diacritics: first installed of the chain, else pygame's default."""

from __future__ import annotations

import pygame as pg

CHAIN = "segoeui,arial,tahoma,dejavusans,freesans"

_cache: dict[tuple[int, bool], pg.font.Font] = {}


def get(size: int, bold: bool = False) -> pg.font.Font:
    key = (size, bold)
    font = _cache.get(key)
    if font is not None:
        try:
            font.get_height()  # raises once the font module has been quit since creation
            return font
        except pg.error:
            pass
    if not pg.font.get_init():
        pg.font.init()
    font = _cache[key] = pg.font.SysFont(CHAIN, size, bold=bold)
    return font
