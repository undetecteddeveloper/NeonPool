"""The first screen of the game: a dark screen with one small line in the middle, "Getting ready",
on the same arcade monitor as the opening screen (render/tube.py: bowed glass, dark corners, a
faint band crawling down).

What the game makes before the first picture is done in small pieces with this screen redrawn
between them, so the band keeps moving instead of the screen freezing on one frame. It runs on
the clock of the computer, not on the game's time.
"""

from __future__ import annotations

import time

import pygame as pg

from game.config import LOGICAL_SIZE
from game.i18n import t
from game.render import crt, hud
from game.render import palette as C
from game.render.tube import Monitor
from game.render.view import View

SCAN_DARK = 0.80  # the same worn scan lines as the opening screen


class LoadingScene:
    def __init__(self, screen: pg.Surface) -> None:
        self.view = View.for_window(screen.get_size())
        self.monitor = Monitor(self.view)
        self._t0 = time.perf_counter()

    def draw(self, screen: pg.Surface) -> None:
        now = time.perf_counter() - self._t0
        pic = self.monitor.begin()
        cx, cy = LOGICAL_SIZE[0] / 2, LOGICAL_SIZE[1] / 2
        hud.label(pic, self.view, t("app.loading"), (cx, cy), C.TEXT_DIM, 14, center=True)
        self.monitor.present(screen, now)
        crt.scanlines(screen, self.view.s, SCAN_DARK)

    def show(self, screen: pg.Surface) -> bool:
        """Answer the window (so the system sees it alive), draw and show one frame. False if
        the player closed the window."""
        for e in pg.event.get():
            if e.type == pg.QUIT:
                return False
        self.draw(screen)
        pg.display.flip()
        return True
