"""The table in Practice: pot the random target ball, under a clock.

Over the solo Free play table this changes: a run begins with a countdown in which nothing may
be touched (the ball to hit is only shown once it is over), the rules are `rules/practice.py`'s
(a random ball is the target, three lives, no foul for what the cue ball touches), a counter in the
side panel counts down each shot (reaching zero costs a life), and the result card shows the
streak you reached and the best one ever instead of shots and fouls. See
docs/plans/20261102-luyen-tap.md.

Three drills share this table (`start(mode)`, config.PRACTICE_MODES): "ghost" (Beat the Ghost, as
above); "call" (Call the Pocket: a lit ring marks the pocket the target must go into); "sprint"
(one clock for the whole run instead of lives and shot clocks, it runs only while the player may
aim). See docs/plans/20261104-luyen-tap-da-che-do.md.
"""

from __future__ import annotations

import math

import pygame as pg

from game.config import (
    NOTICE_S,
    PRACTICE_DIM_FADE_S,
    PRACTICE_LEVELS,
    PRACTICE_READY_S,
    PRACTICE_SHOT_S,
    PRACTICE_WARN_S,
)
from game.i18n import t
from game.physics import Shot
from game.render import draw, hud
from game.render import palette as C
from game.render.view import View
from game.rules.eight_ball import LOST, PLAYING, WON
from game.rules.practice import MISS, GhostRun, ShotResult, make_run
from game.scenes.play import CALLOUT_AT, PlayScene
from game.settings import best_field, best_for
from game.tally import Tally

BLINK_HZ = 2.0  # the shot clock blinks this often in its last seconds (same feel as the net game)


class PracticeScene(PlayScene):
    def __init__(self, app) -> None:
        super().__init__(app)
        self.mode, self.level = "ghost", "hard"
        self.rules = GhostRun(self.world.rng)
        self._shot_left = PRACTICE_SHOT_S
        self._ready_left = PRACTICE_READY_S  # the wait before a run: nothing may be touched
        self._warned = -1  # the last second of the shot's clock that was beeped
        self._dim_k = 1.0  # how dark the screen is: all dark for the wait, then it clears
        self._swap_left = 0.0  # how long the "target swapped" line of the notice still shows
        self._hand_left = 0.0  # ... and the "no shot to a pocket, cue ball in hand" line
        self._swap_key = "practice.target_swapped"  # what the swap line says (ball or pocket)
        self._miss_key: str | None = None  # why the last shot cost a life, when not the rules' word
        self._time_note, self._time_note_left = 0, 0.0  # Sprint: the time the last shot won / cost

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
    def start(self, mode: str, level: str | None = None) -> None:
        """A new run of the given kind (config.PRACTICE_MODES) at the given level
        (config.PRACTICE_LEVELS; None: the one last played, in the settings). Every later new run
        (R, the result card) keeps both."""
        self.mode = mode
        self.level = level if level in PRACTICE_LEVELS else self.app.settings.practice_level
        self.rules = make_run(mode, self.world.rng, self.level)
        self.new_game()

    def new_game(self) -> None:
        super().new_game()
        self._shot_left = PRACTICE_SHOT_S
        self._ready_left = PRACTICE_READY_S
        self._warned = -1
        self._dim_k = 1.0
        self._swap_left = self._hand_left = 0.0
        self._miss_key = None
        self._time_note, self._time_note_left = 0, 0.0

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
        if self.counting_down or self._banner_lines():
            return None  # (the wait has its own line; a notice hangs in the same strip: it wins)
        if self.rules.target is None and self.rules.phase == PLAYING:
            return t("practice.breaking")
        if self.mode == "call" and self.rules.pocket is not None and self.rules.phase == PLAYING:
            return t("practice.call_hint")
        return super()._hint_words()

    def _banner_lines(self) -> list[tuple[str, tuple[int, int, int]]]:
        """The one notice under the table, never more than two lines (a third would not fit in the
        strip below the table): why a life went, then what the rules did about the target, then
        the how-to-place line. The last to go is the first that can be guessed. In Sprint the
        seconds a shot won or cost are told in the same card: on the reason's own line for a cost,
        a line of their own for a gain."""
        base = super()._banner_lines()
        drag = base[len(base) - 1 :] if self._holding() else []
        lines = base[: len(base) - len(drag)]
        if self._time_note_left > 0.0 and self._time_note:
            if self._time_note > 0:
                lines.insert(0, (t("practice.time_gain", s=self._time_note), C.OK))
            elif lines:
                why, colour = lines[0]
                lines[0] = (f"{why} · {t('practice.time_loss', s=-self._time_note)}", colour)
        if self._hand_left > 0.0:
            lines.append((t("practice.hand_given"), C.ACCENT))
            drag = []  # (that line already says what to do)
        if self._swap_left > 0.0:
            lines.append((t(self._swap_key), C.ACCENT))
        return (lines + drag)[:2]

    def fire(self, shot: Shot) -> None:
        self._shot_visuals(shot, self.drag.bar_length)
        self.world.apply(shot)
        self.rules.on_shot()
        self._live = True
        self._break_pending = self.rules.shots == 1
        self._shot_left = PRACTICE_SHOT_S
        self._ready_left = 0.0  # (a shot was taken: the wait is over, whoever fired it)
        self._time_note_left = 0.0

    def _end_shot(self) -> None:
        self._live = False
        if not self.world.balls[0].in_play:
            self.world.respawn_cue()  # back on the table, ready to be placed
        old_target, time_before = self.rules.target, getattr(self.rules, "time_left", 0.0)
        res = self.rules.finish_shot(self.world.balls)
        self.app.achievements.practice_shot(self.mode, self.level, self.rules.streak, res.outcome)
        # Call the Pocket: the target went down, but not into the called pocket
        wrong = self.mode == "call" and res.lost_life == MISS and old_target in res.pocketed
        self._miss_key = "practice.miss_pocket" if wrong else None
        if self.mode == "sprint":
            self._time_note = round(self.rules.time_left - time_before)
            self._time_note_left = NOTICE_S
        if res.outcome in (WON, LOST):
            self._finish_run(res)
        elif res.lost_life:
            self._notify("foul", self._miss_key or res.lost_life)
        self._announce_retarget(old_target)

    def _announce_retarget(self, old_target: int | None) -> None:
        if self.rules.target_swapped:
            self._swap_left = NOTICE_S
            same_ball = self.mode == "call" and self.rules.target == old_target
            self._swap_key = "practice.pocket_swapped" if same_ball else "practice.target_swapped"
        if self.rules.hand_given:
            self._hand_left = NOTICE_S

    def _finish_run(self, res: ShotResult) -> None:
        self._ended_at = self._clock
        won = res.outcome == WON
        (self.app.audio.play_win if won else self.app.audio.play_lose)()
        old_best = best_for(self.app.settings, self.mode, self.level)
        best = max(old_best, self.rules.streak)
        if best > old_best:
            self.app.change_settings(**{best_field(self.mode, self.level): best})
        self._tally = Tally({"score": self.rules.streak, "shots": self.rules.shots, "fouls": best})
        self._ticks, self._tinged = dict.fromkeys(self._tally.targets, 0), set()

    # --- time: the wait before the run, then the clock of each shot (it costs a life)
    def update(self, dt: float) -> None:
        super().update(dt)
        if self._leave_open:
            return
        self._swap_left = max(0.0, self._swap_left - dt)
        self._hand_left = max(0.0, self._hand_left - dt)
        self._time_note_left = max(0.0, self._time_note_left - dt)
        self._dim_k = (
            1.0 if self.counting_down else max(0.0, self._dim_k - dt / PRACTICE_DIM_FADE_S)
        )
        if self.counting_down:
            self._count_down_to_start(dt)
            return
        if not self._can_aim():
            self._warned = -1
            return
        if self.mode == "sprint":
            res = self.rules.tick(dt)  # the one clock of the run: only while the player may aim
            if res is not None:
                self.drag.cancel()
                self._finish_run(res)
                return
        else:
            self._shot_left = max(0.0, self._shot_left - dt)
            if self._shot_left <= 0.0:
                self._timeout()
                return
        left = self._count()
        if left > PRACTICE_WARN_S:
            self._warned = -1
        elif left != self._warned:
            self._warned = left
            self.app.audio.play_clock_warn(left)

    def _count(self) -> int:
        """The number in the counter cell: the wait before the run, then the seconds left of the
        shot's clock (Sprint: of the run's)."""
        if self.counting_down:
            return math.ceil(self._ready_left)
        return math.ceil(self.rules.time_left if self.mode == "sprint" else self._shot_left)

    def _count_word(self) -> str:
        return (
            "practice.time"
            if self.mode == "sprint" and not self.counting_down
            else "practice.count"
        )

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
        old_target = self.rules.target
        res = self.rules.timeout(self.world.balls)
        self._miss_key = None
        if res.outcome in (WON, LOST):
            self._finish_run(res)
            return
        self._notice, self._notice_left = ("foul", res.lost_life), NOTICE_S
        self._callout = (t("callout.timeout"), C.AMBER, self._clock)
        self.app.audio.play_foul()
        self._announce_retarget(old_target)

    # --- drawing ------------------------------------------------------------------------------
    def _draw_cues(self, canvas: pg.Surface, v: View, over: bool) -> None:
        super()._draw_cues(canvas, v, over)
        if (
            self.mode == "call"
            and not over
            and not self.counting_down
            and self.rules.phase == PLAYING
            and self.rules.pocket is not None
        ):
            draw.draw_pocket_call(canvas, v, self.rules.pocket, self._clock)

    def _draw_overlays(self, canvas: pg.Surface, v: View, over: bool) -> None:
        """While the run waits to begin the whole screen is dark, only the counter is lit and the
        middle of the table says so; when the wait is over the screen clears."""
        if self._dim_k > 0.0 and not over:
            hud.dim_screen(canvas, self._dim_k)
            counting = self.counting_down
            hud.draw_practice_count(
                canvas, v, self._count(), counting, False, False, word=self._count_word()
            )
            if counting:
                hud.glow_text(canvas, v, t("practice.counting"), 30, C.WHITE, C.CYAN, CALLOUT_AT)
        super()._draw_overlays(canvas, v, over)

    def _draw_panel(self, canvas: pg.Surface, v: View) -> None:
        blink_on = int(self._clock * BLINK_HZ * 2) % 2 == 0
        counting = self.counting_down
        sprint = self.mode == "sprint"
        left = self.rules.time_left if sprint else self._shot_left
        hud.draw_practice_panel(
            canvas,
            v,
            streak=self.rules.streak,
            lives=None if sprint else self.rules.lives,
            best=best_for(self.app.settings, self.mode, self.level),
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
            count=self._count(),
            counting_down=counting,
            warn=not counting and left <= PRACTICE_WARN_S,
            blink_on=blink_on,
            keys=self.PANEL_KEYS,
            score_word=self._score_word(),
            count_word=self._count_word(),
        )

    def _score_word(self) -> str:
        """What the first cell and the card's big number are called: Sprint counts balls."""
        return "practice.potted" if self.mode == "sprint" else "practice.streak"

    def _shown_numbers(self) -> tuple[dict[str, int], tuple[float, float, float]]:
        tally, age = self._tally, self._clock - self._ended_at
        if tally is None:
            whole = {
                "score": self.rules.streak,
                "shots": self.rules.shots,
                "fouls": best_for(self.app.settings, self.mode, self.level),
            }
            return whole, (0.0, 0.0, 0.0)
        shown = {name: tally.value(name, age) for name in tally.targets}
        return shown, tuple(tally.flash(name, age) for name in tally.targets)

    def _lost_words(self) -> str | None:
        """Why the run was lost, or nothing for a win: two lines (out of lives, then the last
        shot's cause) joined by '\n'; in Sprint, the clock alone."""
        res = self.rules.last
        if self.rules.phase == WON or res is None or res.lost_life is None:
            return None
        if self.mode == "sprint":
            return t("practice.time_up")
        why = t("practice.last_one", why=t(self._miss_key or res.lost_life))
        return f"{t('practice.out_of_lives')}\n{why}"

    def _draw_result_frame(self, canvas: pg.Surface, v: View) -> None:
        hud.draw_result_frame(
            canvas,
            v,
            won=self.rules.phase == WON,
            reason=self._lost_words(),
            row_names=[t("hud.shots"), t("practice.best")],
            score_label=t(self._score_word()),
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
            score_label=t(self._score_word()),
            flashes=flashes,
            age=self._clock - self._ended_at,
            fx=self.result_fx,
            clock=self._clock,
        )
