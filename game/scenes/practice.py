"""The table in Practice "the Ghost": pot the 15 balls strictly in order, under a clock.

Over the solo Free play table this changes: a run begins with a countdown in which nothing may
be touched (the ball to hit is only shown once it is over), a counter in the side panel counts
down each shot (reaching zero loses the run, exactly like a foul), there is no ball in hand (any
foul ends the run at once, no rerack), and the result card shows the streak you reached and the
best one ever instead of shots and fouls. See docs/plans/20261102-luyen-tap.md.
"""

from __future__ import annotations

import math

import pygame as pg

from game.config import (
    PRACTICE_READY_BEEP_S,
    PRACTICE_READY_S,
    PRACTICE_SHOT_S,
    PRACTICE_WARN_S,
)
from game.i18n import t
from game.physics import Shot
from game.render import hud
from game.render.view import View
from game.rules.eight_ball import LOST, PLAYING, WON
from game.rules.practice import GhostRun, ShotResult
from game.scenes.play import PlayScene
from game.tally import Tally

BLINK_HZ = 2.0  # the shot clock blinks this often in its last seconds (same feel as the net game)


class PracticeScene(PlayScene):
    def __init__(self, app) -> None:
        super().__init__(app)
        self.rules = GhostRun()
        self._shot_left = PRACTICE_SHOT_S
        self._ready_left = PRACTICE_READY_S  # the wait before a run: nothing may be touched
        self._warned = -1  # the last second of the shot's clock that was beeped

    def set_view(self, v: View) -> None:
        """The Free play table already made the sprites and the table picture for this size: share
        them instead of making them again (as `NetPlayScene` does for the same reason)."""
        solo = getattr(self.app, "play", None)
        if solo is not None and solo is not self and solo.view.same_as(v):
            self.view, self.sprites, self.table = v, solo.sprites, solo.table
            if hasattr(self, "_frozen"):
                self._frozen.clear()
        else:
            super().set_view(v)

    # --- game flow -------------------------------------------------------------------
    def new_game(self) -> None:
        super().new_game()
        self._shot_left = PRACTICE_SHOT_S
        self._ready_left = PRACTICE_READY_S
        self._warned = -1

    @property
    def counting_down(self) -> bool:
        """The run has not begun: nothing may be touched and the ball to hit is not shown."""
        return self.rules.phase == PLAYING and self._ready_left > 0.0

    def _can_aim(self) -> bool:
        return (
            not self.counting_down
            and self.rules.phase == PLAYING
            and self.world.balls[0].in_play
            and self.world.at_rest()
        )

    def _dial_ok(self) -> bool:
        return self._can_aim()

    def _holding(self) -> bool:
        return False  # no ball in hand here: any foul ends the run outright

    def _hand_event(self, e: pg.event.Event) -> bool:
        self.placing = False
        return False

    def fire(self, shot: Shot) -> None:
        self._shot_visuals(shot, self.drag.bar_length)
        self.world.apply(shot)
        self.rules.on_shot()
        self._live = True
        self._break_pending = self.rules.shots == 1
        self._shot_left = PRACTICE_SHOT_S
        self._ready_left = 0.0  # (a shot was taken: the wait is over, whoever fired it)

    def _end_shot(self) -> None:
        self._live = False
        res = self.rules.finish_shot()
        if res.outcome in (WON, LOST):
            self._finish_run(res)

    def _finish_run(self, res: ShotResult) -> None:
        self._ended_at = self._clock
        won = res.outcome == WON
        (self.app.audio.play_win if won else self.app.audio.play_lose)()
        best = max(self.app.settings.practice_best, self.rules.streak)
        if best > self.app.settings.practice_best:
            self.app.change_settings(practice_best=best)
        self._tally = Tally({"score": self.rules.streak, "shots": self.rules.shots, "fouls": best})
        self._ticks, self._tinged = dict.fromkeys(self._tally.targets, 0), set()

    # --- time: the wait before the run, then the clock of each shot (it ends the run like a foul)
    def update(self, dt: float) -> None:
        super().update(dt)
        if self.counting_down:
            self._count_down_to_start(dt)
            return
        if not self._can_aim():
            self._warned = -1
            return
        self._shot_left = max(0.0, self._shot_left - dt)
        if self._shot_left <= 0.0:
            self._timeout()
            return
        left = math.ceil(self._shot_left)
        if left > PRACTICE_WARN_S:
            self._warned = -1
        elif left != self._warned:
            self._warned = left
            self.app.audio.play_clock_warn(left)

    def _count_down_to_start(self, dt: float) -> None:
        before = math.ceil(self._ready_left)
        self._ready_left = max(0.0, self._ready_left - dt)
        if self._ready_left <= 0.0:
            self.app.audio.play_notice()  # the table is yours
            self._warned = -1
            return
        left = math.ceil(self._ready_left)
        if left != before and left <= PRACTICE_READY_BEEP_S:
            self.app.audio.play_clock_warn(left)

    def _timeout(self) -> None:
        self.drag.cancel()
        self._finish_run(self.rules.timeout())

    # --- drawing ------------------------------------------------------------------------------
    def _draw_panel(self, canvas: pg.Surface, v: View) -> None:
        blink_on = int(self._clock * BLINK_HZ * 2) % 2 == 0
        counting = self.counting_down
        hud.draw_practice_panel(
            canvas,
            v,
            streak=self.rules.streak,
            best=self.app.settings.practice_best,
            target=self.rules.target,
            target_shown=not counting,
            pocketed=self.rules.pocketed,
            muted=self.app.audio.muted,
            moving=not self.world.at_rest(),
            sprites=self.sprites,
            clock=self._clock,
            board=self.board,
            pocket_times=self.pocket_times,
            spin=self.spin,
            spin_lit=self._dial_lit,
            spin_on=self._dial_ok(),
            count=math.ceil(self._ready_left if counting else self._shot_left),
            counting_down=counting,
            warn=not counting and self._shot_left <= PRACTICE_WARN_S,
            blink_on=blink_on,
            keys=self.PANEL_KEYS,
        )

    def _shown_numbers(self) -> tuple[dict[str, int], tuple[float, float, float]]:
        tally, age = self._tally, self._clock - self._ended_at
        if tally is None:
            whole = {
                "score": self.rules.streak,
                "shots": self.rules.shots,
                "fouls": self.app.settings.practice_best,
            }
            return whole, (0.0, 0.0, 0.0)
        shown = {name: tally.value(name, age) for name in tally.targets}
        return shown, tuple(tally.flash(name, age) for name in tally.targets)

    def _draw_result_frame(self, canvas: pg.Surface, v: View) -> None:
        res = self.rules.last
        hud.draw_result_frame(
            canvas,
            v,
            won=self.rules.phase == WON,
            reason=t(res.reason) if res and res.reason else None,
            row_names=[t("hud.shots"), t("practice.best")],
            score_label=t("practice.streak"),
        )

    def _draw_result(self, canvas: pg.Surface, v: View) -> None:
        res = self.rules.last
        shown, flashes = self._shown_numbers()
        hud.draw_result(
            canvas,
            v,
            won=self.rules.phase == WON,
            reason=t(res.reason) if res and res.reason else None,
            score=shown["score"],
            rows=[(t("hud.shots"), shown["shots"]), (t("practice.best"), shown["fouls"])],
            score_label=t("practice.streak"),
            flashes=flashes,
            age=self._clock - self._ended_at,
            fx=self.result_fx,
            clock=self._clock,
        )
