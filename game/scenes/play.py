"""The table: free play. Mouse drag-back to shoot; R restarts; 1/2/3 change the feel; G grid."""

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
    PHYSICS_DT,
    PX_PER_M,
    RIPPLE_BALL_SPEED,
    RIPPLE_CUSHION_SPEED,
)
from game.i18n import t
from game.input.drag import DragAim
from game.physics import BallHitBall, BallHitCushion, BallPocketed, World, first_contact
from game.render import draw, hud
from game.render import palette as C
from game.render.fx import Fx
from game.render.layout import OUTER_H, OUTER_W, OUTER_X, OUTER_Y, to_px
from game.render.view import View
from game.rules.free_play import FreePlay


class PlayScene:
    def __init__(self, app) -> None:
        self.app = app
        self.feel_key = DEFAULT_FEEL
        self.world = World(seed=0, feel=FEEL_SETS[self.feel_key])
        self.rules = FreePlay()
        self.drag = DragAim()
        self.fx = Fx()
        self.show_grid = False
        self._acc = 0.0
        self._break_pending = True  # the first hard hit after a rack shakes the screen
        self.set_view(app.view)

    def set_view(self, v: View) -> None:
        """(Re)build everything that depends on the resolution."""
        self.view = v
        self.sprites = draw.BallSprites(v)
        self.table = draw.build_table(v)
        self.grid = draw.build_grid(v)

    # --- game flow -------------------------------------------------------------------
    def new_game(self) -> None:
        self.world.rack()
        self.rules.reset()
        self.drag.cancel()
        self.fx.clear()
        self._acc = 0.0

    def set_feel(self, key: str) -> None:
        self.feel_key = key
        self.world.feel = FEEL_SETS[key]

    def _can_aim(self) -> bool:
        return self.world.balls[0].in_play and self.world.at_rest()

    def shake_offset(self) -> tuple[float, float]:
        return self.fx.shake_offset()

    # --- events ----------------------------------------------------------------------
    def handle_event(self, e: pg.event.Event) -> None:
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
                self.world.apply(shot)
                self.rules.on_shot()
                self._break_pending = self.rules.shots == 1
                self.app.audio.play_shot(shot.power)

    def _key(self, key: int) -> None:
        if key == pg.K_r:
            self.new_game()
        elif key == pg.K_g:
            self.show_grid = not self.show_grid
        elif key == pg.K_ESCAPE:
            if self.drag.active:
                self.drag.cancel()
            else:
                self.app.go_menu()
        elif key in (pg.K_1, pg.K_2, pg.K_3):
            self.set_feel(FEEL_ORDER[key - pg.K_1])

    # --- update / draw ------------------------------------------------------------------
    def update(self, dt: float) -> None:
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
        if (
            not self.world.balls[0].in_play
            and self.world.at_rest()
            and self.rules.take_cue_respawn()
        ):
            self.world.respawn_cue()

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

    def draw(self, canvas: pg.Surface) -> None:
        v = self.view
        canvas.blit(self.table, (0, 0))
        if self.show_grid:
            canvas.blit(self.grid, (0, 0))
        draw.draw_balls(canvas, v, self.world.balls, self.sprites)
        self.fx.draw(canvas, v, self.sprites)
        cue = self.world.balls[0]
        if self.drag.has_direction and cue.in_play:
            a = self.drag.angle
            d = (math.cos(a), math.sin(a))
            contact = first_contact(self.world.balls, (cue.x, cue.y), d)
            draw.draw_aim(canvas, v, cue, contact, d, self.drag.bar_length, self.drag.power)
        draw.draw_power_bar(canvas, v, self.drag.power)
        hud.draw_panel(
            canvas,
            v,
            shots=self.rules.shots,
            pocketed=self.rules.pocketed,
            feel_key=self.feel_key,
            muted=self.app.audio.muted,
            moving=not self.world.at_rest(),
            sprites=self.sprites,
        )
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
