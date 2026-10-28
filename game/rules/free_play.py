"""Free play (MVP): count shots and balls left; no fouls, no win/lose. Pure (no pygame)."""

from __future__ import annotations

from collections.abc import Iterable

from game.physics.world import CUE, BallPocketed, Event


class FreePlay:
    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self.shots = 0
        self.pocketed: set[int] = set()
        self.cue_pocketed = False

    @property
    def balls_left(self) -> int:
        return 15 - len(self.pocketed)

    def on_shot(self) -> None:
        self.shots += 1

    def on_events(self, events: Iterable[Event]) -> None:
        for ev in events:
            if isinstance(ev, BallPocketed):
                if ev.ball == CUE:
                    self.cue_pocketed = True
                else:
                    self.pocketed.add(ev.ball)

    def take_cue_respawn(self) -> bool:
        """True once after the cue ball was pocketed: the caller must put it back."""
        was, self.cue_pocketed = self.cue_pocketed, False
        return was
