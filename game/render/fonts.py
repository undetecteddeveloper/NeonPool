"""Fonts with Vietnamese diacritics: first installed of the chain, else pygame's default."""

from __future__ import annotations

from functools import cache

import pygame as pg

CHAIN = "segoeui,arial,tahoma,dejavusans,freesans"


@cache
def get(size: int, bold: bool = False) -> pg.font.Font:
    if not pg.font.get_init():
        pg.font.init()
    return pg.font.SysFont(CHAIN, size, bold=bold)
