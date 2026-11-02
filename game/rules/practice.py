"""Practice "the Ghost": a solo pressure drill, brief docs/plans/20261102-luyen-tap.md.

Pure (no pygame). Pot the 15 balls strictly in order (1, then the lowest still left, ...): any
foul, or the shot's clock running out, ends the run at once -- there is no ball in hand, no
rerack. The foul checks are the same shape as `rules.eight_ball.EightBall` (scratch / no contact
at all / the wrong ball touched first / nothing happened after a legal touch), only "legal first
ball" is always the single lowest ball left, never a group.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from game.physics.world import CUE, BallHitBall, BallHitCushion, BallPocketed, Event
from game.rules.eight_ball import (
    FOUL_NO_CUSHION,
    FOUL_NO_HIT,
    FOUL_SCRATCH,
    FOUL_WRONG_BALL,
    LOST,
    PLAYING,
    WON,
)

LOST_TIMEOUT = "practice.lost_timeout"  # the shot's clock reached zero before a shot was taken
BALLS = frozenset(range(1, 16))


@dataclass(frozen=True)
class ShotResult:
    fouls: tuple[str, ...] = ()  # at most one foul is ever reported (the first found)
    pocketed: tuple[int, ...] = ()  # object balls this shot pocketed, in order
    outcome: str | None = None  # None | WON | LOST
    reason: str | None = None  # why the run ended (a foul key, or LOST_TIMEOUT)


class GhostRun:
    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self.shots = 0
        self.pocketed: set[int] = set()
        self.phase = PLAYING
        self.last: ShotResult | None = None
        self._begin_record()

    # --- state the screen shows ------------------------------------------------------------
    @property
    def target(self) -> int | None:
        """The one ball that must be touched first this shot; None once all 15 are gone."""
        left = BALLS - self.pocketed
        return min(left) if left else None

    @property
    def streak(self) -> int:
        """Balls pocketed so far, in a row: the run's score (0..15)."""
        return len(self.pocketed)

    @property
    def balls_left(self) -> int:
        return 15 - len(self.pocketed)

    # --- one shot ----------------------------------------------------------------------------
    def _begin_record(self) -> None:
        self._target_at_start = self.target
        self._first_hit: int | None = None
        self._cushion = False  # a ball reached a cushion AFTER the cue ball's first contact
        self._down: list[int] = []
        self._cue_down = False
        self._live = False

    def on_shot(self) -> None:
        self.shots += 1
        self._begin_record()
        self._live = True
        self.last = None

    def on_events(self, events: Iterable[Event]) -> None:
        for ev in events:
            if isinstance(ev, BallHitBall):
                if self._first_hit is None and CUE in (ev.a, ev.b):
                    self._first_hit = ev.b if ev.a == CUE else ev.a
            elif isinstance(ev, BallHitCushion):
                if self._first_hit is not None:
                    self._cushion = True
            elif isinstance(ev, BallPocketed):
                if ev.ball == CUE:
                    self._cue_down = True
                else:
                    self._down.append(ev.ball)
                    self.pocketed.add(ev.ball)

    def finish_shot(self) -> ShotResult:
        """Judge the shot that just ended (call once, when every ball has stopped)."""
        if not self._live:
            return ShotResult()
        self._live = False
        down = tuple(self._down)
        fouls = self._fouls()
        if fouls:
            self.phase = LOST
            self.last = ShotResult(fouls, down, LOST, fouls[0])
        elif self.target is None:  # the 15th ball just went down: the whole rack is clear
            self.phase = WON
            self.last = ShotResult(fouls, down, WON, None)
        else:
            self.last = ShotResult(fouls, down)
        return self.last

    def _fouls(self) -> tuple[str, ...]:
        fouls = []
        if self._cue_down:
            fouls.append(FOUL_SCRATCH)
        if self._first_hit is None:
            fouls.append(FOUL_NO_HIT)
        elif self._first_hit != self._target_at_start:
            fouls.append(FOUL_WRONG_BALL)
        elif not (self._cushion or self._down):
            fouls.append(FOUL_NO_CUSHION)
        return tuple(fouls)

    def timeout(self) -> ShotResult:
        """The shot's clock reached zero with no shot taken: the run ends, like a foul."""
        self.phase = LOST
        self.last = ShotResult(outcome=LOST, reason=LOST_TIMEOUT)
        return self.last
