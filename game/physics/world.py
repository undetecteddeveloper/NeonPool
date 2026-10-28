"""Deterministic 2D pool world: fixed step, sub-stepped against tunnelling. Pure (no pygame).

Balls are numbered 0 (cue) .. 15 and `World.balls[n].number == n`.
Model (MVP): equal-mass discs, constant rolling deceleration, restitution on ball-ball and
cushion contacts, no spin. Order of every loop is by ball number, so results are reproducible.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass

from game.config import (
    BALL_R,
    DEFAULT_FEEL,
    FEEL_SETS,
    FOOT_SPOT,
    HEAD_SPOT,
    MAX_STEP_FRAC,
    MIN_EVENT_SPEED,
    PHYSICS_DT,
    POCKETS,
    RACK_GAP,
    RACK_ORDER,
    REST_SPEED,
    ROW_STEP,
    TABLE_L,
    TABLE_W,
    FeelSet,
)
from game.physics.shot import Shot

CUE = 0
N_BALLS = 16
_D = 2 * BALL_R
MAX_RELAX_PASSES = (
    16  # measured worst overlap in a full-power break: 4 passes 208 um, 16 passes 4 um
)


@dataclass(frozen=True)
class BallHitBall:
    a: int
    b: int
    speed: float  # approach speed along the contact normal, m/s


@dataclass(frozen=True)
class BallHitCushion:
    ball: int
    speed: float  # speed into the cushion, m/s


@dataclass(frozen=True)
class BallPocketed:
    ball: int
    pocket: int  # index into config.POCKETS


Event = BallHitBall | BallHitCushion | BallPocketed


@dataclass(slots=True)
class Ball:
    number: int
    x: float = 0.0
    y: float = 0.0
    vx: float = 0.0
    vy: float = 0.0
    in_play: bool = False
    pocket: int | None = None  # set when pocketed


class World:
    def __init__(self, seed: int = 0, feel: FeelSet | None = None, rack: bool = True) -> None:
        self.rng = random.Random(seed)  # the only randomness allowed in the simulation
        self.feel = feel or FEEL_SETS[DEFAULT_FEEL]
        self.balls = [Ball(n) for n in range(N_BALLS)]
        if rack:
            self.rack()

    # --- setup -------------------------------------------------------------------
    def rack(self) -> None:
        """Cue ball on the head spot, 15 balls in a triangle at the foot spot."""
        for b in self.balls:
            b.vx = b.vy = 0.0
            b.pocket = None
        self.place(CUE, *HEAD_SPOT)
        fx, fy = FOOT_SPOT
        i = 0
        for row in range(5):
            for k in range(row + 1):
                y = fy + (k - row / 2) * (_D + RACK_GAP)
                self.place(RACK_ORDER[i], fx + row * ROW_STEP, y)
                i += 1

    def place(self, number: int, x: float, y: float, vx: float = 0.0, vy: float = 0.0) -> None:
        b = self.balls[number]
        b.x, b.y, b.vx, b.vy = x, y, vx, vy
        b.in_play = True
        b.pocket = None

    def respawn_cue(self) -> tuple[float, float]:
        """Put the cue ball back: head spot, or the nearest free spot to its right."""
        hx, hy = HEAD_SPOT
        candidates = [(hx + k * BALL_R, hy) for k in range(int((TABLE_L - hx) / BALL_R))]
        for dy in (BALL_R * 2, -BALL_R * 2, BALL_R * 4, -BALL_R * 4):
            candidates += [(hx + k * BALL_R, hy + dy) for k in range(int((TABLE_L - hx) / BALL_R))]
        for x, y in candidates:
            if self._free(x, y):
                self.place(CUE, x, y)
                return x, y
        raise RuntimeError("no free spot for the cue ball")

    def _free(self, x: float, y: float) -> bool:
        if not (BALL_R <= x <= TABLE_L - BALL_R and BALL_R <= y <= TABLE_W - BALL_R):
            return False
        for b in self.balls[1:]:
            if b.in_play and (b.x - x) ** 2 + (b.y - y) ** 2 < (_D + 1e-6) ** 2:
                return False
        return True

    # --- acting on the world -------------------------------------------------------
    def apply(self, shot: Shot) -> None:
        cue = self.balls[CUE]
        if not cue.in_play:
            raise ValueError("cue ball is not in play")
        speed = self.feel.v_max * shot.power
        cue.vx = speed * math.cos(shot.angle)
        cue.vy = speed * math.sin(shot.angle)

    def at_rest(self) -> bool:
        return all(b.vx == 0.0 and b.vy == 0.0 for b in self.balls if b.in_play)

    def kinetic_energy(self) -> float:
        """Sum of 1/2 v^2 (unit mass); used by tests and tuning."""
        return sum(0.5 * (b.vx * b.vx + b.vy * b.vy) for b in self.balls if b.in_play)

    def in_play(self) -> list[Ball]:
        return [b for b in self.balls if b.in_play]

    # --- simulation ------------------------------------------------------------------
    def step(self) -> list[Event]:
        """Advance exactly PHYSICS_DT. Returns the events that happened, in order."""
        events: list[Event] = []
        vmax = max((math.hypot(b.vx, b.vy) for b in self.balls if b.in_play), default=0.0)
        n = max(1, math.ceil(vmax * PHYSICS_DT / (MAX_STEP_FRAC * BALL_R)))
        h = PHYSICS_DT / n
        for _ in range(n):
            self._substep(h, events)
        return events

    def _substep(self, h: float, events: list[Event]) -> None:
        feel = self.feel
        live = [b for b in self.balls if b.in_play]

        for b in live:
            s = math.hypot(b.vx, b.vy)
            if s > 0.0:
                s2 = s - feel.roll_decel * h
                if s2 < REST_SPEED:
                    b.vx = b.vy = 0.0
                else:
                    k = s2 / s
                    b.vx *= k
                    b.vy *= k
            b.x += b.vx * h
            b.y += b.vy * h

        # Pockets are checked before cushions so a ball near a mouth drops instead of bouncing.
        for b in live:
            for pi, (px, py, pr) in enumerate(POCKETS):
                if (b.x - px) ** 2 + (b.y - py) ** 2 < pr * pr:
                    b.in_play = False
                    b.pocket = pi
                    b.vx = b.vy = 0.0
                    events.append(BallPocketed(b.number, pi))
                    break
        live = [b for b in live if b.in_play]

        for b in live:
            self._cushions(b, events)

        # Pairs are resolved one after another, so a later pair can push an earlier one back
        # into overlap (dense cluster at the break). Repeat until nothing overlaps.
        for _ in range(MAX_RELAX_PASSES):
            touched = False
            for i in range(len(live)):
                a = live[i]
                for j in range(i + 1, len(live)):
                    if self._ball_pair(a, live[j], events):
                        touched = True
            if not touched:
                break

    def _cushions(self, b: Ball, events: list[Event]) -> None:
        e = self.feel.cushion_e
        lo_x, hi_x = BALL_R, TABLE_L - BALL_R
        lo_y, hi_y = BALL_R, TABLE_W - BALL_R
        if b.x < lo_x:
            b.x = lo_x
            if b.vx < 0.0:
                self._cushion_event(b, -b.vx, events)
                b.vx = -b.vx * e
        elif b.x > hi_x:
            b.x = hi_x
            if b.vx > 0.0:
                self._cushion_event(b, b.vx, events)
                b.vx = -b.vx * e
        if b.y < lo_y:
            b.y = lo_y
            if b.vy < 0.0:
                self._cushion_event(b, -b.vy, events)
                b.vy = -b.vy * e
        elif b.y > hi_y:
            b.y = hi_y
            if b.vy > 0.0:
                self._cushion_event(b, b.vy, events)
                b.vy = -b.vy * e

    @staticmethod
    def _cushion_event(b: Ball, speed: float, events: list[Event]) -> None:
        if speed > MIN_EVENT_SPEED:
            events.append(BallHitCushion(b.number, speed))

    def _ball_pair(self, a: Ball, b: Ball, events: list[Event]) -> bool:
        """Resolve one pair; True if they were overlapping."""
        dx = b.x - a.x
        if dx >= _D or dx <= -_D:
            return False
        dy = b.y - a.y
        d2 = dx * dx + dy * dy
        if d2 >= _D * _D:
            return False
        d = math.sqrt(d2)
        if d < 1e-12:
            nx, ny, d = 1.0, 0.0, 0.0
        else:
            nx, ny = dx / d, dy / d
        push = (_D - d) / 2
        a.x -= nx * push
        a.y -= ny * push
        b.x += nx * push
        b.y += ny * push
        vn = (a.vx - b.vx) * nx + (a.vy - b.vy) * ny
        if vn > 0.0:
            j = (1.0 + self.feel.ball_e) * vn / 2
            a.vx -= j * nx
            a.vy -= j * ny
            b.vx += j * nx
            b.vy += j * ny
            if vn > MIN_EVENT_SPEED:
                events.append(BallHitBall(a.number, b.number, vn))
        return True
