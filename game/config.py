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

# --- Spin: follow (high) and draw (low) on the cue ball --------------------------------------
# Model (docs/GAME_DESIGN.md, the spin section): a struck ball slides on the cloth until it
# rolls. The part of that slide a plain centre hit does not have is the cue ball's "slip" q
# (a vector, m/s, along the aim line). Sliding friction uses q up at `decay` m/s^2 and turns
# every unit of it into SLIDE_GAIN units of speed along q: follow pushes the ball on, draw
# pulls it back.
SLIDE_GAIN = 2 / 7  # solid sphere: speed gained per unit of slip used up (Townsend, UIUC)


@dataclass(frozen=True)
class SpinSet:
    """A named bundle of 'how strong spin is'. Chosen by the user by playing."""

    key: str
    base: float  # slip (m/s) given at spin = +-1 whatever the power: soft shots spin too
    gain: float  # ... plus this multiple of the shot speed: hard shots spin more
    decay: float  # m/s^2: how fast the slip is used up (3.5 * sliding friction * g)


# A real cloth uses slip up fast (decay ~6.9) and a tip half a radius off centre gives slip ~1.25 x
# the speed, but this table rolls far (little rolling friction): that sent the cue ball metres and
# left soft shots with no spin at all (used up before the hit). So slip is mostly a fixed amount
# (base) used up slowly (decay), with a little extra for power. All self-chosen; playtest decides.
SPIN_SETS: dict[str, SpinSet] = {
    "NHE": SpinSet("NHE", base=1.2, gain=0.1, decay=2.0),
    "VUA": SpinSet("VUA", base=1.5, gain=0.1, decay=1.8),
    "MANH": SpinSet("MANH", base=1.8, gain=0.1, decay=1.5),
}
SPIN_MAX_RATIO = 3.0  # slip never exceeds this multiple of the shot speed (a feather-light shot
# must not get a push out of nothing)
DEFAULT_SPIN = "VUA"
SPIN_WHEEL_STEP = 0.25  # one notch of the mouse wheel moves the spin this much (-1 .. +1)
SPIN_DIAL_TRAVEL = 0.62  # the dot on the dial reaches this fraction of the ball's radius

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
AIM_MIN_PX = 4  # pulled less than this from where the press was: no direction yet
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
# --- The numbers on the result card count up one after the other (game/tally.py) ---
TALLY_SPANS = (("score", 1.1), ("shots", 0.6), ("fouls", 0.5))  # in order: name, seconds it runs
TALLY_START_S = 0.7  # after the game ends: the card has grown in and the jingle is on its way
TALLY_GAP_S = 0.15  # a pause between one number and the next
TALLY_MAX_TICKS = 14  # a counting number ticks at most this many times (one per step when fewer)
TALLY_FLASH_S = 0.4  # a number that has just stopped glows brighter for this long
MUSIC_GAIN = 0.7  # the music setting at 100% plays this loud (the effects stay in front)
MUSIC_FADE_S = 1.0  # one track fades out while the next fades in (menu <-> game)
MUSIC_DUCK = 0.3  # the music drops to this while the result card is up (the jingle plays)
MUSIC_DUCK_S = 0.3  # ... and comes back / goes down over this long
MUSIC_CHANNELS = 2  # mixer channels kept for the music (one per track), never used by effects

# --- Score on the result card (rules/eight_ball.py: `EightBall.score`) ---
SCORE_WIN_BASE = 1000  # a won game starts from this ...
SCORE_PER_SHOT = 10  # ... loses this for every shot ...
SCORE_PER_FOUL = 50  # ... and this for every foul ...
SCORE_WIN_MIN = 100  # ... but a win is never worth less than this
SCORE_PER_BALL_LOST = 50  # a lost game only counts the balls that went down (the 8 excluded)

# --- Network play (docs/ARCHITECTURE.md, section on network play) ---
GAME_VERSION = "0.1"  # two builds with different values never meet; bump it with any change that
# can alter a shot's result (the physics numbers are also checked: protocol.physics_fingerprint)
NET_PORT = 47474  # where a room listens on the local network
NET_AIM_HZ = 30  # at most this many cue-position packets a second
NET_DESYNC_M = 0.0005  # a checkpoint ball this far (m) from the local one counts as a desync
NET_NAME_MAX = 16  # longest player name (characters)
NET_CONNECT_TIMEOUT_S = 5.0  # joining a room: give up after this long
NET_HANDSHAKE_TIMEOUT_S = 5.0  # a connection that says nothing for this long is dropped
NET_REMOTE_CUE_TAU_S = 1 / 60  # the other player's cue closes on its newest position in ~1 frame

# --- Rack: ball numbers in rack order (apex first). 8 in the middle of row 3,
# the two back corners are one solid (6) and one stripe (15). ---
RACK_ORDER = (1, 9, 2, 10, 8, 3, 11, 4, 12, 5, 6, 13, 14, 7, 15)
ROW_STEP = math.sqrt(3) * BALL_R + RACK_GAP  # distance between rack rows along x
