"""Aiming with the mouse. Pure (no pygame): the scene feeds it pointer positions.

Two parts, both ending in one `Shot`:
- `Knob`: while the pointer is on the cue ball (nothing pressed), going round the ball's centre
  turns the cue like a dial, one turn of the pointer for one turn of the cue.
- `DragAim`: press, pull, release. The shot goes the opposite way to the pull, from wherever on
  the ball the press was, so the aim is free to change all through the pull.
Works in logical screen pixels (same orientation as table coordinates, so angles carry over).
"""

from __future__ import annotations

import math

from game.config import AIM_MIN_PX, KNOB_DEAD_PX, MAX_DRAG_PX, MIN_PULL_PX, POWER_CURVE
from game.physics.shot import Shot


def wrap_angle(a: float) -> float:
    """The same angle in (-pi, pi]."""
    return math.atan2(math.sin(a), math.cos(a))


class Knob:
    """The cue as a dial round the cue ball: `angle` is where the shot would go."""

    def __init__(self, angle: float = 0.0) -> None:
        self.angle = angle
        self._last: float | None = None  # the pointer's angle round the ball at the last move

    def release(self) -> None:
        """The pointer left the ball: the next touch starts a new turn (no jump)."""
        self._last = None

    def move(self, centre: tuple[float, float], pointer: tuple[float, float]) -> float:
        """The pointer moved on the ball: turn by as much as it went round. Returns the turn."""
        dx, dy = pointer[0] - centre[0], pointer[1] - centre[1]
        if math.hypot(dx, dy) < KNOB_DEAD_PX:  # too close to the centre: its angle means nothing
            self._last = None
            return 0.0
        a = math.atan2(dy, dx)
        turn = 0.0 if self._last is None else wrap_angle(a - self._last)
        self._last = a
        self.angle = wrap_angle(self.angle + turn)
        return turn


class DragAim:
    def __init__(self) -> None:
        self.active = False
        self._press = (0.0, 0.0)
        self._pointer = (0.0, 0.0)

    def begin(self, pointer_px: tuple[float, float]) -> None:
        """Start pulling from where the pointer is now."""
        self.active = True
        self._press = pointer_px
        self._pointer = pointer_px

    def move(self, pointer_px: tuple[float, float]) -> None:
        if self.active:
            self._pointer = pointer_px

    def cancel(self) -> None:
        self.active = False

    @property
    def pointer(self) -> tuple[float, float]:
        return self._pointer

    @property
    def pull(self) -> float:
        """Pull distance in logical pixels, from where the press was."""
        return math.hypot(self._press[0] - self._pointer[0], self._press[1] - self._pointer[1])

    @property
    def bar_length(self) -> float:
        """How far the pull counts: grows with the pull, never beyond full power."""
        return min(self.pull, MAX_DRAG_PX) if self.active else 0.0

    @property
    def has_direction(self) -> bool:
        return self.active and self.pull >= AIM_MIN_PX

    @property
    def angle(self) -> float:
        """Shooting direction: away from the pull (only means something once `has_direction`)."""
        return math.atan2(self._press[1] - self._pointer[1], self._press[0] - self._pointer[0])

    @property
    def power(self) -> float:
        return min(1.0, self.pull / MAX_DRAG_PX) ** POWER_CURVE if self.active else 0.0

    def end(self, spin: float = 0.0) -> Shot | None:
        """Release: the Shot (struck at `spin`, -1 low .. +1 high), or None if the pull was too
        weak (counts as cancel)."""
        shot = None
        if self.has_direction and self.pull >= MIN_PULL_PX:
            shot = Shot(self.angle, self.power, spin)
        self.active = False
        return shot
