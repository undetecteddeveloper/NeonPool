"""Opening menu: Play / Language / Quit."""

from __future__ import annotations

import pygame as pg

from game import i18n
from game.config import LOGICAL_SIZE
from game.i18n import t
from game.render import hud
from game.render import palette as C
from game.render.draw import BallSprites

ITEMS = ("play", "language", "quit")
BTN_W, BTN_H, BTN_GAP = 320, 58, 18
FIRST_Y = 330


class MenuScene:
    def __init__(self, app) -> None:
        self.app = app
        self.sel = 0
        self.sprites = BallSprites()

    def _labels(self) -> list[str]:
        resume = self.app.game_in_progress()
        return [
            t("menu.resume") if resume else t("menu.play"),
            f"{t('menu.language')}: {t('lang.name')}",
            t("menu.quit"),
        ]

    def _rects(self) -> list[pg.Rect]:
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
        canvas.fill(C.BG)
        cx = LOGICAL_SIZE[0] // 2
        # decorative balls flanking the title (the real sprites, enlarged)
        for number, dx, dy in ((0, -330, 0), (8, -420, 38), (11, 330, 0), (3, 420, 38)):
            big = pg.transform.smoothscale(
                self.sprites.get(number), (self.sprites.size * 3, self.sprites.size * 3)
            )
            canvas.blit(big, big.get_rect(center=(cx + dx, 150 + dy)))
        hud.text_outlined(canvas, t("app.title"), 76, C.WHITE, (cx, 150))
        hud.text(canvas, t("app.subtitle"), 22, C.ACCENT, (cx, 214), bold=True, center=True)

        for i, (rect, label) in enumerate(zip(self._rects(), self._labels(), strict=True)):
            active = i == self.sel
            pg.draw.rect(canvas, C.OUTLINE, rect.inflate(10, 10), border_radius=18)
            pg.draw.rect(canvas, C.ACCENT if active else C.PANEL, rect, border_radius=14)
            hud.text(
                canvas,
                label,
                26,
                C.OUTLINE if active else C.TEXT,
                rect.center,
                bold=True,
                center=True,
            )
        hud.text(canvas, t("menu.hint"), 15, C.TEXT_DIM, (cx, LOGICAL_SIZE[1] - 36), center=True)
