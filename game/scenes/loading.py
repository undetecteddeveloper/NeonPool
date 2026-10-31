"""The first screen of the game: what it is getting ready, as a boot log on the same arcade
monitor as the opening screen (render/tube.py: bowed glass, dark corners, a faint band).

The title sits unlit above; each thing the game makes before the first picture (the pictures of
the how-to-play card, the panels, the music, ...) gets a line when it starts and an OK when it is
done. The work is done in small pieces with this screen redrawn between them, so it keeps moving
instead of freezing on one frame. It runs on the clock of the computer, not on the game's time.
"""

from __future__ import annotations

import time

import pygame as pg

from game.i18n import t
from game.render import crt, hud
from game.render import palette as C
from game.render.tube import Monitor
from game.render.view import View
from game.scenes.splash import CX, LOG_PT, LOG_W, LOG_X, TITLE_PT, TITLE_Y

SCAN_DARK = 0.80  # the same worn scan lines as the opening screen
LOG_Y, LOG_STEP = 300, 38
READY_KEY = "splash.ready"  # the last line: no OK, it hands over to the opening screen


class LoadingScene:
    def __init__(self, screen: pg.Surface) -> None:
        self.view = View.for_window(screen.get_size())
        self.monitor = Monitor(self.view)
        self.lines: list[list] = []  # [i18n key, done]
        self._t0 = time.perf_counter()

    def begin(self, key: str) -> None:
        """A thing starts to be made: it gets its line."""
        if not any(line[0] == key for line in self.lines):
            self.lines.append([key, False])

    def done(self, key: str) -> None:
        for line in self.lines:
            if line[0] == key:
                line[1] = True

    def draw(self, screen: pg.Surface) -> None:
        v, now = self.view, time.perf_counter() - self._t0
        pic = self.monitor.begin()
        hud.glow_text(pic, v, t("app.title"), TITLE_PT, C.scale(C.MAGENTA, 0.25), C.MAGENTA,
                      (CX, TITLE_Y), strength=0.0, face="display")  # fmt: skip
        blink = int(now * 2) % 2 == 0
        for i, (key, done) in enumerate(self.lines):
            y, text = LOG_Y + LOG_STEP * i, f"> {t(key).lower()}"
            ready = key == READY_KEY
            hud.text(pic, v, text, LOG_PT, C.MAGENTA if ready else C.CYAN, (LOG_X, y), bold=True)
            if done and not ready:
                hud.text(pic, v, t("splash.ok"), LOG_PT, C.OK, (LOG_X + LOG_W, y), bold=True,
                         align="right")  # fmt: skip
            elif blink:
                x = LOG_X + hud.text_width(v, text, LOG_PT, bold=True) + 3
                pic.fill(C.MAGENTA if ready else C.CYAN, v.rect(x, y - 2, 12, 24),
                         special_flags=pg.BLEND_RGB_ADD)  # fmt: skip
        self.monitor.present(screen, now)
        crt.scanlines(screen, v.s, SCAN_DARK)

    def show(self, screen: pg.Surface) -> bool:
        """Answer the window (so the system sees it alive), draw and show one frame. False if
        the player closed the window."""
        for e in pg.event.get():
            if e.type == pg.QUIT:
                return False
        self.draw(screen)
        pg.display.flip()
        return True
