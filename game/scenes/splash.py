"""The opening screen: the title lights up letter by letter like a neon sign, then the tools the
game was made with are typed out like a machine starting up, then the tube folds into a line and
the menu opens out of it (that fold is the app's usual change of scene). Any key or click skips.

It is an arcade monitor: the picture is bowed out like its glass (render/tube.py), the corners are
dark and rounded, a faint bright band crawls down it, the colours of the title are fringed apart,
and now and then the picture slips sideways for a moment. Everything that appears has a chip-tune
sound of its own (the schedule below is built from the same times the drawing uses). When it ends
the menu is drawn by a beam of light (scenes/menu.py).
"""

from __future__ import annotations

import pygame as pg

from game.config import LOGICAL_SIZE
from game.i18n import t
from game.render import hud
from game.render import palette as C
from game.render.tube import Fringe, Monitor
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
READY_AT = TOOLS_AT + TOOL_STEP * len(TOOLS) + 0.1
OFF_AT = SPLASH_S - 0.2  # the sound of the tube switching off starts here
LOG_X, LOG_W, LOG_Y, LOG_STEP, LOG_PT = CX - 250, 500, 360, 42, 22
FRINGE_PX = 2  # the red and the blue of the title are this far apart (logical px)
FRINGE_BOX = (CX - 340, 100, 680, 200)  # where the title and its halo are


def log_text(key: str) -> str:
    return f"> {t(key).lower()}"


def sound_schedule() -> list[tuple[float, str, int]]:
    """Every sound of the screen: (when, kind, which), in the order of time. `kind` is what
    Audio.play_splash takes. The times are the ones the drawing shows things at."""
    events: list[tuple[float, str, int]] = [(0.0, "on", 0)]
    events += [(LETTER_AT + LETTER_STEP * i, "letter", i) for i in range(len(t("app.title")))]
    events.append((SUBTITLE_AT, "sub", 0))
    for i, key in enumerate(TOOLS):
        start, n = TOOLS_AT + TOOL_STEP * i, len(log_text(key))
        events.append((start, "line", i))
        events += [(start + c / TYPE_CPS, "tick", 0) for c in range(1, n)]
        events.append((start + n / TYPE_CPS + OK_AFTER_S, "ok", 0))
    events += [(READY_AT, "ready", 0), (OFF_AT, "off", 0)]
    return sorted(events, key=lambda e: e[0])


class SplashScene:
    SCAN_DARK = 0.80  # darker scan lines than the rest of the game: this is a worn tube

    def __init__(self, app) -> None:
        self.app = app
        self.t = 0.0
        self._done = False
        self._events: list[tuple[float, str, int]] = []
        self._next = 0  # which sound is next
        self.set_view(app.view)

    def set_view(self, v: View) -> None:
        """(Re)build the pictures that depend on the resolution."""
        self.view = v
        self.monitor = Monitor(v)  # the glass, the dark corners, the band, the slip
        self._fringe_box = v.rect(*FRINGE_BOX).clip(pg.Rect(0, 0, *v.canvas))
        self._fringe = Fringe(self._fringe_box.size)

    def restart(self) -> None:
        self.t, self._done, self._next = 0.0, False, 0
        self._events = sound_schedule()

    def shake_offset(self) -> tuple[float, float]:
        return 0.0, 0.0

    def finish(self) -> None:
        """On to the menu, which draws itself in with a beam of light."""
        if not self._done:
            self._done = True
            self.app.go_menu()
            self.app.menu.start_intro()

    def handle_event(self, e: pg.event.Event) -> None:
        if e.type in (pg.KEYDOWN, pg.MOUSEBUTTONDOWN):
            self.finish()

    def update(self, dt: float) -> None:
        self.t += dt
        while self._next < len(self._events) and self._events[self._next][0] <= self.t:
            _, kind, which = self._events[self._next]
            self._next += 1
            self.app.audio.play_splash(kind, which)
        if self.t >= SPLASH_S:
            self.finish()

    # --- drawing -----------------------------------------------------------------------------
    def draw(self, canvas: pg.Surface) -> None:
        v, pic = self.view, self.monitor.begin()
        self._title(pic, v)
        k = min(1.0, max(0.0, (self.t - SUBTITLE_AT) / SUBTITLE_S))
        if k > 0:
            hud.text(pic, v, t("app.subtitle").upper(), 17, C.scale(C.CYAN, k),
                     (CX, SUBTITLE_Y), bold=True, center=True, track=3.0)  # fmt: skip
        self._fringe.apply(pic, self._fringe_box, max(1, v.i(FRINGE_PX)))
        self._log(pic, v)
        self.monitor.present(canvas, self.t)  # bowed out like the glass of the monitor

    def prewarm(self, canvas: pg.Surface) -> None:
        """Draw the screen at a few moments onto `canvas` so that every sprite it needs (the
        halos of a letter lighting up, the typed lines, the bowed rows) is made before it is
        shown. Leaves the time as it was."""
        was = self.t
        try:
            for at in (0.0, LETTER_AT + 0.02, LETTER_AT + 0.07, LETTER_AT + 0.2, SUBTITLE_AT + 0.5,
                       TOOLS_AT + 0.5, READY_AT + 0.2):  # fmt: skip
                self.t = at
                self.draw(canvas)
        finally:
            self.t = was

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

    def _log(self, canvas: pg.Surface, v: View) -> None:
        """The tools, typed one line at a time with a block cursor; at the end, "ready"."""
        blink = int(self.t * 2) % 2 == 0
        for i, key in enumerate(TOOLS):
            start = TOOLS_AT + TOOL_STEP * i
            text = log_text(key)
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
        if self.t > READY_AT:
            y, text = LOG_Y + LOG_STEP * len(TOOLS), f"> {t('splash.ready')}"
            hud.text(canvas, v, text, LOG_PT, C.MAGENTA, (LOG_X, y), bold=True)
            if blink:
                self._cursor(canvas, v, text, y, C.MAGENTA)

    @staticmethod
    def _cursor(canvas: pg.Surface, v: View, typed: str, y: float, colour) -> None:
        x = LOG_X + hud.text_width(v, typed, LOG_PT, bold=True) + 3
        canvas.fill(colour, v.rect(x, y - 2, 12, 24), special_flags=pg.BLEND_RGB_ADD)
