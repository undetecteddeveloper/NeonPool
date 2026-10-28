"""Opening menu: Play / Language / Quit."""

from __future__ import annotations

import pygame as pg

from game import i18n
from game.config import LOGICAL_SIZE
from game.i18n import t
from game.render import hud
from game.render import palette as C
from game.render.draw import BallSprites, blit_pm, blit_rrect
from game.render.view import View

ITEMS = ("play", "language", "quit")
BTN_W, BTN_H, BTN_GAP = 320, 58, 18
FIRST_Y = 330
DECOR_SCALE = 3  # decorative balls are drawn natively 3x bigger, not stretched


class MenuScene:
    def __init__(self, app) -> None:
        self.app = app
        self.sel = 0
        self.set_view(app.view)

    def set_view(self, v: View) -> None:
        """(Re)build everything that depends on the resolution."""
        self.view = v
        self.big_sprites = BallSprites(v.scaled(DECOR_SCALE))

    def _labels(self) -> list[str]:
        resume = self.app.game_in_progress()
        return [
            t("menu.resume") if resume else t("menu.play"),
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
        pass

    def draw(self, canvas: pg.Surface) -> None:
        v = self.view
        canvas.fill(C.BG)
        cx = LOGICAL_SIZE[0] // 2
        half = self.big_sprites.size / 2
        for number, dx, dy in ((0, -330, 0), (8, -420, 38), (11, 330, 0), (3, 420, 38)):
            x, y = v.pt((cx + dx, 150 + dy))
            blit_pm(canvas, self.big_sprites.get(number), (x - half, y - half))
        hud.text_outlined(canvas, v, t("app.title"), 76, C.WHITE, (cx, 150))
        hud.text(canvas, v, t("app.subtitle"), 22, C.ACCENT, (cx, 214), bold=True, center=True)

        for i, (rect, label) in enumerate(zip(self._rects(), self._labels(), strict=True)):
            active = i == self.sel
            blit_rrect(
                canvas, v, rect.x, rect.y, rect.w, rect.h, 14, C.ACCENT if active else C.PANEL
            )
            hud.text(
                canvas,
                v,
                label,
                26,
                C.OUTLINE if active else C.TEXT,
                rect.center,
                bold=True,
                center=True,
            )
        hud.text(canvas, v, t("menu.hint"), 15, C.TEXT_DIM, (cx, LOGICAL_SIZE[1] - 36), center=True)
