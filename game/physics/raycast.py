"""Aim line: where does the cue ball first touch something? Pure (no pygame)."""

from __future__ import annotations

import math
from dataclasses import dataclass

from game.config import BALL_R, TABLE_L, TABLE_W
from game.physics.world import CUE, Ball


@dataclass(frozen=True)
class Contact:
    kind: str  # "ball" or "cushion"
    distance: float  # how far the cue ball centre travels before contact
    point: tuple[float, float]  # cue ball centre at contact
    ball: int | None = None  # number of the ball hit (kind == "ball")
    object_dir: tuple[float, float] | None = None  # unit direction that ball is pushed


def first_contact(
    balls: list[Ball], origin: tuple[float, float], direction: tuple[float, float]
) -> Contact:
    """Cast the cue ball's centre from `origin` along `direction` (need not be unit length)."""
    ox, oy = origin
    length = math.hypot(*direction)
    if length == 0.0:
        raise ValueError("direction must be non-zero")
    dx, dy = direction[0] / length, direction[1] / length

    best_t = math.inf
    best_ball: Ball | None = None

    for t in (_wall_t(ox, dx, BALL_R, TABLE_L - BALL_R), _wall_t(oy, dy, BALL_R, TABLE_W - BALL_R)):
        best_t = min(best_t, t)

    reach = 2 * BALL_R
    for b in balls:
        if b.number == CUE or not b.in_play:
            continue
        rx, ry = ox - b.x, oy - b.y
        bq = rx * dx + ry * dy
        cq = rx * rx + ry * ry - reach * reach
        if cq <= 0.0:  # already touching / overlapping
            t = 0.0 if bq < 0.0 else math.inf
        else:
            disc = bq * bq - cq
            if disc < 0.0:
                continue
            t = -bq - math.sqrt(disc)
            if t < 0.0:
                continue
        if t < best_t:
            best_t, best_ball = t, b

    point = (ox + dx * best_t, oy + dy * best_t)
    if best_ball is None:
        return Contact("cushion", best_t, point)
    ndx, ndy = best_ball.x - point[0], best_ball.y - point[1]
    nlen = math.hypot(ndx, ndy) or 1.0
    return Contact("ball", best_t, point, best_ball.number, (ndx / nlen, ndy / nlen))


def _wall_t(o: float, d: float, lo: float, hi: float) -> float:
    if d > 0.0:
        return max(0.0, (hi - o) / d)
    if d < 0.0:
        return max(0.0, (lo - o) / d)
    return math.inf
