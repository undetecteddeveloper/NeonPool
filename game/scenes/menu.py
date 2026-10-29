"""Opening menu: Play / How to play / Language / Quit, on a night of slow ribbons of light."""

from __future__ import annotations

import math

import pygame as pg

from game import i18n
from game.config import LOGICAL_SIZE
from game.i18n import t
from game.render import backdrop, hud
from game.render import palette as C
from game.render.draw import BallSprites, blit_pm
from game.render.view import View
from game.render.waves import MENU, Waves

ITEMS = ("play", "help", "language", "quit")
BTN_W, BTN_H, BTN_GAP = 320, 58, 18
FIRST_Y = 330
DECOR_SCALE = 3  # decorative balls are drawn natively 3x bigger, not stretched
BREATH_S = 4.0  # the title's halo swells and fades once in this many seconds


class MenuScene:
    def __init__(self, app) -> None:
        self.app = app
        self.sel = 0
        self._clock = 0.0
        self.set_view(app.view)

    def set_view(self, v: View) -> None:
        """(Re)build everything that depends on the resolution."""
        self.view = v
        self.big_sprites = BallSprites(v.scaled(DECOR_SCALE))
        self.waves = Waves(v, MENU)

    def _labels(self) -> list[str]:
        resume = self.app.game_in_progress()
        return [
            t("menu.resume") if resume else t("menu.play"),
            t("menu.help"),
            f"{t('menu.language')}: {t('lang.name')}",
            t("menu.quit"),
        ]

    def _rects(self) -> list[pg.Rect]:
        """Button rectangles in LOGICAL units (mouse events arrive in logical units)."""
        cx = LOGICAL_SIZE[0] // 2
        return [
            pg.Rect(cx - BTN_W // 2, FIRST_Y + i * (BTN_H + BTN_GAP), BTN_W, BTN_H)
            for i in range(len(ITEMS))
        ]

    def shake_offset(self) -> tuple[float, float]:
        return 0.0, 0.0

    def activate(self, i: int) -> None:
        self.app.audio.play_click()
        item = ITEMS[i]
        if item == "play":
            self.app.go_play()
        elif item == "help":
            self.app.go_help()
        elif item == "language":
            i18n.toggle_lang()
        else:
            self.app.running = False

    def handle_event(self, e: pg.event.Event) -> None:
        if e.type == pg.MOUSEMOTION:
            for i, r in enumerate(self._rects()):
                if r.collidepoint(e.pos):
                    self.sel = i
        elif e.type == pg.MOUSEBUTTONDOWN and e.button == 1:
            for i, r in enumerate(self._rects()):
                if r.collidepoint(e.pos):
                    self.sel = i
                    self.activate(i)
        elif e.type == pg.KEYDOWN:
            if e.key in (pg.K_UP, pg.K_w):
                self.sel = (self.sel - 1) % len(ITEMS)
            elif e.key in (pg.K_DOWN, pg.K_s):
                self.sel = (self.sel + 1) % len(ITEMS)
            elif e.key in (pg.K_RETURN, pg.K_KP_ENTER, pg.K_SPACE):
                self.activate(self.sel)

    def update(self, dt: float) -> None:
        self._clock += dt

    def draw(self, canvas: pg.Surface) -> None:
        v = self.view
        canvas.blit(backdrop.night(canvas.get_size()), (0, 0))
        self.waves.draw(canvas, self._clock)
        cx = LOGICAL_SIZE[0] // 2
        half = self.big_sprites.size / 2
        for number, dx, dy in ((0, -330, 0), (8, -420, 38), (11, 330, 0), (3, 420, 38)):
            x, y = v.pt((cx + dx, 150 + dy))
            blit_pm(canvas, self.big_sprites.get(number), (x - half, y - half))
        breath = 0.9 + 0.2 * math.sin(2 * math.pi * self._clock / BREATH_S)
        hud.glow_text(canvas, v, t("app.title"), 76, C.WHITE, C.CYAN, (cx, 150), strength=breath)
        hud.glow_text(canvas, v, t("app.subtitle"), 22, (255, 168, 238), C.MAGENTA, (cx, 214))

        for i, (rect, label) in enumerate(zip(self._rects(), self._labels(), strict=True)):
            hud.button(canvas, v, rect, label, "primary" if i == self.sel else "normal", 26)
        hud.text(canvas, v, t("menu.hint"), 15, C.TEXT_DIM, (cx, LOGICAL_SIZE[1] - 36), center=True)
