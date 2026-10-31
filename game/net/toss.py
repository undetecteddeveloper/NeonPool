"""The start of a game as a timeline of seconds (pure): a look at the table, the coin waits, it
spins, it lies there. Both machines and the scene read the same numbers, so nobody can shoot
earlier on one machine than on the other. Times are in game/config.py (NET_TOSS_*)."""

from __future__ import annotations

import math
from dataclasses import dataclass

from game import config

LEAD, HOLD, FLIP, LAND, DONE = "lead", "hold", "flip", "land", "done"


def total_s(again: bool) -> float:
    """How long a game's start lasts; `again`: it is a rematch, not the first game of the room."""
    lead = config.NET_TOSS_LEAD_AGAIN_S if again else config.NET_TOSS_LEAD_S
    return lead + config.NET_TOSS_HOLD_S + config.NET_TOSS_FLIP_S + config.NET_TOSS_LAND_S


@dataclass(frozen=True)
class Toss:
    again: bool
    breaker: int  # who the coin lands on: 0 = the host

    @property
    def lead_s(self) -> float:
        return config.NET_TOSS_LEAD_AGAIN_S if self.again else config.NET_TOSS_LEAD_S

    @property
    def flip_at(self) -> float:
        return self.lead_s + config.NET_TOSS_HOLD_S

    @property
    def land_at(self) -> float:
        return self.flip_at + config.NET_TOSS_FLIP_S

    @property
    def total_s(self) -> float:
        return total_s(self.again)

    def breaker_known(self, age: float) -> bool:
        """The coin has landed: from here on the screen may show who breaks (the plate lights, the
        words and the sound). The rules chose the breaker at the start; the screen keeps it back."""
        return age >= self.land_at

    def phase(self, age: float) -> str:
        if age < self.lead_s:
            return LEAD
        if age < self.flip_at:
            return HOLD
        if age < self.land_at:
            return FLIP
        return LAND if age < self.total_s else DONE

    def dim(self, age: float) -> float:
        """How dark the table is, 0 (as it is) .. 1: it darkens at the end of the lead and lights
        up again at the end of the landing."""
        d = config.NET_TOSS_DIM_S
        if age < self.total_s - d:
            return max(0.0, min(1.0, (age - (self.lead_s - d)) / d))
        return max(0.0, min(1.0, (self.total_s - age) / d))

    def spin(self, age: float) -> float:
        """The angle of the coin (radians): fast at first, slowing, and it stops face-on showing
        the breaker (3 to 3.5 turns)."""
        end = math.pi * (6 + self.breaker)
        if age <= self.flip_at:
            return 0.0
        k = min(1.0, (age - self.flip_at) / config.NET_TOSS_FLIP_S)
        return end * (1 - (1 - k) ** 3)

    def hop(self, age: float) -> float:
        """How high the coin is, 0 (on the table) .. 1 (the top of its throw)."""
        if not self.flip_at < age < self.land_at:
            return 0.0
        k = (age - self.flip_at) / config.NET_TOSS_FLIP_S
        return 4 * k * (1 - k)

    def faces_seen(self, age: float) -> int:
        """How many times the coin has turned over (a half turn each) by `age`."""
        return int(self.spin(age) / math.pi + 0.5)
