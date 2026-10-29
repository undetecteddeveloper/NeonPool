"""Colours: a table at night, lit by neon tubes. Cyan is the line, pink-violet is what is chosen
or happening. Everything here is a lit colour on a deep blue-black night; nothing is outlined in
black any more (OUTLINE is the dark "ink" used for text on a lit fill).
"""

from __future__ import annotations

from dataclasses import dataclass

# --- night and glass ---------------------------------------------------------------------------
BG = (8, 10, 24)  # the night behind everything
PANEL = (13, 17, 42)  # glass panels, buttons at rest
PANEL_HOT = (22, 26, 62)  # a panel under the pointer or selected
PANEL_EDGE = (38, 54, 108)  # unlit hairlines, dots that are off
OUTLINE = (4, 5, 12)  # the dark ink: text on a lit fill
TEXT = (230, 246, 255)
TEXT_DIM = (125, 141, 184)

# --- the lights ----------------------------------------------------------------------------------
CYAN = (46, 242, 255)  # the line: rim, headings, aim
CYAN_DIM = (30, 150, 178)  # a lit line at rest
MAGENTA = (255, 79, 216)  # the accent: selected, active, happening now
VIOLET = (122, 76, 255)  # the deep glow between cyan and magenta
ACCENT = MAGENTA
WHITE = (252, 253, 255)
ERROR = (255, 92, 108)
OK = (84, 255, 172)

# --- the table -----------------------------------------------------------------------------------
CLOTH_CENTRE = (20, 34, 78)  # the cloth is a night blue, a little lighter in the middle
CLOTH_EDGE = (7, 9, 24)
RAIL = (9, 12, 30)  # the rail around the cloth
CUSHION = (17, 24, 60)
CUSHION_BASE = (9, 12, 30)
CUSHION_NOSE = (48, 196, 236)  # the lit edge of a cushion, facing the cloth
SIGHT = (160, 240, 255)  # the diamonds on the rail
POCKET = (2, 3, 8)  # the deepest part of the hole
POCKET_WALL = (26, 14, 56)  # the near wall of a pocket, a violet crescent
POCKET_RING = MAGENTA

AIM = (190, 250, 255)  # the core of the aim line
AIM_GLOW = CYAN
POWER_WEAK = CYAN
POWER_STRONG = MAGENTA

# balls: a dark body, the lit colour is the ring and the number
BODY = (7, 9, 24)
BALL_COLORS = {
    0: (240, 250, 255),  # cue: the one lit disc
    1: (255, 214, 64),
    2: (76, 132, 255),
    3: (255, 72, 80),
    4: (180, 96, 255),
    5: (255, 140, 48),
    6: (48, 226, 140),
    7: (222, 70, 116),
    8: (200, 208, 232),
}


@dataclass(frozen=True)
class Look:
    """How bright the neon is: the named set the user chose by looking at pictures (2026-10-29)."""

    line: float  # width of every lit line, relative to 1.0
    glow: float  # strength of the halo round a lit line, relative to 1.0
    reach: float  # how far the halo reaches, relative to 1.0


# The look called "tube lamp": thin sharp tubes and a tight halo, so a 20 px ball shows its number
LOOK = Look(line=0.85, glow=0.8, reach=0.85)


def lerp(a: tuple[int, int, int], b: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    t = min(1.0, max(0.0, t))
    return tuple(round(x + (y - x) * t) for x, y in zip(a, b, strict=True))
