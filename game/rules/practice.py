"""Practice "the Ghost": a solo pressure drill, brief docs/plans/20261102-luyen-tap.md.

Pure (no pygame). One ball at a time is the TARGET, picked at random among the balls still on the
table that have a pot line (physics/pot_lines.py, docs/GAME_DESIGN.md round 39): a straight shot
into a pocket that no other ball blocks, from where the cue ball stands. So no run can lose a life
to a shot that was never possible in the first place. A shot succeeds when the target goes into a
pocket (what the cue ball touches first does not matter, a bank or a combination is as good as a
straight shot); the next target is then picked. A shot that does not pot the target, the cue ball
going into a pocket (it is then in hand), or the shot's clock running out each cost one of the
lives; with none left the run is lost; with no ball left on the table it is won. A target that
survives a miss is kept for the next shot unless it has lost every pot line, in which case it is
swapped for a ball that has one, at no extra cost. If NO ball has a pot line from where the cue
ball stands, it is given in hand (no life lost) and the lines are counted from wherever it could
be put; only if even that finds none is a ball the cue ball can see picked, else any.

The opening break is the exception (docs/GAME_DESIGN.md round 38): nothing is called while the
balls still sit racked, so there is nothing to miss — the first real target is picked only once the
break has scattered them. A scratch on the break still costs a life as normal; stalling past the
shot's clock before it is even fired also does, but leaves the table untouched and still waiting.

Two more drills share all of this (and the scale the target is picked on); `make_run(mode, rng)`
gives the one asked for:
- `CallRun` "Call the Pocket": the pocket the target must go into is named too, picked among those
  with a pot line cutting no thinner than CALL_MAX_CUT_DEG. The target in any other pocket is a
  miss (the ball still stays down). If the called pocket loses its line the pocket is changed (the
  ball too, if it has no other).
- `SprintRun` "Sprint": no lives, one shared clock instead (the scene feeds `tick`): a pot adds
  time, a miss or a scratch takes it away; no time left loses the run, no ball left wins it.

Every drill has two levels (`make_run(mode, rng, level)`, config.PRACTICE_LEVELS). "hard" is all of
the above. "easy" first asks the same scale of the easy lines only (cut no thinner than
EASY_MAX_CUT_DEG, target no further than EASY_MAX_POT_DIST_M from the pocket; in Call the Pocket
the pocket named is one of those too): from where the cue ball stands, then in hand (no life or
time lost), margin first and then the squeezes. Only when even that finds no ball does it go on
with the hard scale, so a run is never stuck.
"""

from __future__ import annotations

import random
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from game.config import (
    CALL_MAX_CUT_DEG,
    EASY_MAX_CUT_DEG,
    EASY_MAX_POT_DIST_M,
    PRACTICE_LEVELS,
    PRACTICE_LINE_MARGIN_M,
    PRACTICE_LIVES,
    PRACTICE_MAX_CUT_DEG,
    SPRINT_CAP_S,
    SPRINT_MISS_COST_S,
    SPRINT_POT_BONUS_S,
    SPRINT_SCRATCH_COST_S,
    SPRINT_START_S,
)
from game.physics.pot_lines import pot_lines, pot_pockets
from game.physics.raycast import first_contact
from game.physics.world import CUE, Ball, BallPocketed, Event
from game.rules.eight_ball import FOUL_SCRATCH, LOST, PLAYING, WON

MISS = "practice.miss"  # the target did not go into a pocket
LOST_TIMEOUT = "practice.lost_timeout"  # the shot's clock reached zero before a shot was taken
SPRINT_TIME_UP = "practice.time_up"  # Sprint: the one clock of the run reached zero
BALLS = frozenset(range(1, 16))


@dataclass(frozen=True)
class ShotResult:
    hit: bool = False  # the target went into a pocket (and the cue ball did not)
    pocketed: tuple[int, ...] = ()  # object balls this shot pocketed, in order
    lost_life: str | None = None  # why a life was lost: FOUL_SCRATCH, MISS or LOST_TIMEOUT (in
    # Sprint, where no life is lost: what cost time, and SPRINT_TIME_UP when the clock ran out)
    outcome: str | None = None  # None | WON | LOST


class GhostRun:
    mode = "ghost"

    def __init__(self, rng: random.Random | None = None, level: str = "hard") -> None:
        if level not in PRACTICE_LEVELS:
            raise ValueError(f"unknown practice level: {level!r}")
        self.level = level  # "hard" (as it always was) or "easy" (only the easy lines)
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
        self.target_swapped = False  # the last target change was a swap away from a dead ball
        self.hand_given = False  # the last judging found no pot line and gave the cue ball in hand
        self.target: int | None = None  # nothing is called while the break still sits racked
        self._ask: tuple[bool, float] | None = None  # the (in hand, margin) the lines were found at
        self._ask_easy = False  # ... and whether that was one of the easy asks
        self._begin_record()

    # --- state the screen shows ------------------------------------------------------------
    @property
    def balls_left(self) -> int:
        return 15 - len(self.pocketed)

    def _lines(
        self, balls: Sequence[Ball], n: int, in_hand: bool, margin: float, easy: bool = False
    ) -> int:
        """In how many ways could ball `n` be shot straight into a pocket (what counts as one is
        up to the mode); `easy`: only the easy lines."""
        if easy:
            return pot_lines(
                balls,
                n,
                cue_in_hand=in_hand,
                max_cut_deg=min(EASY_MAX_CUT_DEG, PRACTICE_MAX_CUT_DEG),
                margin=margin,
                max_pot_dist=EASY_MAX_POT_DIST_M,
            )
        return pot_lines(balls, n, cue_in_hand=in_hand, margin=margin)

    def _viable(
        self, balls: Sequence[Ball], in_hand: bool, margin: float, easy: bool = False
    ) -> list[int]:
        """The balls still on the table that could be shot straight into a pocket."""
        left = sorted(BALLS - self.pocketed)
        return [n for n in left if self._lines(balls, n, in_hand, margin, easy) > 0]

    def _pick_pocket(self, balls: Sequence[Ball] | None) -> None:
        """Called once a target has just been picked: a mode that names a pocket names it here."""

    def _hold_pocket(self, balls: Sequence[Ball]) -> None:
        """Called when the held target is kept after a shot: a mode that names a pocket checks the
        one it named still has its line here."""

    def _pick(self) -> int | None:
        left = sorted(BALLS - self.pocketed)
        return self._rng.choice(left) if left else None

    def _retarget(self, balls: Sequence[Ball] | None, *, keep: bool) -> None:
        """Choose a target now: a fresh one (`keep` False), or the held one unless it has lost
        every pot line. Asking for the most from the table first, then less: lines from where the
        cue ball stands; if none, from wherever it could be put (it is given in hand, no life
        lost); if none, the same with the thinnest squeezes allowed (no gap to spare)."""
        if balls is None:
            if not keep:
                self.target = self._pick()
                self._pick_pocket(None)
            return
        left = sorted(BALLS - self.pocketed)
        hand = self.cue_in_hand
        good: list[int] = []
        self._ask = None
        self._ask_easy = False
        asks = [
            (hand, PRACTICE_LINE_MARGIN_M),
            (True, PRACTICE_LINE_MARGIN_M),
            (hand, 0.0),
            (True, 0.0),
        ]
        # the easy level goes through the scale on the easy lines first, then as the hard one does
        steps = [(a, False) for a in asks]
        if self.level == "easy":
            steps = [(a, True) for a in asks] + steps
        for (in_hand, margin), easy in steps:
            good = self._viable(balls, in_hand, margin, easy)
            if good:
                if in_hand and not hand:
                    self.cue_in_hand = self.hand_given = True
                self._ask = (in_hand, margin)
                self._ask_easy = easy
                break
        pool = good or [n for n in left if self._open(balls, n)] or left
        if keep and self.target in pool:
            self._hold_pocket(balls)
            return
        self.target_swapped = keep
        self.target = self._rng.choice(pool)
        self._pick_pocket(balls)

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
        self._pocket_of: dict[int, int] = {}  # the pocket (index into POCKETS) each ball fell in
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
                    self._pocket_of[ev.ball] = ev.pocket
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
        elif self._potted_right(self.target):
            hit = True
            self.streak += 1
        else:
            lost = MISS
        return self._settle(
            ShotResult(hit, down, lost), target_gone=self.target in down, balls=balls
        )

    def _potted_right(self, target: int) -> bool:
        """Did the target go down the way this mode wants (any pocket will do here)?"""
        return target in self._down

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
        self._penalize(res)
        outcome = None
        if self._out_of_chances():
            outcome = LOST
        elif not BALLS - self.pocketed:
            outcome = WON
        self.target_swapped = self.hand_given = False
        if outcome:
            self.phase = outcome
            self.cue_in_hand = False
            self.target = None if outcome == WON else self.target
        elif target_gone or (self.target is None and shot_fired):
            self._retarget(balls, keep=False)
        elif self.target is not None:
            self._retarget(balls, keep=True)
        self.last = ShotResult(res.hit, res.pocketed, res.lost_life, outcome)
        return self.last

    def _penalize(self, res: ShotResult) -> None:
        """What a judged shot (or a timeout) costs, or earns, in this mode: here, one life."""
        if res.lost_life:
            self.lives -= 1

    def _out_of_chances(self) -> bool:
        return self.lives <= 0


class CallRun(GhostRun):
    """Practice "Call the Pocket": the target must go into the pocket that is named."""

    mode = "call"

    def reset(self) -> None:
        super().reset()
        self.pocket: int | None = None  # index into POCKETS; None while no target is called

    def _lines(
        self, balls: Sequence[Ball], n: int, in_hand: bool, margin: float, easy: bool = False
    ) -> int:
        return len(self._pockets(balls, n, in_hand, margin, easy))

    @staticmethod
    def _pockets(
        balls: Sequence[Ball], n: int, in_hand: bool, margin: float, easy: bool = False
    ) -> list[int]:
        if easy:
            return pot_pockets(
                balls,
                n,
                cue_in_hand=in_hand,
                max_cut_deg=min(EASY_MAX_CUT_DEG, CALL_MAX_CUT_DEG),
                margin=margin,
                max_pot_dist=EASY_MAX_POT_DIST_M,
            )
        return pot_pockets(
            balls, n, cue_in_hand=in_hand, max_cut_deg=CALL_MAX_CUT_DEG, margin=margin
        )

    def _callable(self, balls: Sequence[Ball] | None) -> list[int]:
        """The pockets the target may be called into, at the same ask its ball was found at."""
        if balls is None or self.target is None or self._ask is None:
            return []
        return self._pockets(balls, self.target, *self._ask, self._ask_easy)

    def _pick_pocket(self, balls: Sequence[Ball] | None) -> None:
        # (with no pot line anywhere, or no positions to look at, no pocket is named: any will do)
        pockets = self._callable(balls)
        self.pocket = self._rng.choice(pockets) if pockets else None

    def _hold_pocket(self, balls: Sequence[Ball]) -> None:
        pockets = self._callable(balls)
        if self.pocket in pockets or not pockets:
            if not pockets:
                self.pocket = None
            return
        self.target_swapped = self.pocket is not None
        self.pocket = self._rng.choice(pockets)

    def _potted_right(self, target: int) -> bool:
        if target not in self._down:
            return False
        return self.pocket is None or self._pocket_of.get(target) == self.pocket

    def _settle(
        self,
        res: ShotResult,
        *,
        target_gone: bool,
        balls: Sequence[Ball] | None = None,
        shot_fired: bool = True,
    ) -> ShotResult:
        self._ask = None  # (what the lines were found at is only known after the next picking)
        self._ask_easy = False
        out = super()._settle(res, target_gone=target_gone, balls=balls, shot_fired=shot_fired)
        if self.target is None or self.phase != PLAYING:
            self.pocket = None  # nothing is called once the run is over
        return out


class SprintRun(GhostRun):
    """Practice "Sprint": one clock for the whole run instead of lives."""

    mode = "sprint"

    def reset(self) -> None:
        super().reset()
        self.time_left = SPRINT_START_S

    def tick(self, dt: float) -> ShotResult | None:
        """Time passes (the scene calls this while the player may aim). The clock reaching zero
        loses the run: that result is returned, else None."""
        if self.phase != PLAYING:
            return None
        self.time_left = max(0.0, self.time_left - dt)
        if self.time_left > 0.0:
            return None
        self.phase = LOST
        self._live = False
        self.cue_in_hand = False
        self.last = ShotResult(lost_life=SPRINT_TIME_UP, outcome=LOST)
        return self.last

    def timeout(self, balls: Sequence[Ball] | None = None) -> ShotResult:
        """There is no clock for each shot here: nothing happens."""
        return ShotResult()

    def _penalize(self, res: ShotResult) -> None:
        if res.hit:
            self.time_left = min(SPRINT_CAP_S, self.time_left + SPRINT_POT_BONUS_S)
        elif res.lost_life == FOUL_SCRATCH:
            self.time_left = max(0.0, self.time_left - SPRINT_SCRATCH_COST_S)
        elif res.lost_life:
            self.time_left = max(0.0, self.time_left - SPRINT_MISS_COST_S)

    def _out_of_chances(self) -> bool:
        return self.time_left <= 0.0


_MODES = {"ghost": GhostRun, "call": CallRun, "sprint": SprintRun}


def make_run(mode: str, rng: random.Random, level: str = "hard") -> GhostRun:
    """The run for a practice mode (config.PRACTICE_MODES) at a level (config.PRACTICE_LEVELS)."""
    return _MODES[mode](rng, level)
