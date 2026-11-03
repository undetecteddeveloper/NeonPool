"""The table in Practice "the Ghost": pot the random target ball, under a clock.

Over the solo Free play table this changes: a run begins with a countdown in which nothing may
be touched (the ball to hit is only shown once it is over), the rules are `rules/practice.py`'s
(a random ball is the target, three lives, no foul for what the cue ball touches), a counter in the
side panel counts down each shot (reaching zero costs a life), and the result card shows the
streak you reached and the best one ever instead of shots and fouls. See
docs/plans/20261102-luyen-tap.md.
"""

from __future__ import annotations

import math

import pygame as pg

from game.config import (
    NOTICE_S,
    PRACTICE_DIM_FADE_S,
    PRACTICE_READY_S,
    PRACTICE_SHOT_S,
    PRACTICE_WARN_S,
)
from game.i18n import t
from game.physics import Shot
from game.render import hud
from game.render import palette as C
from game.render.view import View
from game.rules.eight_ball import LOST, PLAYING, WON
from game.rules.practice import GhostRun, ShotResult
from game.scenes.play import CALLOUT_AT, PlayScene
from game.tally import Tally

BLINK_HZ = 2.0  # the shot clock blinks this often in its last seconds (same feel as the net game)


class PracticeScene(PlayScene):
    def __init__(self, app) -> None:
        super().__init__(app)
        self.rules = GhostRun(self.world.rng)
        self._shot_left = PRACTICE_SHOT_S
        self._ready_left = PRACTICE_READY_S  # the wait before a run: nothing may be touched
        self._warned = -1  # the last second of the shot's clock that was beeped
        self._dim_k = 1.0  # how dark the screen is: all dark for the wait, then it clears
        self._swap_left = 0.0  # how long the "target swapped" hint under the table still shows

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
        self._dim_k = 1.0
        self._swap_left = 0.0

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
            and not self.rules.cue_in_hand
        )

    def _dial_ok(self) -> bool:
        return self._can_aim()

    def _hint_words(self) -> str | None:
        if self.counting_down:
            return None  # (the wait has its own)
        if self.rules.target is None and self.rules.phase == PLAYING:
            return t("practice.breaking")
        if self._swap_left > 0.0:
            return t("practice.target_swapped")
        return super()._hint_words()

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
        if not self.world.balls[0].in_play:
            self.world.respawn_cue()  # back on the table, ready to be placed
        res = self.rules.finish_shot(self.world.balls)
        if res.outcome in (WON, LOST):
            self._finish_run(res)
        elif res.lost_life:
            self._notify("foul", res.lost_life)
        if self.rules.target_swapped:
            self._swap_left = NOTICE_S

    def _finish_run(self, res: ShotResult) -> None:
        self._ended_at = self._clock
        won = res.outcome == WON
        (self.app.audio.play_win if won else self.app.audio.play_lose)()
        best = max(self.app.settings.practice_best, self.rules.streak)
        if best > self.app.settings.practice_best:
            self.app.change_settings(practice_best=best)
        self._tally = Tally({"score": self.rules.streak, "shots": self.rules.shots, "fouls": best})
        self._ticks, self._tinged = dict.fromkeys(self._tally.targets, 0), set()

    # --- time: the wait before the run, then the clock of each shot (it costs a life)
    def update(self, dt: float) -> None:
        super().update(dt)
        if self._leave_open:
            return
        self._swap_left = max(0.0, self._swap_left - dt)
        self._dim_k = (
            1.0 if self.counting_down else max(0.0, self._dim_k - dt / PRACTICE_DIM_FADE_S)
        )
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
        if self._ready_left == PRACTICE_READY_S:
            self.app.audio.play_count()  # the first second of the count
        self._ready_left = max(0.0, self._ready_left - dt)
        if self._ready_left <= 0.0:
            self.app.audio.play_notice()  # the table is yours
            self._warned = -1
            return
        if math.ceil(self._ready_left) != before:
            self.app.audio.play_count()  # one sound for every second of the count

    def _timeout(self) -> None:
        """The clock of the shot ran out: a life lost, a fresh clock."""
        self.drag.cancel()
        self._shot_left = PRACTICE_SHOT_S
        res = self.rules.timeout(self.world.balls)
        if res.outcome in (WON, LOST):
            self._finish_run(res)
            return
        self._notice, self._notice_left = ("foul", res.lost_life), NOTICE_S
        self._callout = (t("callout.timeout"), C.AMBER, self._clock)
        self.app.audio.play_foul()
        if self.rules.target_swapped:
            self._swap_left = NOTICE_S

    # --- drawing ------------------------------------------------------------------------------
    def _draw_overlays(self, canvas: pg.Surface, v: View, over: bool) -> None:
        """While the run waits to begin the whole screen is dark, only the counter is lit and the
        middle of the table says so; when the wait is over the screen clears."""
        if self._dim_k > 0.0 and not over:
            hud.dim_screen(canvas, self._dim_k)
            counting = self.counting_down
            hud.draw_practice_count(
                canvas,
                v,
                math.ceil(self._ready_left if counting else self._shot_left),
                counting,
                False,
                False,
            )
            if counting:
                hud.glow_text(canvas, v, t("practice.counting"), 30, C.WHITE, C.CYAN, CALLOUT_AT)
        super()._draw_overlays(canvas, v, over)

    def _draw_panel(self, canvas: pg.Surface, v: View) -> None:
        blink_on = int(self._clock * BLINK_HZ * 2) % 2 == 0
        counting = self.counting_down
        hud.draw_practice_panel(
            canvas,
            v,
            streak=self.rules.streak,
            lives=self.rules.lives,
            best=self.app.settings.practice_best,
            target=self.rules.target,
            target_shown=not counting,
            cleared=self.rules.phase == WON,
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

    def _lost_words(self) -> str | None:
        """Why the run was lost (the last life), or nothing for a win."""
        res = self.rules.last
        if self.rules.phase == WON or res is None or res.lost_life is None:
            return None
        return t("practice.out_of_lives", why=t(res.lost_life))

    def _draw_result_frame(self, canvas: pg.Surface, v: View) -> None:
        hud.draw_result_frame(
            canvas,
            v,
            won=self.rules.phase == WON,
            reason=self._lost_words(),
            row_names=[t("hud.shots"), t("practice.best")],
            score_label=t("practice.streak"),
        )

    def _draw_result(self, canvas: pg.Surface, v: View) -> None:
        shown, flashes = self._shown_numbers()
        hud.draw_result(
            canvas,
            v,
            won=self.rules.phase == WON,
            reason=self._lost_words(),
            score=shown["score"],
            rows=[(t("hud.shots"), shown["shots"]), (t("practice.best"), shown["fouls"])],
            score_label=t("practice.streak"),
            flashes=flashes,
            age=self._clock - self._ended_at,
            fx=self.result_fx,
            clock=self._clock,
        )
