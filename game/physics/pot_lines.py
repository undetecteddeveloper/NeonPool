"""Pot lines: in how many ways could this ball be shot straight into a pocket? Pure (no pygame).

A line to one pocket exists when all of these hold (ball centres, metres):
- the target can travel straight to the pocket (aimed at its mouth, kept inside the cushions)
  without touching another ball;
- the cue ball can travel straight to the "ghost" spot one ball behind the target on that line
  without touching another ball, and cuts it no thinner than `max_cut_deg`;
- the ghost spot itself lies inside the cushions.
With the cue ball in hand it will be put wherever suits, so only the ghost spot has to be free.
Bank shots and combinations are not counted: this is "is there an honest shot", not "is there any".
"""

from __future__ import annotations

import math
from collections.abc import Sequence

from game.config import (
    BALL_R,
    POCKETS,
    PRACTICE_LINE_MARGIN_M,
    PRACTICE_MAX_CUT_DEG,
    TABLE_L,
    TABLE_W,
)
from game.physics.world import CUE, Ball


def _near_segment(
    balls: Sequence[Ball], a: tuple[float, float], b: tuple[float, float], reach: float
) -> bool:
    """Is any of `balls` closer than `reach` to the segment a-b?"""
    dx, dy = b[0] - a[0], b[1] - a[1]
    length2 = dx * dx + dy * dy
    for ball in balls:
        if length2 == 0.0:
            s = 0.0
        else:
            s = max(0.0, min(1.0, ((ball.x - a[0]) * dx + (ball.y - a[1]) * dy) / length2))
        if math.hypot(ball.x - (a[0] + s * dx), ball.y - (a[1] + s * dy)) < reach:
            return True
    return False


def pot_pockets(
    balls: Sequence[Ball],
    target: int,
    *,
    cue_in_hand: bool = False,
    max_cut_deg: float = PRACTICE_MAX_CUT_DEG,
    margin: float = PRACTICE_LINE_MARGIN_M,
) -> list[int]:
    """The pockets (indices into `POCKETS`, ascending) `target` could be shot into straight, see
    the module docstring."""
    ball = next((b for b in balls if b.number == target and b.in_play), None)
    cue = next((b for b in balls if b.number == CUE), None)
    if ball is None or (cue is None and not cue_in_hand):
        return []
    others = [b for b in balls if b.in_play and b.number not in (CUE, target)]
    reach = 2 * BALL_R + margin
    cos_limit = math.cos(math.radians(max_cut_deg))
    pockets: list[int] = []
    for index, (px, py, _radius) in enumerate(POCKETS):
        # a ball's centre cannot go past the cushions: aim at the nearest centre that can drop in
        aim = (min(max(px, BALL_R), TABLE_L - BALL_R), min(max(py, BALL_R), TABLE_W - BALL_R))
        vx, vy = aim[0] - ball.x, aim[1] - ball.y
        dist = math.hypot(vx, vy)
        if dist == 0.0:
            pockets.append(index)
            continue
        dx, dy = vx / dist, vy / dist
        ghost = (ball.x - 2 * BALL_R * dx, ball.y - 2 * BALL_R * dy)
        if not (BALL_R <= ghost[0] <= TABLE_L - BALL_R and BALL_R <= ghost[1] <= TABLE_W - BALL_R):
            continue
        if _near_segment(others, (ball.x, ball.y), aim, reach):
            continue
        if cue_in_hand or cue is None:
            if _near_segment(others, ghost, ghost, reach):
                continue
        else:
            ux, uy = ghost[0] - cue.x, ghost[1] - cue.y
            travel = math.hypot(ux, uy)
            if travel > 0.0 and (ux * dx + uy * dy) / travel < cos_limit:
                continue
            if _near_segment(others, (cue.x, cue.y), ghost, reach):
                continue
        pockets.append(index)
    return pockets


def pot_lines(
    balls: Sequence[Ball],
    target: int,
    *,
    cue_in_hand: bool = False,
    max_cut_deg: float = PRACTICE_MAX_CUT_DEG,
    margin: float = PRACTICE_LINE_MARGIN_M,
) -> int:
    """How many pockets `target` could be shot into straight (0..6): `len(pot_pockets(...))`."""
    return len(
        pot_pockets(balls, target, cue_in_hand=cue_in_hand, max_cut_deg=max_cut_deg, margin=margin)
    )
