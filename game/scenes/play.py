"""The table: 8-ball practice, played by dragging back from the cue ball (a neon cue follows).

After a foul the cue ball is "in hand": drag it to where you want it.
Hotkeys: R restart, H how to play, Esc menu (M mute and F11 full screen belong to the App).
"""

from __future__ import annotations

import math
import os

import pygame as pg

from game.config import (
    BREAK_SHAKE_SPEED,
    GRAB_RADIUS_M,
    MAX_FRAME_DT,
    NOTICE_S,
    PHYSICS_DT,
    PX_PER_M,
    RIPPLE_BALL_SPEED,
    RIPPLE_CUSHION_SPEED,
    SPIN_SETS,
    SPIN_WHEEL_STEP,
    STRONG_HIT_SPEED,
)
from game.i18n import t
from game.input.drag import DragAim, Knob
from game.physics import BallHitBall, BallHitCushion, BallPocketed, Shot, World, first_contact
from game.render import draw, hud
from game.render import palette as C
from game.render.frozen import FrozenScene
from game.render.fx import Fx
from game.render.layout import (
    FIELD_H,
    FIELD_W,
    FIELD_X,
    FIELD_Y,
    OUTER_H,
    OUTER_W,
    OUTER_X,
    OUTER_Y,
    to_m,
    to_px,
)
from game.render.view import View
from game.rules.eight_ball import LOST, PLAYING, RERACK, WON, EightBall
from game.tally import Tally

# notices hang under the table, in the free strip below it (on the cloth they hid rolling balls)
RESULT_FREEZE_S = 1.7  # the card has been up this long: the waves on the table have died out
BANNER_AT = (OUTER_X + OUTER_W / 2, OUTER_Y + OUTER_H + 12)
CALLOUT_AT = (FIELD_X + FIELD_W / 2, FIELD_Y + FIELD_H / 2)  # the big arcade word pops here
# notice key -> (call-out word key, colour, sound)
CALLOUTS = {
    "foul": ("callout.foul", C.ERROR, "foul"),
    "notice.group_solid": ("callout.solid", C.CYAN, "notice"),
    "notice.group_stripe": ("callout.stripe", C.CYAN, "notice"),
    "notice.eight": ("callout.eight", C.MAGENTA, "notice"),
    "notice.rerack": ("callout.rerack", C.AMBER, "notice"),
}


class PlayScene:
    def __init__(self, app) -> None:
        self.app = app
        # the table always feels "medium" (the user removed the choice); NEONPOOL_SPIN_SET picks
        # which named spin set to play-test (NHE / VUA / MANH) and goes once one is chosen
        spin_set = SPIN_SETS.get(os.environ.get("NEONPOOL_SPIN_SET", ""))
        self.world = World(seed=0, spin=spin_set)
        self.spin = 0.0  # where the cue will strike the white ball: -1 (low) .. +1 (high)
        self._dial_drag = False  # the spin dial is being dragged
        self._dial_lit = 0.0  # how lit the dial is (the pointer is on it / dragging)
        self.rules = EightBall()
        self.drag = DragAim()
        self.fx = Fx()
        self.board = hud.Scoreboard()
        self._acc = 0.0
        self._clock = 0.0  # drives every light on this screen (photos of the scene repeat)
        self._break_pending = True  # the first hard hit after a rack shakes the screen
        self._live = False  # a shot is rolling: judge it when everything stops
        self.placing = False  # the cue ball in hand is being dragged
        self._place_ok = True  # ... and the pointer is over an allowed spot
        self._notice: tuple[str, str] | None = None  # (kind "foul"|"info", i18n key)
        self._notice_left = 0.0
        self._callout: tuple[str, tuple[int, int, int], float] | None = None  # (word, colour, at)
        self._lunge: tuple[float, tuple[float, float], tuple[float, float], float, float] | None
        self._lunge = None  # the cue darting at the ball: (at, centre, shot dir, pull, power)
        self.pocket_times: dict[int, float] = {}  # ball -> when it went in (the panel strikes it)
        self._ended_at = -99.0  # when the game ended (the result card grows in)
        self._tally: Tally | None = None  # the card's numbers counting up (None: show them whole)
        self._ticks: dict[str, int] = {}  # how many ticks of each number have sounded
        self._tinged: set[str] = set()  # the numbers whose bell has rung
        self._frozen = FrozenScene()  # the table behind the result card, once it will not change
        self._pointer: tuple[float, float] | None = None  # where the mouse is (logical)
        self._cue_alpha = 0.0  # the cue fades in while the pointer is on the cue ball
        self.knob = Knob(0.0)  # the cue as a dial round the cue ball: where the shot goes
        self._hover: str | None = None  # hovered button of the result card
        self.result_fx = hud.ButtonFx()  # how the result card's buttons move
        self.set_view(app.view)

    def set_view(self, v: View) -> None:
        """(Re)build everything that depends on the resolution."""
        self.view = v
        self.sprites = draw.BallSprites(v)
        self.table = draw.build_table(v)
        if hasattr(self, "_frozen"):
            self._frozen.clear()

    # --- game flow -------------------------------------------------------------------
    def new_game(self) -> None:
        self.world.rack()
        self.rules.reset()
        self.drag.cancel()
        self.fx.clear()
        self._acc = 0.0
        self._live = False
        self.placing = False
        self.spin, self._dial_drag = 0.0, False
        self._notice, self._notice_left, self._callout, self._lunge = None, 0.0, None, None
        self.pocket_times.clear()
        self._break_pending = True
        self._tally = None
        self._frozen.clear()

    def _can_aim(self) -> bool:
        return (
            self.rules.phase == PLAYING
            and self.world.balls[0].in_play
            and self.world.at_rest()
            and not self.rules.cue_in_hand
        )

    def fire(self, shot: Shot) -> None:
        """Every cue shot goes through here."""
        self._shot_visuals(shot, self.drag.bar_length)
        self.world.apply(shot)
        self.rules.on_shot()  # also ends "cue ball in hand"
        self._live = True
        self._break_pending = self.rules.is_break

    def _shot_visuals(self, shot: Shot, pull_px: float) -> None:
        """What a shot looks and sounds like: the cue darts at the ball, the clutter clears."""
        cue = self.world.balls[0]
        d = (math.cos(shot.angle), math.sin(shot.angle))
        self._lunge = (self._clock, to_px(cue.x, cue.y), d, pull_px, shot.power)
        self._dial_drag = False  # the spin stays as set: the next shot uses it too
        self.placing = False
        self._notice_left = 0.0
        self._callout = None
        self._cue_alpha = 0.0  # the darting cue of the shot takes over
        self.knob.angle = shot.angle
        self.app.audio.play_shot(shot.power)

    def shake_offset(self) -> tuple[float, float]:
        return self.fx.shake_offset()

    def _notify(self, kind: str, key: str) -> None:
        self._notice, self._notice_left = (kind, key), NOTICE_S
        word, colour, sound = CALLOUTS["foul" if kind == "foul" else key]
        self._callout = (t(word), colour, self._clock)
        getattr(self.app.audio, f"play_{sound}")()

    def _end_shot(self) -> None:
        """Every ball has stopped: let the rules judge the shot and show what happened."""
        self._live = False
        res = self.rules.finish_shot()
        if res.outcome == RERACK:
            self.world.rack()
            self.fx.clear()
            self.rules.rerack()
            self.pocket_times.clear()
            self._break_pending = True
            self._notify("info", "notice.rerack")
        elif res.outcome is None:
            if not self.world.balls[0].in_play:
                self.world.respawn_cue()  # back on the table, ready to be placed
            if res.fouls:
                self._notify("foul", res.fouls[0])
            elif res.group:
                self._notify("info", f"notice.group_{res.group}")
            elif res.pocketed and self.rules.eight_is_next():
                self._notify("info", "notice.eight")
        elif res.outcome in (WON, LOST):
            self._ended_at = self._clock
            (self.app.audio.play_win if res.outcome == WON else self.app.audio.play_lose)()
            self._tally = Tally(
                {"score": self.rules.score, "shots": self.rules.shots, "fouls": self.rules.fouls}
            )
            self._ticks, self._tinged = dict.fromkeys(self._tally.targets, 0), set()

    # --- events ----------------------------------------------------------------------
    def handle_event(self, e: pg.event.Event) -> None:
        if self.rules.phase != PLAYING:
            self._result_event(e)
            return
        if e.type in (pg.MOUSEMOTION, pg.MOUSEBUTTONDOWN, pg.MOUSEBUTTONUP):
            self._pointer = e.pos
        if e.type == pg.MOUSEBUTTONDOWN:
            self._callout = None  # the player is acting: the big word gets out of the way
        if self._dial_event(e) or self._hand_event(e):
            return
        if e.type == pg.KEYDOWN:
            self._key(e.key)
        elif e.type == pg.MOUSEBUTTONDOWN:
            if e.button == 1 and self._can_aim():
                cue = self.world.balls[0]
                cx, cy = to_px(cue.x, cue.y)
                if math.hypot(e.pos[0] - cx, e.pos[1] - cy) <= GRAB_RADIUS_M * PX_PER_M:
                    self.drag.begin(e.pos)
                    self.knob.release()
            elif e.button == 3:
                self.drag.cancel()
        elif e.type == pg.MOUSEMOTION:
            self.drag.move(e.pos)
            if not self.drag.active:
                self._turn_knob(e.pos)
            elif self.drag.has_direction:
                self.knob.angle = self.drag.angle  # a cancelled pull leaves the cue where it was
        elif e.type == pg.MOUSEBUTTONUP and e.button == 1 and self.drag.active:
            self.drag.move(e.pos)
            shot = self.drag.end(self.spin)
            if shot is not None:
                self.fire(shot)

    def _dial_ok(self) -> bool:
        """The spin can be set: the game is on and every ball is still."""
        return self.rules.phase == PLAYING and self.world.balls[0].in_play and self.world.at_rest()

    def _over_dial(self, pos: tuple[float, float]) -> bool:
        return math.dist(pos, hud.SPIN_C) <= hud.SPIN_HIT_R

    def _set_spin(self, value: float, press: bool = False) -> None:
        """Set the spin; a soft low 'tok' sounds when it reaches another step (and on a press)."""
        old = self._spin_step()
        value = max(-1.0, min(1.0, round(value * 32) / 32))  # steps of 1/32: exact, tidy
        self.spin = 0.0 if abs(value) < 0.08 else value  # the middle is easy to hit
        if press or self._spin_step() != old:
            self.app.audio.play_spin(self.spin)

    def _spin_step(self) -> int:
        """Which of the nine steps (-4 .. +4, a quarter each) the spin is nearest to."""
        return round(self.spin * 4)

    def _dial_event(self, e: pg.event.Event) -> bool:
        """Set the spin: press or drag the dot on the dial, or roll the wheel. True if used."""
        if e.type == pg.MOUSEWHEEL:
            if self._dial_ok() and e.y:  # wheel up = higher
                self._set_spin(self.spin + SPIN_WHEEL_STEP * (1 if e.y > 0 else -1))
                return True
        elif e.type == pg.MOUSEBUTTONDOWN and e.button == 1:
            if self._dial_ok() and self._over_dial(e.pos):
                self._dial_drag = True
                self._set_spin(hud.spin_value(e.pos[1]), press=True)
                return True
        elif e.type == pg.MOUSEMOTION and self._dial_drag:
            self._set_spin(hud.spin_value(e.pos[1]))
            return True
        elif e.type == pg.MOUSEBUTTONUP and e.button == 1 and self._dial_drag:
            self._dial_drag = False
            return True
        return False

    def _turn_knob(self, pos: tuple[float, float]) -> None:
        """Going round the cue ball with the pointer turns the cue, like a dial."""
        if self._can_aim() and self._over_cue():
            cue = self.world.balls[0]
            self.knob.move(to_px(cue.x, cue.y), pos)
        else:
            self.knob.release()

    def _shakes(self) -> bool:
        """The screen may shake (the "Shake" setting; the how-to-play studio has no settings)."""
        settings = getattr(self.app, "settings", None)
        return settings is None or settings.shake

    def _hand_event(self, e: pg.event.Event) -> bool:
        """Place the cue ball after a foul: press it, drag, let go. True if the event was used."""
        cue = self.world.balls[0]
        if not (self.rules.cue_in_hand and cue.in_play and self.world.at_rest()):
            self.placing = False
            return False
        if e.type == pg.MOUSEBUTTONDOWN and e.button == 1:
            cx, cy = to_px(cue.x, cue.y)
            if math.hypot(e.pos[0] - cx, e.pos[1] - cy) <= GRAB_RADIUS_M * PX_PER_M:
                self.placing, self._place_ok = True, True
                return True
        elif e.type == pg.MOUSEMOTION and self.placing:
            self._place_ok = self.world.place_cue(*to_m(*e.pos))  # False: it stays on its last spot
        elif e.type == pg.MOUSEBUTTONUP and e.button == 1 and self.placing:
            self.placing = False
            self.rules.cue_placed()
            self.app.audio.play_click()
            return True
        return False

    def _result_event(self, e: pg.event.Event) -> None:
        if e.type == pg.MOUSEMOTION:
            hover = next((k for k, r in hud.RESULT_BUTTONS.items() if r.collidepoint(e.pos)), None)
            if hover is not None and hover != self._hover:
                self.app.audio.play_hover()
            self._hover = hover
        elif e.type == pg.MOUSEBUTTONDOWN and e.button == 1:
            if hud.RESULT_BUTTONS["new"].collidepoint(e.pos):
                self.app.audio.play_click()
                self.result_fx.press("new", self._clock)
                self.new_game()
            elif hud.RESULT_BUTTONS["menu"].collidepoint(e.pos):
                self.app.audio.play_click()
                self.result_fx.press("menu", self._clock)
                self.app.go_menu()
        elif e.type == pg.KEYDOWN:
            if e.key in (pg.K_RETURN, pg.K_KP_ENTER, pg.K_SPACE, pg.K_r):
                self.new_game()
            elif e.key == pg.K_ESCAPE:
                self.app.go_menu()

    def _key(self, key: int) -> None:
        if key == pg.K_r:
            self.new_game()
        elif key == pg.K_h:
            self.app.open_help()
        elif key == pg.K_ESCAPE:
            if self.drag.active:
                self.drag.cancel()
            else:
                self.app.go_menu()

    # --- update / draw ------------------------------------------------------------------
    def update(self, dt: float) -> None:
        self._clock += dt
        self._notice_left = max(0.0, self._notice_left - dt)
        frame_events = self._step_world(dt)
        if frame_events:
            self.app.audio.on_events(frame_events)
        self.fx.update(dt)
        want = 1.0 if self._dial_drag else 0.6 if self._dial_hover() else 0.0
        self._dial_lit += max(-1.0, min(1.0, (want - self._dial_lit) * 8.0 * dt)) if dt else 0.0
        if self.rules.phase != PLAYING:
            chosen = self._hover or "new"  # Enter starts a new game: that button is lit
            self.result_fx.update(dt, chosen, hud.RESULT_BUTTONS, self._clock)
            self._tally_sounds()
        if self._live and self.world.at_rest():
            self._end_shot()
        self._fade_cue(dt)

    def _step_world(self, dt: float) -> list:
        """Run the simulation for `dt` (whole fixed steps); the events of those steps."""
        self._acc += min(dt, MAX_FRAME_DT)
        frame_events = []
        while self._acc >= PHYSICS_DT:
            self._acc -= PHYSICS_DT
            events = self.world.step()
            if events:
                self.rules.on_events(events)
                self._show_events(events)
                frame_events += events
        return frame_events

    def _tally_sounds(self) -> None:
        """The card's numbers tick while they climb and ring a bell when they stop."""
        tally, audio = self._tally, self.app.audio
        if tally is None:
            return
        age = self._clock - self._ended_at
        won = self.rules.phase == WON
        for name in tally.targets:
            ticks = tally.ticks_done(name, age)
            if ticks > self._ticks.get(name, 0):  # several in one frame: only the last is heard
                self._ticks[name] = ticks
                audio.play_tally_tick(tally.tick_pitch(name, ticks))
            if tally.finished(name, age) and name not in self._tinged and tally.targets[name]:
                self._tinged.add(name)
                audio.play_tally_ting(won, big=name == "score")

    def _dial_hover(self) -> bool:
        return self._dial_ok() and self._pointer is not None and self._over_dial(self._pointer)

    def _over_cue(self) -> bool:
        """The pointer is on the cue ball (where pressing would start a shot)."""
        if self._pointer is None:
            return False
        cue = self.world.balls[0]
        return math.dist(self._pointer, to_px(cue.x, cue.y)) <= GRAB_RADIUS_M * PX_PER_M

    def _fade_cue(self, dt: float) -> None:
        """The cue shows while the pointer is on a ball that can be shot, and while aiming."""
        if self._can_aim() and (self.drag.active or self._over_cue()):
            self._cue_alpha = min(1.0, self._cue_alpha + dt / draw.CUE_FADE_IN_S)
        else:
            self._cue_alpha = max(0.0, self._cue_alpha - dt / draw.CUE_FADE_OUT_S)

    def _show_events(self, events) -> None:
        balls = self.world.balls
        for ev in events:
            if isinstance(ev, BallHitBall):
                if ev.speed >= RIPPLE_BALL_SPEED:
                    a, b = balls[ev.a], balls[ev.b]
                    self.fx.add_ripple((a.x + b.x) / 2, (a.y + b.y) / 2, "ball")
                if self._break_pending and ev.speed >= BREAK_SHAKE_SPEED:
                    if self._shakes():
                        self.fx.shake(1.0)
                    self._break_pending = False
                elif 0 in (ev.a, ev.b):
                    self._hard_hit(ev.speed)
            elif isinstance(ev, BallHitCushion):
                if ev.speed >= RIPPLE_CUSHION_SPEED:
                    self.fx.add_ripple(balls[ev.ball].x, balls[ev.ball].y, "cushion")
                if ev.ball == 0:
                    self._hard_hit(ev.speed)
            elif isinstance(ev, BallPocketed):
                self.fx.add_drop(ev.ball, balls[ev.ball].x, balls[ev.ball].y, ev.pocket)
                if ev.ball:
                    self.pocket_times[ev.ball] = self._clock

    def _hard_hit(self, speed: float) -> None:
        """The cue ball hits very hard: a small shake, stronger for a harder hit."""
        if speed >= STRONG_HIT_SPEED and self._shakes():
            self.fx.shake(0.35 + 0.4 * min(1.0, (speed - STRONG_HIT_SPEED) / 2.0))

    def _banner_lines(self) -> list[tuple[str, tuple[int, int, int]]]:
        lines = []
        if self._notice and self._notice_left > 0:
            kind, key = self._notice
            lines.append((t(key), C.ERROR if kind == "foul" else C.ACCENT))
        if self._holding():
            lines.append((t("notice.hand_drag"), C.TEXT))
        return lines

    def _holding(self) -> bool:
        """The cue ball is waiting to be placed (it is on the table and everything is still)."""
        return (
            self.rules.phase == PLAYING
            and self.rules.cue_in_hand
            and self.world.balls[0].in_play
            and self.world.at_rest()
        )

    def draw(self, canvas: pg.Surface) -> None:
        v = self.view
        if self._frozen.covers(canvas.get_size()) and self.rules.phase != PLAYING:
            # the card has settled and the table behind it is a picture: paste it, draw the rest
            self._frozen.paste_baked(
                canvas, hud.RESULT_DIM_ALPHA, lambda base: self._draw_result_frame(base, v)
            )
            self._draw_result_live(canvas, v)
            return
        canvas.blit(self.table, (0, 0))
        draw.draw_balls(canvas, v, self.world.balls, self.sprites)
        self.fx.draw(canvas, v, self.sprites)
        cue = self.world.balls[0]
        over = self.rules.phase != PLAYING
        if self._holding():
            pulse = 0.5 + 0.5 * math.sin(self._clock * 7.5)
            color = (*C.ACCENT, round(150 + 105 * pulse)) if self._place_ok else (*C.ERROR, 255)
            draw.draw_ring(canvas, v, to_px(cue.x, cue.y), draw.RIM + 5, color)
        self._draw_cues(canvas, v, over)
        self._draw_lunge(canvas, v)
        self._draw_panel(canvas, v)
        self._draw_overlays(canvas, v, over)

    def _draw_cues(self, canvas: pg.Surface, v: View, over: bool) -> None:
        """The aiming line and the cue: pulled back while aiming, resting behind the ball."""
        cue = self.world.balls[0]
        if self.drag.has_direction and cue.in_play and not over:
            a = self.drag.angle
            d = (math.cos(a), math.sin(a))
            contact = first_contact(self.world.balls, (cue.x, cue.y), d)
            draw.draw_aim(canvas, v, cue, contact, d)
            draw.draw_cue(
                canvas,
                v,
                to_px(cue.x, cue.y),
                d,
                self.drag.bar_length,
                self.drag.power,
                self._clock,
            )
        elif self._cue_alpha > 0.01 and cue.in_play and not over:  # resting behind the ball
            centre = to_px(cue.x, cue.y)
            d = (math.cos(self.knob.angle), math.sin(self.knob.angle))
            draw.draw_cue(canvas, v, centre, d, 0.0, 0.0, self._clock, self._cue_alpha)

    def _draw_panel(self, canvas: pg.Surface, v: View) -> None:
        """The panel beside the table."""
        hud.draw_panel(
            canvas,
            v,
            shots=self.rules.shots,
            fouls=self.rules.fouls,
            pocketed=self.rules.pocketed,
            group=self.rules.group,
            eight_next=self.rules.eight_is_next(),
            muted=self.app.audio.muted,
            moving=not self.world.at_rest(),
            sprites=self.sprites,
            clock=self._clock,
            board=self.board,
            pocket_times=self.pocket_times,
            spin=self.spin,
            spin_lit=self._dial_lit,
            spin_on=self._dial_ok(),
        )

    def _draw_overlays(self, canvas: pg.Surface, v: View, over: bool) -> None:
        """Notices, the big arcade word, the hint, and the result card."""
        if not over:
            hud.banner(canvas, v, self._banner_lines(), BANNER_AT)
            if self._callout is not None:
                word, colour, at = self._callout
                home = (BANNER_AT[0], BANNER_AT[1] + 20)
                hud.draw_callout(canvas, v, word, colour, self._clock - at, CALLOUT_AT, home)
        if self.rules.shots == 0 and self._can_aim() and not self.drag.active:
            hud.text(
                canvas,
                v,
                t("hud.hint"),
                16,
                C.TEXT_DIM,
                (OUTER_X + OUTER_W // 2, OUTER_Y + OUTER_H + 30),
                center=True,
            )
        if over:
            if self._clock - self._ended_at >= RESULT_FREEZE_S:
                self._frozen.under(canvas)  # the table as it is now: its waves have died out
            self._draw_result(canvas, v)

    def _draw_lunge(self, canvas: pg.Surface, v: View) -> None:
        """After a shot the cue darts to where the ball was, then goes out."""
        if self._lunge is None:
            return
        at, centre, d, pull, power = self._lunge
        age = self._clock - at
        if age >= draw.LUNGE_S + draw.FADE_S:
            self._lunge = None
            return
        if age < draw.LUNGE_S:
            k = age / draw.LUNGE_S
            draw.draw_cue(canvas, v, centre, d, pull * (1 - k * k), power, self._clock)
        else:
            fade = 1 - (age - draw.LUNGE_S) / draw.FADE_S
            draw.draw_cue(canvas, v, centre, d, 0.0, power, self._clock, alpha=fade)

    def _shown_numbers(self) -> tuple[dict[str, int], tuple[float, float, float]]:
        """What the card's numbers show now (they count up), and how much each glows."""
        tally, age = self._tally, self._clock - self._ended_at
        if tally is None:  # not counting (a game photographed, or ended some other way): whole
            whole = {
                "score": self.rules.score,
                "shots": self.rules.shots,
                "fouls": self.rules.fouls,
            }
            return whole, (0.0, 0.0, 0.0)
        shown = {name: tally.value(name, age) for name in tally.targets}
        return shown, tuple(tally.flash(name, age) for name in tally.targets)

    def _draw_result_frame(self, canvas: pg.Surface, v: View) -> None:
        """The card's parts that never move (baked into the picture of the settled card)."""
        res = self.rules.last
        hud.draw_result_frame(
            canvas,
            v,
            won=self.rules.phase == WON,
            reason=t(res.reason) if res and res.reason else None,
            row_names=[t("hud.shots"), t("hud.fouls")],
        )

    def _draw_result_live(self, canvas: pg.Surface, v: View) -> None:
        shown, flashes = self._shown_numbers()
        hud.draw_result_live(
            canvas,
            v,
            score=shown["score"],
            values=[shown["shots"], shown["fouls"]],
            fx=self.result_fx,
            clock=self._clock,
            flashes=flashes,
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
            rows=[(t("hud.shots"), shown["shots"]), (t("hud.fouls"), shown["fouls"])],
            flashes=flashes,
            hover=self._hover,
            age=self._clock - self._ended_at,
            fx=self.result_fx,
            clock=self._clock,
        )
