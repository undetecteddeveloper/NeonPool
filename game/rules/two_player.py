"""Two-player 8-ball: whose turn it is, each player's group, who wins. Pure (no pygame).

A `Match` wraps ONE `EightBall` that judges every shot (fouls, the 8, the break), so the rules of
a foul or of the 8 are exactly the ones of solo practice. Before each shot the judge is given the
group of the player on turn; after it, the Match decides what the result means for the two:

- a foul: the turn passes and the other player has the cue ball in hand;
- a legal pocket of the shooter's own group (or any ball while the table is open): shoot again;
- anything else (a miss, or only the other group's balls went down): the turn passes;
- the 8 pocketed: the shooter wins or loses (see `EightBall`); on the break the table is racked
  again and the same player breaks.

Player 0 is the room's host, who alone calls `finish_shot` (the referee); the guest's copy is
brought up to date from a `MatchState` (`snapshot` / `load`). See GAME_DESIGN.md (network play).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from game.physics.world import Event
from game.rules.eight_ball import (
    FOUL_NO_CUSHION,
    FOUL_NO_HIT,
    FOUL_SCRATCH,
    FOUL_WRONG_BALL,
    LOST,
    LOST_EARLY,
    LOST_FOUL,
    RERACK,
    SOLID,
    SOLIDS,
    STRIPE,
    STRIPES,
    WON,
    EightBall,
)

PLAYERS = 2
OPPOSITE = {SOLID: STRIPE, STRIPE: SOLID}
# small codes for the wire (game/net/protocol.py): the index of a value is its code
GROUPS = (None, SOLID, STRIPE)
FOULS = (FOUL_SCRATCH, FOUL_NO_HIT, FOUL_WRONG_BALL, FOUL_NO_CUSHION)
REASONS = (None, LOST_EARLY, LOST_FOUL)
OUTCOMES = (None, WON, LOST, RERACK)


@dataclass(frozen=True)
class MatchShot:
    """What one shot (or a lost turn) decided, seen from the player who took it."""

    shooter: int
    fouls: tuple[str, ...] = ()
    pocketed: tuple[int, ...] = ()
    group: str | None = None  # the group the shooter was given by this shot
    outcome: str | None = None  # None | WON | LOST | RERACK, the shooter's own result
    reason: str | None = None  # why the shooter lost
    timed_out: bool = False  # the turn was lost to the clock, no shot was taken


@dataclass(frozen=True)
class MatchState:
    """Everything the screen and the next shot need; this is what the referee sends."""

    turn: int
    groups: tuple[str | None, str | None]
    cue_in_hand: bool
    over: bool
    winner: int | None
    is_break: bool
    pocketed: frozenset[int]
    shots: tuple[int, int]
    fouls: tuple[int, int]
    last: MatchShot | None


class Match:
    def __init__(self, breaker: int = 0) -> None:
        self._judge = EightBall()
        self.reset(breaker)

    def reset(self, breaker: int = 0) -> None:
        self._judge.reset()
        self.turn = breaker
        self.groups: list[str | None] = [None, None]
        self.cue_in_hand = False
        self.over = False
        self.winner: int | None = None
        self.shots = [0, 0]
        self.fouls = [0, 0]
        self.last: MatchShot | None = None

    # --- state the screen shows ----------------------------------------------------------------
    @property
    def pocketed(self) -> set[int]:
        return self._judge.pocketed

    @property
    def is_break(self) -> bool:
        return self._judge.is_break

    def group_left(self, player: int) -> int | None:
        """Balls of the player's group still on the table (None while they have no group)."""
        group = self.groups[player]
        if group is None:
            return None
        return len((SOLIDS if group == SOLID else STRIPES) - self._judge.pocketed)

    def eight_is_next(self, player: int) -> bool:
        return self.group_left(player) == 0 and 8 not in self._judge.pocketed

    # --- one shot -------------------------------------------------------------------------------
    def on_shot(self) -> None:
        """The player on turn has taken a shot (also ends their "cue ball in hand")."""
        self._judge.group = self.groups[self.turn]
        self._judge.on_shot()
        self.shots[self.turn] += 1
        self.cue_in_hand = False

    def on_events(self, events: Iterable[Event]) -> None:
        self._judge.on_events(events)

    def cue_placed(self) -> None:
        self._judge.cue_placed()
        self.cue_in_hand = False

    def finish_shot(self) -> MatchShot:
        """Judge the shot that just ended (the referee calls this once, when every ball stopped)."""
        shooter = self.turn
        res = self._judge.finish_shot()
        if res.group is not None:  # the first legal pocket after the break picks both groups
            self.groups[shooter] = res.group
            self.groups[1 - shooter] = OPPOSITE[res.group]
        outcome = res.outcome
        if outcome == RERACK:  # the 8 went down on the break: same player breaks again
            self.cue_in_hand = False
        elif outcome in (WON, LOST):
            self.over, self.winner = True, shooter if outcome == WON else 1 - shooter
            self.cue_in_hand = False
        elif res.fouls:
            self.fouls[shooter] += 1
            self.turn, self.cue_in_hand = 1 - shooter, True
        elif not self._keeps_turn(shooter, res.pocketed):
            self.turn = 1 - shooter
        self.last = MatchShot(shooter, res.fouls, res.pocketed, res.group, outcome, res.reason)
        return self.last

    def _keeps_turn(self, shooter: int, pocketed: tuple[int, ...]) -> bool:
        group = self.groups[shooter]
        if group is None:  # the table is open: any ball down counts
            return bool(pocketed)
        mine = SOLIDS if group == SOLID else STRIPES
        return any(ball in mine for ball in pocketed)

    def timeout(self) -> MatchShot:
        """The clock ran out: the turn passes (no foul, no ball in hand)."""
        shooter = self.turn
        self.turn, self.cue_in_hand = 1 - shooter, False
        self.last = MatchShot(shooter, timed_out=True)
        return self.last

    def rerack(self) -> None:
        """The caller racked the balls again after a RERACK result."""
        self._judge.rerack()
        self.cue_in_hand = False

    # --- the referee's word, for the other machine --------------------------------------------
    def snapshot(self) -> MatchState:
        return MatchState(
            turn=self.turn,
            groups=(self.groups[0], self.groups[1]),
            cue_in_hand=self.cue_in_hand,
            over=self.over,
            winner=self.winner,
            is_break=self._judge.is_break,
            pocketed=frozenset(self._judge.pocketed),
            shots=(self.shots[0], self.shots[1]),
            fouls=(self.fouls[0], self.fouls[1]),
            last=self.last,
        )

    def load(self, s: MatchState) -> None:
        """Take over the referee's state (this copy only follows; it never judges)."""
        self.turn = s.turn
        self.groups = [s.groups[0], s.groups[1]]
        self.cue_in_hand = s.cue_in_hand
        self.over, self.winner = s.over, s.winner
        self.shots, self.fouls = [s.shots[0], s.shots[1]], [s.fouls[0], s.fouls[1]]
        self.last = s.last
        self._judge.pocketed = set(s.pocketed)
        self._judge.is_break = s.is_break
        self._judge.cue_in_hand = s.cue_in_hand
