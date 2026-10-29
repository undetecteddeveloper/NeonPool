"""Colours: an 80s arcade at night (synthwave). Cyan is the line, hot pink is what is chosen or
happening, violet joins them; the sun runs from yellow through orange to pink. Everything lit sits
on a deep indigo night; nothing is outlined in black (OUTLINE is the dark ink for text on a lit
fill).
"""

from __future__ import annotations

from dataclasses import dataclass

# --- night and solid panels ----------------------------------------------------------------
BG = (11, 5, 28)  # the night behind everything (deep indigo)
PANEL = (18, 9, 40)  # solid panels: text sits on these, never on a busy background
PANEL_HOT = (34, 14, 66)  # a panel or row under the pointer / selected
PANEL_EDGE = (66, 44, 116)  # unlit hairlines, dots that are off, ghost segments
OUTLINE = (6, 2, 16)  # the dark ink: text on a lit fill
TEXT = (244, 238, 255)
TEXT_DIM = (156, 138, 198)

# --- the lights ----------------------------------------------------------------------------
CYAN = (40, 240, 255)  # the line: rim, headings, aim
CYAN_DIM = (34, 150, 190)  # a lit line at rest
MAGENTA = (255, 46, 196)  # the accent: selected, active, happening now
VIOLET = (142, 64, 255)  # the deep glow between cyan and pink
AMBER = (255, 196, 64)  # "busy": balls rolling
ACCENT = MAGENTA
WHITE = (252, 250, 255)
ERROR = (255, 74, 104)
OK = (70, 255, 168)

# --- the synthwave sky (menu and how-to-play) ----------------------------------------------
SKY_TOP = (8, 3, 22)
SKY_LOW = (58, 12, 84)  # just above the horizon
FLOOR_FAR = (34, 6, 52)  # the floor at the horizon ...
FLOOR_NEAR = (6, 2, 16)  # ... and at the bottom of the screen
SUN_TOP = (255, 232, 92)
SUN_MID = (255, 136, 62)
SUN_LOW = (255, 40, 140)
GRID = (226, 52, 255)  # the floor grid

# --- the table: a flat dark plate drawn with a few neon lines ------------------------------
TABLE = (21, 10, 50)  # the plate (a touch lighter than the night, so the table reads at once)
CUSHION_NOSE = (52, 200, 246)  # the line where the cloth meets the cushions
POCKET = (2, 1, 6)  # inside a pocket
POCKET_RING = MAGENTA

AIM = (196, 250, 255)  # the core of the aim line
AIM_GLOW = CYAN

# balls: a dark body, the lit colour is the ring and the number
BODY = (9, 4, 24)
BALL_COLORS = {
    0: (244, 250, 255),  # cue: the one lit disc
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


def scale(c: tuple[int, int, int], k: float) -> tuple[int, int, int]:
    """A colour `k` times as bright (light added on a dark ground)."""
    return tuple(max(0, min(255, round(x * k))) for x in c)
