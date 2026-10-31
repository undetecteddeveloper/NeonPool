"""The opening screen: the title lights up letter by letter like a neon sign, then the tools the
game was made with are typed out like a machine starting up, then the tube folds into a line and
the menu opens out of it (that fold is the app's usual change of scene). Any key or click skips.

It is a tube picture: dark corners and a faint bright band crawling down (both made once), the
colours of the title fringed apart, and now and then the picture tears sideways for a moment.
"""

from __future__ import annotations

import math

import numpy as np
import pygame as pg

from game.config import LOGICAL_SIZE
from game.i18n import t
from game.render import crt, hud
from game.render import palette as C
from game.render.view import View

SPLASH_S = 6.2  # the whole of it, then the menu
CX = LOGICAL_SIZE[0] // 2
TITLE_Y, SUBTITLE_Y, TITLE_PT = 190, 262, 116
LETTER_AT, LETTER_STEP = 0.6, 0.14  # the first letter lights here; each next one this much later
SUBTITLE_AT, SUBTITLE_S = 1.9, 0.4
TOOLS = ("tool.python", "tool.pygame", "tool.numpy", "tool.claude")
TOOLS_AT, TOOL_STEP = 2.4, 0.7  # the first line starts to be typed here; each next this later
TYPE_CPS = 40.0  # characters typed a second
OK_AFTER_S = 0.25  # a typed line gets its OK this long after its last character
LOG_X, LOG_W, LOG_Y, LOG_STEP, LOG_PT = CX - 250, 500, 360, 42, 22
FRINGE_PX = 2  # the red and the blue of the title are this far apart (logical px)
FRINGE_BOX = (CX - 340, 100, 680, 200)  # where the title and its halo are
TEAR_EVERY_S, TEAR_S, TEAR_PX = 1.25, 0.06, 10  # now and then the picture slips sideways
BAR_PX, BAR_PEAK, BAR_SPEED = 150, 16, 0.28  # the faint band: height, brightness, screens/s


class SplashScene:
    SCAN_DARK = 0.80  # darker scan lines than the rest of the game: this is a worn tube

    def __init__(self, app) -> None:
        self.app = app
        self.t = 0.0
        self._done = False
        self.set_view(app.view)

    def set_view(self, v: View) -> None:
        """(Re)build the pictures that depend on the resolution: the dark ground and the band."""
        self.view = v
        self.bg = pg.Surface(v.canvas)
        self.bg.fill(C.BG)
        crt.darken_corners(self.bg)
        w, _ = v.canvas
        rows = (np.sin(np.linspace(0, math.pi, v.i(BAR_PX))) ** 2 * BAR_PEAK).astype(np.uint8)
        self.bar = pg.surfarray.make_surface(np.repeat(np.tile(rows, (w, 1))[:, :, None], 3, 2))
        self._fringe_box = v.rect(*FRINGE_BOX).clip(self.bg.get_rect())
        size = self._fringe_box.size  # three pictures the size of the title, reused every frame
        self._fringe_bufs = tuple(pg.Surface(size) for _ in range(3))

    def restart(self) -> None:
        self.t, self._done = 0.0, False

    def shake_offset(self) -> tuple[float, float]:
        return 0.0, 0.0

    def finish(self) -> None:
        if not self._done:
            self._done = True
            self.app.go_menu()

    def handle_event(self, e: pg.event.Event) -> None:
        if e.type in (pg.KEYDOWN, pg.MOUSEBUTTONDOWN):
            self.finish()

    def update(self, dt: float) -> None:
        self.t += dt
        if self.t >= SPLASH_S:
            self.finish()

    # --- drawing -----------------------------------------------------------------------------
    def draw(self, canvas: pg.Surface) -> None:
        v = self.view
        canvas.blit(self.bg, (0, 0))
        self._title(canvas, v)
        k = min(1.0, max(0.0, (self.t - SUBTITLE_AT) / SUBTITLE_S))
        if k > 0:
            hud.text(canvas, v, t("app.subtitle").upper(), 17, C.scale(C.CYAN, k),
                     (CX, SUBTITLE_Y), bold=True, center=True, track=3.0)  # fmt: skip
        self._fringe(canvas, v)
        self._log(canvas, v)
        self._tear(canvas, v)
        y = int(((self.t * BAR_SPEED) % 1.3 - 0.15) * canvas.get_height())
        canvas.blit(self.bar, (0, y), special_flags=pg.BLEND_RGB_ADD)

    def _title(self, canvas: pg.Surface, v: View) -> None:
        title = t("app.title")
        dim = C.scale(C.MAGENTA, 0.25)
        hud.glow_text(canvas, v, title, TITLE_PT, dim, C.MAGENTA, (CX, TITLE_Y), strength=0.0,
                      face="display")  # fmt: skip
        total = hud.text_width(v, title, TITLE_PT, face="display")
        left = CX - total / 2
        for i in range(len(title)):  # letter i lights up at LETTER_AT + i * LETTER_STEP, stuttering
            age = self.t - (LETTER_AT + LETTER_STEP * i)
            if age < 0:
                continue
            lit = 0.4 if age < 0.05 else 0.1 if age < 0.1 else 1.0
            x0 = hud.text_width(v, title[:i], TITLE_PT, face="display")
            x1 = hud.text_width(v, title[: i + 1], TITLE_PT, face="display")
            canvas.set_clip(v.rect(left + x0, 100, x1 - x0, 200))
            hud.glow_text(canvas, v, title, TITLE_PT, C.WHITE, C.MAGENTA, (CX, TITLE_Y),
                          strength=1.5 * lit, face="display")  # fmt: skip
        canvas.set_clip(None)

    def _fringe(self, canvas: pg.Surface, v: View) -> None:
        """The red of the title slips one way and the blue the other, as on a tired tube."""
        box = self._fringe_box
        if box.w <= 0 or box.h <= 0:
            return
        src, channel, out = self._fringe_bufs
        src.blit(canvas, (0, 0), area=box)
        out.fill((0, 0, 0))
        d = max(1, v.i(FRINGE_PX))
        for mask, dx in (((255, 0, 0), d), ((0, 255, 0), 0), ((0, 0, 255), -d)):
            channel.blit(src, (0, 0))
            channel.fill(mask, special_flags=pg.BLEND_RGB_MULT)  # only this colour of the picture
            out.blit(channel, (dx, 0), special_flags=pg.BLEND_RGB_ADD)
        canvas.blit(out, box.topleft)

    def _log(self, canvas: pg.Surface, v: View) -> None:
        """The tools, typed one line at a time with a block cursor; at the end, "ready"."""
        blink = int(self.t * 2) % 2 == 0
        for i, key in enumerate(TOOLS):
            start = TOOLS_AT + TOOL_STEP * i
            text = f"> {t(key).lower()}"
            typed = min(len(text), int((self.t - start) * TYPE_CPS))
            if typed <= 0:
                continue
            y = LOG_Y + LOG_STEP * i
            hud.text(canvas, v, text[:typed], LOG_PT, C.CYAN, (LOG_X, y), bold=True)
            if typed == len(text) and self.t > start + len(text) / TYPE_CPS + OK_AFTER_S:
                hud.text(canvas, v, t("splash.ok"), LOG_PT, C.OK, (LOG_X + LOG_W, y), bold=True,
                         align="right")  # fmt: skip
            elif typed < len(text) or blink:
                self._cursor(canvas, v, text[:typed], y, C.CYAN)
        ready_at = TOOLS_AT + TOOL_STEP * len(TOOLS) + 0.1
        if self.t > ready_at:
            y, text = LOG_Y + LOG_STEP * len(TOOLS), f"> {t('splash.ready')}"
            hud.text(canvas, v, text, LOG_PT, C.MAGENTA, (LOG_X, y), bold=True)
            if blink:
                self._cursor(canvas, v, text, y, C.MAGENTA)

    @staticmethod
    def _cursor(canvas: pg.Surface, v: View, typed: str, y: float, colour) -> None:
        x = LOG_X + hud.text_width(v, typed, LOG_PT, bold=True) + 3
        canvas.fill(colour, v.rect(x, y - 2, 12, 24), special_flags=pg.BLEND_RGB_ADD)

    def _tear(self, canvas: pg.Surface, v: View) -> None:
        """For a few frames now and then a band of the picture slips sideways."""
        if self.t < 2.0 or (self.t / TEAR_EVERY_S) % 1.0 >= TEAR_S / TEAR_EVERY_S:
            return
        w, h = canvas.get_size()
        y, bh = int((self.t * 7.3 % 1.0) * h * 0.8), v.i(26)
        band = canvas.subsurface((0, y, w, min(bh, h - y))).copy()
        canvas.blit(band, (v.i(TEAR_PX * math.sin(self.t * 90)), y))
