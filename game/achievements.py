"""Achievements: which ones there are, and when the player earns them. No pygame here.

The scenes tell the `Tracker` what just happened (a free-play shot judged, a practice shot judged,
a two-player game won); it decides what that unlocks, keeps the player's progress in the settings
(so it is saved with them, in the player's own folder) and says which ones are new. An unlocked
achievement stays unlocked for good: nothing here takes one away. Each is earned once.
The words (name, how to earn it) are `ach.<id>` and `ach.<id>.d` in lang/*.json.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from game.rules.eight_ball import LOST, RERACK, WON

FREE, PRACTICE, DUO = "free", "practice", "duo"  # where an achievement is earned (its group)

# the numbers behind the achievements that are a matter of degree
TRIPLE_BALLS = 3  # balls pocketed with ONE shot
WINS_REGULAR = 10  # free-play wins
QUICK_WIN_SHOTS = 12  # a win in this many shots or fewer
CLEAN_STREAK = 3  # free-play wins in a row without a single foul
COMEBACK_FOULS = 5  # fouls in one game that was still won
GHOST_STREAKS = (("ghost_5", 5), ("ghost_10", 10))  # (id, balls in a row in "the Ghost")
DUO_WINS_KING = 5  # two-player games won


@dataclass(frozen=True)
class Achievement:
    id: str
    group: str
    secret: bool = False  # the list shows "???" until it is earned


CATALOGUE = (
    Achievement("first_shot", FREE),
    Achievement("first_pot", FREE),
    Achievement("pick_group", FREE),
    Achievement("triple", FREE),
    Achievement("win", FREE),
    Achievement("clean_win", FREE),
    Achievement("win_10", FREE),
    Achievement("quick_win", FREE, secret=True),
    Achievement("hat_trick", FREE, secret=True),
    Achievement("comeback", FREE, secret=True),
    Achievement("eight_break", FREE, secret=True),
    Achievement("ghost_5", PRACTICE),
    Achievement("ghost_10", PRACTICE),
    Achievement("ghost_clear", PRACTICE),
    Achievement("call_win", PRACTICE),
    Achievement("call_hard", PRACTICE),
    Achievement("sprint_win", PRACTICE),
    Achievement("sprint_hard", PRACTICE),
    Achievement("duo_win", DUO),
    Achievement("duo_5", DUO),
)
IDS = frozenset(a.id for a in CATALOGUE)
assert len(IDS) == len(CATALOGUE) == 20


class Tracker:
    """Keeps the progress in `settings` and reports what each event newly unlocks.

    `save()` is called after every change; `announce(id)` once for each newly earned one (the app
    queues the card that slides out). Both are optional (tests use neither)."""

    def __init__(self, settings, save: Callable[[], object] | None = None,
                 announce: Callable[[str], object] | None = None) -> None:  # fmt: skip
        self._s = settings
        self._save = save
        self._announce = announce

    def has(self, ach_id: str) -> bool:
        return ach_id in self._s.achievements

    @property
    def count(self) -> int:
        return len(self._s.achievements)

    def _unlock(self, *ids: str) -> list[str]:
        new = [i for i in dict.fromkeys(ids) if i in IDS and i not in self._s.achievements]
        self._s.achievements.extend(new)
        if self._save is not None:
            self._save()
        for i in new:
            if self._announce is not None:
                self._announce(i)
        return new

    # --- Free play ------------------------------------------------------------------------------
    def free_shot(self, res, shots: int, fouls: int) -> list[str]:
        """A Free-play shot has been judged. `res` is the rules' `ShotResult`; `shots` and `fouls`
        are the game's totals so far (this shot included)."""
        got = ["first_shot"] if shots >= 1 else []
        if res.pocketed:
            got.append("first_pot")
        if len(res.pocketed) >= TRIPLE_BALLS:
            got.append("triple")
        if res.group:
            got.append("pick_group")
        if res.outcome == RERACK:
            got.append("eight_break")
        if res.outcome == WON:
            got += self._free_won(shots, fouls)
        elif res.outcome == LOST and self._s.ach_clean_streak:
            self._s.ach_clean_streak = 0
        return self._unlock(*got)

    def _free_won(self, shots: int, fouls: int) -> list[str]:
        s = self._s
        s.ach_wins += 1
        s.ach_clean_streak = s.ach_clean_streak + 1 if fouls == 0 else 0
        got = ["win"]
        if fouls == 0:
            got.append("clean_win")
        if s.ach_wins >= WINS_REGULAR:
            got.append("win_10")
        if shots <= QUICK_WIN_SHOTS:
            got.append("quick_win")
        if s.ach_clean_streak >= CLEAN_STREAK:
            got.append("hat_trick")
        if fouls >= COMEBACK_FOULS:
            got.append("comeback")
        return got

    # --- Practice -------------------------------------------------------------------------------
    def practice_shot(self, mode: str, level: str, streak: int, outcome: str | None) -> list[str]:
        """A practice shot has been judged: `streak` is the balls potted in a row in this run
        (it counts as it grows, not only at the run's end), `outcome` is None, WON or LOST."""
        got: list[str] = []
        won = outcome == WON
        if mode == "ghost":
            got += [i for i, need in GHOST_STREAKS if streak >= need]
            if won:
                got.append("ghost_clear")
        elif mode == "call" and won:
            got += ["call_win"] + (["call_hard"] if level == "hard" else [])
        elif mode == "sprint" and won:
            got += ["sprint_win"] + (["sprint_hard"] if level == "hard" else [])
        return self._unlock(*got)

    # --- Two players ----------------------------------------------------------------------------
    def duo_won(self) -> list[str]:
        """The player won a two-player game."""
        self._s.ach_duo_wins += 1
        got = ["duo_win"] + (["duo_5"] if self._s.ach_duo_wins >= DUO_WINS_KING else [])
        return self._unlock(*got)
