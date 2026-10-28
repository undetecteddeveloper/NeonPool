"""8-ball rules for solo practice: groups, fouls, win/lose. Shared by both input modes.

Pure (no pygame): it only reads the physics events. `finish_shot()` judges a whole shot once
every ball has stopped. The rules the player chose are in docs/plans/20261028-8ball.md.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from game.physics.world import CUE, BallHitBall, BallHitCushion, BallPocketed, Event

PLAYING, WON, LOST = "playing", "won", "lost"  # EightBall.phase
RERACK = "rerack"  # ShotResult.outcome only: the 8 went down on the break
SOLID, STRIPE = "solid", "stripe"
EIGHT = 8
SOLIDS = frozenset(range(1, 8))
STRIPES = frozenset(range(9, 16))

# i18n keys: what went wrong, and why the game was lost
FOUL_SCRATCH = "foul.scratch"  # the cue ball went into a pocket
FOUL_NO_HIT = "foul.no_hit"  # the cue ball touched nothing
FOUL_WRONG_BALL = "foul.wrong_ball"  # the first ball it touched was not allowed
FOUL_NO_CUSHION = "foul.no_cushion"  # after contact: nothing pocketed and no ball reached a cushion
LOST_EARLY = "result.lost_early"  # the 8 went down with balls of the group left (or table open)
LOST_FOUL = "result.lost_foul"  # the 8 went down in a shot with a foul


@dataclass(frozen=True)
class ShotResult:
    fouls: tuple[str, ...] = ()  # reasons, most important first (one foul point per shot)
    pocketed: tuple[int, ...] = ()  # object balls this shot pocketed, in order
    group: str | None = None  # the group this shot decided, if any
    outcome: str | None = None  # None | WON | LOST | RERACK
    reason: str | None = None  # why the game was lost


class EightBall:
    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self.shots = 0
        self.fouls = 0
        self.pocketed: set[int] = set()
        self.group: str | None = None
        self.phase = PLAYING
        self.cue_in_hand = False  # after a foul the player places the cue ball
        self.is_break = True  # the next shot is the break
        self.last: ShotResult | None = None
        self._begin_record()

    def rerack(self) -> None:
        """The 8 went down on the break: the caller racks again. Shots and fouls are kept."""
        self.pocketed = set()
        self.group = None
        self.is_break = True
        self.cue_in_hand = False
        self._begin_record()

    # --- state the screen shows ------------------------------------------------------------
    @property
    def balls_left(self) -> int:
        return 15 - len(self.pocketed)

    def _group_set(self) -> frozenset[int]:
        return {SOLID: SOLIDS, STRIPE: STRIPES}.get(self.group, frozenset())

    def group_left(self) -> int | None:
        """Balls of the player's group still on the table (None while the table is open)."""
        if self.group is None:
            return None
        return len(self._group_set() - self.pocketed)

    def eight_is_next(self) -> bool:
        return self.group_left() == 0 and EIGHT not in self.pocketed

    # --- one shot ----------------------------------------------------------------------------
    def _begin_record(self) -> None:
        self._before = frozenset(self.pocketed)  # the table as it was when the shot began
        self._first_hit: int | None = None
        self._cushion = False  # a ball reached a cushion AFTER the cue ball's first contact
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

    def cue_placed(self) -> None:
        self.cue_in_hand = False

    def finish_shot(self) -> ShotResult:
        """Judge the shot that just ended (call once, when every ball has stopped)."""
        if not self._live:
            return ShotResult()
        self._live = False
        was_break, self.is_break = self.is_break, False
        down = tuple(self._down)
        fouls = self._fouls(down)
        group = outcome = reason = None
        if EIGHT in down:
            outcome, reason = self._eight(fouls, was_break)
        elif self.group is None and not was_break and not fouls and down:
            group = self.group = SOLID if down[0] in SOLIDS else STRIPE
        if outcome == RERACK:
            fouls = ()  # no penalty: the caller racks again
        else:
            if fouls:
                self.fouls += 1
                self.cue_in_hand = True
            if outcome in (WON, LOST):
                self.phase = outcome
                self.cue_in_hand = False
        self.last = ShotResult(fouls, down, group, outcome, reason)
        return self.last

    def _fouls(self, down: tuple[int, ...]) -> tuple[str, ...]:
        fouls = []
        if self._cue_down:
            fouls.append(FOUL_SCRATCH)
        if self._first_hit is None:
            fouls.append(FOUL_NO_HIT)
        else:
            if not self._legal_first(self._first_hit):
                fouls.append(FOUL_WRONG_BALL)
            if not (self._cushion or down):
                fouls.append(FOUL_NO_CUSHION)
        return tuple(fouls)

    def _cleared_before(self) -> bool:
        """The player's whole group was already down when this shot began."""
        return self.group is not None and not (self._group_set() - self._before)

    def _legal_first(self, ball: int) -> bool:
        if self.group is None:
            return ball != EIGHT  # an open table: any ball but the 8
        if ball == EIGHT:
            return self._cleared_before()
        return ball in self._group_set()

    def _eight(self, fouls: tuple[str, ...], was_break: bool) -> tuple[str, str | None]:
        if was_break:
            return RERACK, None
        if fouls:
            return LOST, LOST_FOUL
        if not self._cleared_before():
            return LOST, LOST_EARLY
        return WON, None
