"""Where things sit on the logical canvas. The only place metres turn into pixels."""

from __future__ import annotations

from game.config import BALL_R, LOGICAL_SIZE, PX_PER_M, RAIL_PX, TABLE_L, TABLE_W

LW, LH = LOGICAL_SIZE
FIELD_W = round(TABLE_L * PX_PER_M)
FIELD_H = round(TABLE_W * PX_PER_M)
OUTER_W = FIELD_W + 2 * RAIL_PX
OUTER_H = FIELD_H + 2 * RAIL_PX
OUTER_X = 50
OUTER_Y = (LH - OUTER_H) // 2
FIELD_X = OUTER_X + RAIL_PX
FIELD_Y = OUTER_Y + RAIL_PX

BALL_PX = BALL_R * PX_PER_M

# side panel, right of the table
PANEL_X = OUTER_X + OUTER_W + 22
PANEL_W = LW - PANEL_X - OUTER_X  # same margin on both sides
PANEL_Y = OUTER_Y
PANEL_H = OUTER_H

# the table and the glow round it (x, y, w, h): what goes dark while a two-player game's coin is
# tossed. It stops below the name plates and left of the side panel.
TABLE_GLOW = (OUTER_X - 10, OUTER_Y - 6, OUTER_W + 20, OUTER_H + 12)


def to_px(x: float, y: float) -> tuple[float, float]:
    return FIELD_X + x * PX_PER_M, FIELD_Y + y * PX_PER_M


def to_m(px: float, py: float) -> tuple[float, float]:
    return (px - FIELD_X) / PX_PER_M, (py - FIELD_Y) / PX_PER_M
