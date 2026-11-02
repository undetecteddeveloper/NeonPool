"""Practice "the Ghost": a solo pressure drill, brief docs/plans/20261102-luyen-tap.md.

Pure (no pygame). One ball at a time is the TARGET, picked at random among the balls still on the
table. A shot succeeds when the target goes into a pocket (what the cue ball touches first does
not matter, a bank or a combination is as good as a straight shot); the next target is then
picked. A shot that does not pot the target, the cue ball going into a pocket (it is then in
hand), or the shot's clock running out each cost one of the lives; with none left the run is
lost; with no ball left on the table it is won.
"""

from __future__ import annotations

import random
from collections.abc import Iterable
from dataclasses import dataclass

from game.config import PRACTICE_LIVES
from game.physics.world import CUE, BallPocketed, Event
from game.rules.eight_ball import FOUL_SCRATCH, LOST, PLAYING, WON

MISS = "practice.miss"  # the target did not go into a pocket
LOST_TIMEOUT = "practice.lost_timeout"  # the shot's clock reached zero before a shot was taken
BALLS = frozenset(range(1, 16))


@dataclass(frozen=True)
class ShotResult:
    hit: bool = False  # the target went into a pocket (and the cue ball did not)
    pocketed: tuple[int, ...] = ()  # object balls this shot pocketed, in order
    lost_life: str | None = None  # why a life was lost: FOUL_SCRATCH, MISS or LOST_TIMEOUT
    outcome: str | None = None  # None | WON | LOST


class GhostRun:
    def __init__(self, rng: random.Random | None = None) -> None:
        self._rng = rng or random.Random(0)  # the world's, in the game: nothing else is random
        self.reset()

    def reset(self) -> None:
        self.shots = 0
        self.streak = 0  # targets potted in this run (0..15)
        self.lives = PRACTICE_LIVES
        self.pocketed: set[int] = set()
        self.phase = PLAYING
        self.cue_in_hand = False  # after the cue ball went into a pocket
        self.last: ShotResult | None = None
        self.target: int | None = self._pick()
        self._begin_record()

    # --- state the screen shows ------------------------------------------------------------
    @property
    def balls_left(self) -> int:
        return 15 - len(self.pocketed)

    def _pick(self) -> int | None:
        left = sorted(BALLS - self.pocketed)
        return self._rng.choice(left) if left else None

    # --- one shot ----------------------------------------------------------------------------
    def _begin_record(self) -> None:
        self._down: list[int] = []
        self._cue_down = False
        self._live = False

    def on_shot(self) -> None:
        self.shots += 1
        self._begin_record()
        self._live = True
        self.cue_in_hand = False
        self.last = None

    def on_events(self, events: Iterable[Event]) -> None:
        for ev in events:
            if isinstance(ev, BallPocketed):
                if ev.ball == CUE:
                    self._cue_down = True
                else:
                    self._down.append(ev.ball)
                    self.pocketed.add(ev.ball)

    def cue_placed(self) -> None:
        self.cue_in_hand = False

    def finish_shot(self) -> ShotResult:
        """Judge the shot that just ended (call once, when every ball has stopped)."""
        if not self._live:
            return ShotResult()
        self._live = False
        down = tuple(self._down)
        hit = False
        lost = None
        if self._cue_down:
            lost = FOUL_SCRATCH
            self.cue_in_hand = True
        elif self.target in down:
            hit = True
            self.streak += 1
        else:
            lost = MISS
        return self._settle(ShotResult(hit, down, lost), target_gone=self.target in down)

    def timeout(self) -> ShotResult:
        """The shot's clock reached zero with no shot taken: a life is lost, like a miss."""
        return self._settle(ShotResult(lost_life=LOST_TIMEOUT), target_gone=False)

    def _settle(self, res: ShotResult, *, target_gone: bool) -> ShotResult:
        """Take the life, decide the run's end, pick the next target."""
        if res.lost_life:
            self.lives -= 1
        outcome = None
        if self.lives <= 0:
            outcome = LOST
        elif not BALLS - self.pocketed:
            outcome = WON
        if outcome:
            self.phase = outcome
            self.cue_in_hand = False
            self.target = None if outcome == WON else self.target
        elif target_gone:
            self.target = self._pick()
        self.last = ShotResult(res.hit, res.pocketed, res.lost_life, outcome)
        return self.last
