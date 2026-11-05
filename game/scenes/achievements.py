"""The achievements panel: the whole list on a lit panel that slides up over the menu.

Two columns of rows, each a cup, a name and how it is earned. One that is earned is lit in the
colour of its group (Free play pink, Practice cyan, two players amber); one that is not is dim
and says how to earn it; a secret one that is not yet earned shows "???". Esc, the Done button or
a click outside closes it. It only shows: nothing here changes the player's progress.
"""

from __future__ import annotations

import pygame as pg

from game.achievements import CATALOGUE
from game.i18n import t
from game.render import hud
from game.render import palette as C
from game.render.achieve import group_colour, trophy
from game.render.floating import FloatPanel

PANEL = pg.Rect(160, 56, 960, 608)
COL_X = (192, 664)  # where each column starts (logical x)
COL_W = 432
ROW_H, FIRST_ROW_CY = 38, 176  # a row's height, and the middle of the first one
PER_COL = 10
ICON = 28
DONE = pg.Rect(PANEL.centerx - 80, 574, 160, 44)
NAME_SIZE, DESC_SIZE = 15, 12
TEXT_DX = 46  # the words start this far in from the column's left edge


def row_cy(i: int) -> float:
    return FIRST_ROW_CY + (i % PER_COL) * ROW_H


def row_x(i: int) -> int:
    return COL_X[i // PER_COL]


class AchievementsPanel(FloatPanel):
    RECT = PANEL

    def __init__(self, app) -> None:
        super().__init__()
        self.app = app
        self._clock = 0.0
        self.fx = hud.ButtonFx()

    def title(self) -> str:
        return t("ach.title")

    def open(self) -> None:
        self._open()
        self.app.audio.play_click()

    def close(self) -> None:
        self._close()
        self.app.audio.play_click()

    def handle_event(self, e: pg.event.Event) -> None:
        if e.type == pg.KEYDOWN and e.key in (pg.K_ESCAPE, pg.K_RETURN, pg.K_KP_ENTER, pg.K_SPACE):
            self.fx.press("done", self._clock)
            self.close()
        elif e.type == pg.MOUSEBUTTONDOWN and e.button == 1:
            if DONE.collidepoint(e.pos):
                self.fx.press("done", self._clock)
                self.close()
            elif not PANEL.collidepoint(e.pos):
                self.close()  # a click outside the panel closes it

    def update(self, dt: float) -> None:
        self._clock += dt
        self._animate(dt)
        self.fx.update(dt, "done", {"done": DONE}, self._clock)

    # --- drawing ---
    def _paint_live(self, canvas: pg.Surface, pv) -> None:
        have = set(self.app.settings.achievements)
        hud.text(canvas, pv, t("ach.count", n=len(have), total=len(CATALOGUE)), 14, C.TEXT_DIM,
                 (PANEL.centerx, 130), center=True)  # fmt: skip
        for i, a in enumerate(CATALOGUE):
            self._row(canvas, pv, i, a, a.id in have)
        hud.live_button(canvas, pv, DONE, t("settings.done"), self.fx, "done", self._clock)
        hud.text(canvas, pv, t("ach.hint"), 13, C.TEXT_DIM, (PANEL.centerx, DONE.bottom + 16),
                 center=True)  # fmt: skip

    @staticmethod
    def _row(canvas: pg.Surface, pv, i: int, a, earned: bool) -> None:
        x, cy = row_x(i), row_cy(i)
        hidden = a.secret and not earned
        colour = group_colour(a.group)
        if earned:
            trophy(canvas, pv, (x + ICON / 2, cy), ICON, colour, True, 0.7)
        elif hidden:
            hud.text(canvas, pv, "?", 20, C.PANEL_EDGE, (x + ICON / 2, cy), bold=True, center=True)
        else:
            trophy(canvas, pv, (x + ICON / 2, cy), ICON, C.PANEL_EDGE, False, 0.0)
        name = t("ach.secret") if hidden else t(f"ach.{a.id}")
        desc = t("ach.secret.d") if hidden else t(f"ach.{a.id}.d")
        hud.text(canvas, pv, name, NAME_SIZE, C.WHITE if earned else C.TEXT_DIM,
                 (x + TEXT_DX, cy - 14), bold=True)  # fmt: skip
        hud.text(canvas, pv, desc, DESC_SIZE, C.TEXT if earned else C.TEXT_DIM,
                 (x + TEXT_DX, cy + 4))  # fmt: skip
