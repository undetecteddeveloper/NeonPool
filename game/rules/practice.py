"""Practice "the Ghost": a solo pressure drill, brief docs/plans/20261102-luyen-tap.md.

Pure (no pygame). One ball at a time is the TARGET, picked at random among the balls still on the
table that the cue ball can draw a straight line to (docs/GAME_DESIGN.md round 37): a target
another ball sits directly in front of is never picked, so no run can lose a life to a shot that
was never possible in the first place. A shot succeeds when the target goes into a pocket
(what the cue ball touches first does not matter, a bank or a combination is as good as a straight
shot); the next target is then picked. A shot that does not pot the target, the cue ball going into
a pocket (it is then in hand), or the shot's clock running out each cost one of the lives; with
none left the run is lost; with no ball left on the table it is won. A target that survives a miss
is kept for the next shot unless the balls that moved now block it, in which case it is swapped for
an open one at no extra cost.

The opening break is the exception (docs/GAME_DESIGN.md round 38): nothing is called while the
balls still sit racked, so there is nothing to miss — the first real target is picked only once the
break has scattered them. A scratch on the break still costs a life as normal; stalling past the
shot's clock before it is even fired also does, but leaves the table untouched and still waiting.
"""

from __future__ import annotations

import random
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from game.config import PRACTICE_LIVES
from game.physics.raycast import first_contact
from game.physics.world import CUE, Ball, BallPocketed, Event
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
        self.target_swapped = False  # the last target change was a swap away from a blocked ball
        self.target: int | None = None  # nothing is called while the break still sits racked
        self._begin_record()

    # --- state the screen shows ------------------------------------------------------------
    @property
    def balls_left(self) -> int:
        return 15 - len(self.pocketed)

    def _pick(self, balls: Sequence[Ball] | None = None) -> int | None:
        left = sorted(BALLS - self.pocketed)
        if not left or balls is None:
            return self._rng.choice(left) if left else None
        open_left = [n for n in left if self._open(balls, n)]
        return self._rng.choice(open_left or left)

    def _open(self, balls: Sequence[Ball], target_num: int) -> bool:
        """Can the cue ball draw a straight line to this ball before touching another?"""
        cue = next((b for b in balls if b.number == CUE), None)
        target = next((b for b in balls if b.number == target_num), None)
        if cue is None or target is None:
            return False
        direction = (target.x - cue.x, target.y - cue.y)
        if direction == (0.0, 0.0):
            return True
        contact = first_contact(balls, (cue.x, cue.y), direction)
        return contact.kind == "ball" and contact.ball == target_num

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

    def finish_shot(self, balls: Sequence[Ball] | None = None) -> ShotResult:
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
        elif self.target is None:
            pass  # the opening break: nothing was called, so there is nothing to miss
        elif self.target in down:
            hit = True
            self.streak += 1
        else:
            lost = MISS
        return self._settle(
            ShotResult(hit, down, lost), target_gone=self.target in down, balls=balls
        )

    def timeout(self, balls: Sequence[Ball] | None = None) -> ShotResult:
        """The shot's clock reached zero with no shot taken: a life is lost, like a miss. Before
        the break is even fired this still costs a life (stalling is still on the player), but the
        table has not moved, so no target is picked yet."""
        return self._settle(
            ShotResult(lost_life=LOST_TIMEOUT), target_gone=False, balls=balls, shot_fired=False
        )

    def _settle(
        self,
        res: ShotResult,
        *,
        target_gone: bool,
        balls: Sequence[Ball] | None = None,
        shot_fired: bool = True,
    ) -> ShotResult:
        """Take the life, decide the run's end, pick the next target (the first one once the break
        has actually been fired, or swap it for an open one if the balls that just moved now block
        it)."""
        if res.lost_life:
            self.lives -= 1
        outcome = None
        if self.lives <= 0:
            outcome = LOST
        elif not BALLS - self.pocketed:
            outcome = WON
        self.target_swapped = False
        if outcome:
            self.phase = outcome
            self.cue_in_hand = False
            self.target = None if outcome == WON else self.target
        elif target_gone or (self.target is None and shot_fired):
            self.target = self._pick(balls)
        elif balls is not None and self.target is not None and not self._open(balls, self.target):
            self.target = self._pick(balls)
            self.target_swapped = True
        self.last = ShotResult(res.hit, res.pocketed, res.lost_life, outcome)
        return self.last
