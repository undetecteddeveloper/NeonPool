"""Fonts shipped with the game (assets/fonts, SIL Open Font License), all with Vietnamese marks.

- body: Chakra Petch, squared like 80s arcade lettering (Regular, SemiBold for `bold`, Bold).
- display: Tilt Neon, letters drawn as bent neon tubes (the title, big headings).
A missing file falls back to an installed system font, so the game still starts.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pygame as pg

FONT_DIR = Path(__file__).resolve().parents[2] / "assets" / "fonts"
FACES = {
    "body": "ChakraPetch-Regular.ttf",
    "bold": "ChakraPetch-SemiBold.ttf",
    "heavy": "ChakraPetch-Bold.ttf",
    "display": "TiltNeon.ttf",
}
FALLBACK = "segoeui,arial,tahoma,dejavusans,freesans"

log = logging.getLogger("neonpool")
_cache: dict[tuple[int, str], pg.font.Font] = {}


def face(size: int, name: str = "body") -> pg.font.Font:
    """The font `name` at `size` device px; recreated if pygame was shut down since."""
    key = (size, name)
    font = _cache.get(key)
    if font is not None:
        try:
            font.get_height()  # raises once the font module has been quit since creation
            return font
        except pg.error:
            pass
    if not pg.font.get_init():
        pg.font.init()
    path = FONT_DIR / FACES[name]
    if path.exists():
        font = pg.font.Font(str(path), size)
    else:
        log.warning("font file missing, using a system font: %s", path)
        font = pg.font.SysFont(FALLBACK, size, bold=name in ("bold", "heavy"))
    _cache[key] = font
    return font


def get(size: int, bold: bool = False) -> pg.font.Font:
    """The body font (SemiBold when `bold`)."""
    return face(size, "bold" if bold else "body")
