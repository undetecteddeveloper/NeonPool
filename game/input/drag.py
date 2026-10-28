"""Drag-back aiming: press the cue ball, pull away from the target, release to shoot.

Works in logical screen pixels (same orientation as table coordinates, so angles carry over).
Pure (no pygame): the scene feeds it pointer positions.
"""

from __future__ import annotations

import math

from game.config import AIM_MIN_PX, MAX_DRAG_PX, MIN_POWER
from game.physics.shot import Shot


class DragAim:
    def __init__(self) -> None:
        self.active = False
        self._cue = (0.0, 0.0)
        self._pointer = (0.0, 0.0)

    def begin(self, cue_px: tuple[float, float], pointer_px: tuple[float, float]) -> None:
        self.active = True
        self._cue = cue_px
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
        """Pull-back distance in logical pixels."""
        return math.hypot(self._cue[0] - self._pointer[0], self._cue[1] - self._pointer[1])

    @property
    def has_direction(self) -> bool:
        return self.active and self.pull >= AIM_MIN_PX

    @property
    def angle(self) -> float:
        """Shooting direction: from the pointer through the cue ball."""
        return math.atan2(self._cue[1] - self._pointer[1], self._cue[0] - self._pointer[0])

    @property
    def power(self) -> float:
        return min(1.0, self.pull / MAX_DRAG_PX) if self.active else 0.0

    def end(self) -> Shot | None:
        """Release: the Shot, or None if the pull was too weak (counts as cancel)."""
        shot = None
        if self.has_direction and self.power >= MIN_POWER:
            shot = Shot(self.angle, self.power)
        self.active = False
        return shot
