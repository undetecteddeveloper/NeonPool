"""Constants and named feel sets. Units: metres, seconds. No pygame import here."""

from __future__ import annotations

import math
from dataclasses import dataclass

# --- Table (cloth surface; origin = top-left corner, x along the long side, y down) ---
TABLE_L = 2.54
TABLE_W = 1.27
BALL_R = 0.02858  # real pool ball is 57.15 mm across
CORNER_POCKET_R = 0.065  # self-chosen; tune by playtest
SIDE_POCKET_R = 0.070  # self-chosen; tune by playtest

# (x, y, radius): 4 corners then 2 side pockets
POCKETS: tuple[tuple[float, float, float], ...] = (
    (0.0, 0.0, CORNER_POCKET_R),
    (TABLE_L, 0.0, CORNER_POCKET_R),
    (0.0, TABLE_W, CORNER_POCKET_R),
    (TABLE_L, TABLE_W, CORNER_POCKET_R),
    (TABLE_L / 2, 0.0, SIDE_POCKET_R),
    (TABLE_L / 2, TABLE_W, SIDE_POCKET_R),
)

HEAD_SPOT = (TABLE_L * 0.25, TABLE_W / 2)  # cue ball start / respawn
FOOT_SPOT = (TABLE_L * 0.75, TABLE_W / 2)  # apex of the rack
RACK_GAP = 1e-4  # tiny gap so racked balls do not start overlapping

# --- Simulation ---
PHYSICS_DT = 1 / 240
MAX_FRAME_DT = 0.05  # clamp one render frame's time so a stall cannot spiral
MAX_STEP_FRAC = 0.25  # a sub-step moves a ball at most BALL_R * this (no tunnelling)
REST_SPEED = 0.01  # m/s; slower than this after friction = stopped
MIN_EVENT_SPEED = 0.001  # m/s; the rules must see even the gentlest touch of two balls


@dataclass(frozen=True)
class FeelSet:
    """A named bundle of 'how the table feels'. Chosen by the user by playing."""

    key: str
    name_key: str  # i18n key for the display name
    roll_decel: float  # m/s^2, constant rolling deceleration
    cushion_e: float  # restitution against the cushion (1 = no loss)
    ball_e: float  # restitution ball-ball
    v_max: float  # m/s at full power


# Starting values: cushion e 0.98 and rolling friction ~0.01 (decel ~0.1) are the research
# baselines in docs/GAME_DESIGN.md (TRON); VUA / CHAM are self-chosen, to be playtested.
FEEL_SETS: dict[str, FeelSet] = {
    "TRON": FeelSet("TRON", "feel.tron", roll_decel=0.10, cushion_e=0.98, ball_e=0.96, v_max=5.8),
    "VUA": FeelSet("VUA", "feel.vua", roll_decel=0.18, cushion_e=0.92, ball_e=0.95, v_max=5.0),
    "CHAM": FeelSet("CHAM", "feel.cham", roll_decel=0.35, cushion_e=0.85, ball_e=0.93, v_max=4.3),
}
FEEL_ORDER = ("TRON", "VUA", "CHAM")  # keys 1 / 2 / 3
DEFAULT_FEEL = "VUA"

# --- Screen / input (logical canvas is drawn once, then scaled to the window) ---
LOGICAL_SIZE = (1280, 720)
PX_PER_M = 350  # render only (invariant 3): metres -> logical pixels
RAIL_PX = 40  # visual rail thickness around the cloth
MAX_DRAG_PX = 220  # pull-back distance (logical px) that means full power
MIN_PULL_PX = 12  # releasing with a shorter pull than this cancels the shot
VOLUME_STEP = 0.1  # the volume setting moves in steps of 10%
CUE_SHOW_PULL = 0.75  # the neon cue travels 75% of the pull (the power is unchanged)
POWER_CURVE = 2.0  # power = (pull / MAX_DRAG_PX) ** POWER_CURVE: gentle at first, strong at the end
GRAB_RADIUS_M = BALL_R * 2.6  # how close to the cue ball a press must be to start aiming
AIM_MIN_PX = 4  # pointer closer than this to the cue ball: no direction yet
KNOB_DEAD_PX = 3.0  # turning the cue: the pointer this close to the ball centre is ignored

# --- Effects (subtle) and sound ---
RIPPLE_BALL_SPEED = 1.2  # m/s: ball-ball impact at least this hard shows a ripple
RIPPLE_CUSHION_SPEED = 1.6
RIPPLE_S = 0.5  # a ripple of light spreads and fades over this time
TABLE_WAVE_SPEED = 820.0  # a ball drops: a wave in its colour runs over the table (logical px/s)
TABLE_WAVE_S = 1.5  # ... and has died out after this long (it has crossed the whole table)
TABLE_WAVE_BAND = 22.0  # the table's lines light up this close to the passing ring (logical px)
STRONG_HIT_SPEED = 3.2  # m/s: a hit at least this hard shakes the screen a little (setting)
BALL_RIPPLE_PX = 30  # how far a collision ripple spreads past the balls (logical px)
MAX_RIPPLES = 14
POCKET_ANIM_S = 0.25  # a pocketed ball shrinks toward the pocket over this time
BREAK_SHAKE_SPEED = 2.5  # m/s: the first hard hit after a rack shakes the screen
SHAKE_PX = 4.0
SHAKE_S = 0.30
NOTICE_S = 4.0  # how long a foul / group notice stays on the cloth
SAMPLE_RATE = 44100
SFX_MAX_PER_FRAME = 6  # cap sounds started per frame so a break is not a wall of noise
SFX_REF_SPEED = 6.0  # m/s that maps to full volume
SFX_MIN_SPEED = 0.05  # m/s; softer impacts make no sound (no ticking at the end of a roll)

# --- Rack: ball numbers in rack order (apex first). 8 in the middle of row 3,
# the two back corners are one solid (6) and one stripe (15). ---
RACK_ORDER = (1, 9, 2, 10, 8, 3, 11, 4, 12, 5, 6, 13, 14, 7, 15)
ROW_STEP = math.sqrt(3) * BALL_R + RACK_GAP  # distance between rack rows along x
