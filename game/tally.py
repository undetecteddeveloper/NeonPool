"""The numbers on the result card counting up, one after the other. No pygame here.

`Tally` is only a clock: given the final numbers and how long ago the card opened, it says what
each number shows now, how many ticks have sounded and whether it has stopped. The card draws
from it and the table scene plays the sounds from it, so what you see and what you hear always
agree.
"""

from __future__ import annotations

from game.config import (
    TALLY_FLASH_S,
    TALLY_GAP_S,
    TALLY_MAX_TICKS,
    TALLY_SPANS,
    TALLY_START_S,
)


def _ease(u: float) -> float:
    """Fast at first, slowing down to a stop (the number settles instead of hitting a wall)."""
    return 1 - (1 - u) ** 3


class Tally:
    def __init__(self, targets: dict[str, int]) -> None:
        self.targets = {name: max(0, targets[name]) for name, _ in TALLY_SPANS}
        self._span: dict[str, tuple[float, float]] = {}  # name -> (starts at, seconds)
        at = TALLY_START_S
        for name, seconds in TALLY_SPANS:
            self._span[name] = (at, seconds)
            at += seconds + TALLY_GAP_S

    @property
    def total_s(self) -> float:
        """When the last number has stopped (seconds after the game ended)."""
        start, seconds = self._span[TALLY_SPANS[-1][0]]
        return start + seconds

    def progress(self, name: str, age: float) -> float:
        """0 before the number starts, 1 once it has stopped (linear in time)."""
        start, seconds = self._span[name]
        return min(1.0, max(0.0, (age - start) / seconds))

    def value(self, name: str, age: float) -> int:
        return round(self.targets[name] * _ease(self.progress(name, age)))

    def finished(self, name: str, age: float) -> bool:
        return self.progress(name, age) >= 1.0

    def _tick_count(self, name: str) -> int:
        return min(self.targets[name], TALLY_MAX_TICKS)

    def ticks_done(self, name: str, age: float) -> int:
        """How many ticks of this number have sounded. They are spaced by VALUE, not by time, so
        they come quickly while the number races and slow down as it settles."""
        n, u = self._tick_count(name), self.progress(name, age)
        if n == 0:
            return 0
        done = 0
        for k in range(1, n + 1):
            if u >= 1 - (1 - k / n) ** (1 / 3):  # the moment the eased value reaches k/n
                done = k
        return done

    def tick_pitch(self, name: str, ticks: int) -> float:
        """0..1: how far up the scale the tick number `ticks` is (rising as the number climbs)."""
        n = self._tick_count(name)
        return (ticks - 1) / max(1, n - 1)

    def flash(self, name: str, age: float) -> float:
        """1 at the moment a number stops, fading to 0 over TALLY_FLASH_S (0 while it counts)."""
        start, seconds = self._span[name]
        since = age - (start + seconds)
        if since < 0 or self.targets[name] == 0:
            return 0.0
        return max(0.0, 1.0 - since / TALLY_FLASH_S)

    def counting(self, name: str, age: float) -> bool:
        return 0.0 < self.progress(name, age) < 1.0
