"""The table: 8-ball practice, played by dragging back from the cue ball.

After a foul the cue ball is "in hand": drag it to where you want it.
Hotkeys: R restart, 1/2/3 feel, Esc menu.
"""

from __future__ import annotations

import math

import pygame as pg

from game.config import (
    BREAK_SHAKE_SPEED,
    DEFAULT_FEEL,
    FEEL_ORDER,
    FEEL_SETS,
    GRAB_RADIUS_M,
    MAX_FRAME_DT,
    NOTICE_S,
    PHYSICS_DT,
    PX_PER_M,
    RIPPLE_BALL_SPEED,
    RIPPLE_CUSHION_SPEED,
)
from game.i18n import t
from game.input.drag import DragAim
from game.physics import BallHitBall, BallHitCushion, BallPocketed, Shot, World, first_contact
from game.render import draw, hud
from game.render import palette as C
from game.render.fx import Fx
from game.render.layout import (
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
from game.rules.eight_ball import PLAYING, RERACK, WON, EightBall

BANNER_AT = (FIELD_X + FIELD_W / 2, FIELD_Y + 74)  # notices sit below the top middle pocket


class PlayScene:
    def __init__(self, app) -> None:
        self.app = app
        self.feel_key = DEFAULT_FEEL
        self.world = World(seed=0, feel=FEEL_SETS[self.feel_key])
        self.rules = EightBall()
        self.drag = DragAim()
        self.fx = Fx()
        self._acc = 0.0
        self._clock = 0.0  # drives the pulsing ring
        self._break_pending = True  # the first hard hit after a rack shakes the screen
        self._live = False  # a shot is rolling: judge it when everything stops
        self.placing = False  # the cue ball in hand is being dragged
        self._place_ok = True  # ... and the pointer is over an allowed spot
        self._notice: tuple[str, str] | None = None  # (kind "foul"|"info", i18n key)
        self._notice_left = 0.0
        self._hover: str | None = None  # hovered button of the result card
        self.set_view(app.view)

    def set_view(self, v: View) -> None:
        """(Re)build everything that depends on the resolution."""
        self.view = v
        self.sprites = draw.BallSprites(v)
        self.table = draw.build_table(v)

    # --- game flow -------------------------------------------------------------------
    def new_game(self) -> None:
        self.world.rack()
        self.rules.reset()
        self.drag.cancel()
        self.fx.clear()
        self._acc = 0.0
        self._live = False
        self.placing = False
        self._notice, self._notice_left = None, 0.0
        self._break_pending = True

    def set_feel(self, key: str) -> None:
        self.feel_key = key
        self.world.feel = FEEL_SETS[key]

    def _can_aim(self) -> bool:
        return (
            self.rules.phase == PLAYING
            and self.world.balls[0].in_play
            and self.world.at_rest()
            and not self.rules.cue_in_hand
        )

    def fire(self, shot: Shot) -> None:
        """Every cue shot goes through here."""
        self.world.apply(shot)
        self.rules.on_shot()  # also ends "cue ball in hand"
        self._live = True
        self.placing = False
        self._notice_left = 0.0
        self._break_pending = self.rules.is_break
        self.app.audio.play_shot(shot.power)

    def shake_offset(self) -> tuple[float, float]:
        return self.fx.shake_offset()

    def _notify(self, kind: str, key: str) -> None:
        self._notice, self._notice_left = (kind, key), NOTICE_S

    def _end_shot(self) -> None:
        """Every ball has stopped: let the rules judge the shot and show what happened."""
        self._live = False
        res = self.rules.finish_shot()
        if res.outcome == RERACK:
            self.world.rack()
            self.fx.clear()
            self.rules.rerack()
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

    # --- events ----------------------------------------------------------------------
    def handle_event(self, e: pg.event.Event) -> None:
        if self.rules.phase != PLAYING:
            self._result_event(e)
            return
        if self._hand_event(e):
            return
        if e.type == pg.KEYDOWN:
            self._key(e.key)
        elif e.type == pg.MOUSEBUTTONDOWN:
            if e.button == 1 and self._can_aim():
                cue = self.world.balls[0]
                cx, cy = to_px(cue.x, cue.y)
                if math.hypot(e.pos[0] - cx, e.pos[1] - cy) <= GRAB_RADIUS_M * PX_PER_M:
                    self.drag.begin((cx, cy), e.pos)
            elif e.button == 3:
                self.drag.cancel()
        elif e.type == pg.MOUSEMOTION:
            self.drag.move(e.pos)
        elif e.type == pg.MOUSEBUTTONUP and e.button == 1 and self.drag.active:
            self.drag.move(e.pos)
            shot = self.drag.end()
            if shot is not None:
                self.fire(shot)

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
            self._hover = next(
                (k for k, r in hud.RESULT_BUTTONS.items() if r.collidepoint(e.pos)), None
            )
        elif e.type == pg.MOUSEBUTTONDOWN and e.button == 1:
            if hud.RESULT_BUTTONS["new"].collidepoint(e.pos):
                self.app.audio.play_click()
                self.new_game()
            elif hud.RESULT_BUTTONS["menu"].collidepoint(e.pos):
                self.app.audio.play_click()
                self.app.go_menu()
        elif e.type == pg.KEYDOWN:
            if e.key in (pg.K_RETURN, pg.K_KP_ENTER, pg.K_SPACE, pg.K_r):
                self.new_game()
            elif e.key == pg.K_ESCAPE:
                self.app.go_menu()

    def _key(self, key: int) -> None:
        if key == pg.K_r:
            self.new_game()
        elif key == pg.K_ESCAPE:
            if self.drag.active:
                self.drag.cancel()
            else:
                self.app.go_menu()
        elif key in (pg.K_1, pg.K_2, pg.K_3):
            self.set_feel(FEEL_ORDER[key - pg.K_1])

    # --- update / draw ------------------------------------------------------------------
    def update(self, dt: float) -> None:
        self._clock += dt
        self._notice_left = max(0.0, self._notice_left - dt)
        self._acc += min(dt, MAX_FRAME_DT)
        frame_events = []
        while self._acc >= PHYSICS_DT:
            self._acc -= PHYSICS_DT
            events = self.world.step()
            if events:
                self.rules.on_events(events)
                self._show_events(events)
                frame_events += events
        if frame_events:
            self.app.audio.on_events(frame_events)
        self.fx.update(dt)
        if self._live and self.world.at_rest():
            self._end_shot()

    def _show_events(self, events) -> None:
        balls = self.world.balls
        for ev in events:
            if isinstance(ev, BallHitBall):
                if ev.speed >= RIPPLE_BALL_SPEED:
                    a, b = balls[ev.a], balls[ev.b]
                    self.fx.add_ripple((a.x + b.x) / 2, (a.y + b.y) / 2)
                if self._break_pending and ev.speed >= BREAK_SHAKE_SPEED:
                    self.fx.shake()
                    self._break_pending = False
            elif isinstance(ev, BallHitCushion):
                if ev.speed >= RIPPLE_CUSHION_SPEED:
                    self.fx.add_ripple(balls[ev.ball].x, balls[ev.ball].y)
            elif isinstance(ev, BallPocketed):
                self.fx.add_drop(ev.ball, balls[ev.ball].x, balls[ev.ball].y, ev.pocket)

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
        canvas.blit(self.table, (0, 0))
        draw.draw_balls(canvas, v, self.world.balls, self.sprites)
        self.fx.draw(canvas, v, self.sprites)
        cue = self.world.balls[0]
        over = self.rules.phase != PLAYING
        if self._holding():
            pulse = 0.5 + 0.5 * math.sin(self._clock * 7.5)
            color = (*C.ACCENT, round(150 + 105 * pulse)) if self._place_ok else (*C.ERROR, 255)
            draw.draw_ring(canvas, v, to_px(cue.x, cue.y), draw.RIM + 5, color)
        if self.drag.has_direction and cue.in_play and not over:
            a = self.drag.angle
            d = (math.cos(a), math.sin(a))
            contact = first_contact(self.world.balls, (cue.x, cue.y), d)
            draw.draw_aim(canvas, v, cue, contact, d, self.drag.bar_length, self.drag.power)
        hud.draw_panel(
            canvas,
            v,
            shots=self.rules.shots,
            fouls=self.rules.fouls,
            pocketed=self.rules.pocketed,
            group=self.rules.group,
            eight_next=self.rules.eight_is_next(),
            feel_key=self.feel_key,
            muted=self.app.audio.muted,
            moving=not self.world.at_rest(),
            sprites=self.sprites,
        )
        if not over:
            hud.banner(canvas, v, self._banner_lines(), BANNER_AT)
        if self.rules.shots == 0 and self._can_aim() and not self.drag.active:
            hud.text(
                canvas,
                v,
                t("hud.hint"),
                16,
                C.TEXT_DIM,
                (OUTER_X + OUTER_W // 2, OUTER_Y + OUTER_H + 26),
                center=True,
            )
        if over:
            self._draw_result(canvas, v)

    def _draw_result(self, canvas: pg.Surface, v: View) -> None:
        res = self.rules.last
        hud.draw_result(
            canvas,
            v,
            won=self.rules.phase == WON,
            reason=t(res.reason) if res and res.reason else None,
            rows=[(t("hud.shots"), str(self.rules.shots)), (t("hud.fouls"), str(self.rules.fouls))],
            hover=self._hover,
        )
