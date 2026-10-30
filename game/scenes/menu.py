"""Opening menu: Play / How to play / Settings / Quit, on a synthwave night.

The title is a neon tube that stutters on when the menu opens, then hums. Balls float up out of
the floor one after another, land on the ribbons along the horizon and drift away with them.
The chosen button is lit, a little bigger, and a lit frame glides to it from the one before.
Settings open as a panel over the menu.
"""

from __future__ import annotations

import math

import pygame as pg

from game.config import LOGICAL_SIZE
from game.i18n import t
from game.render import hud
from game.render import palette as C
from game.render.draw import blit_rrect
from game.render.synth import Synthwave
from game.render.view import View
from game.scenes.play_panel import PlayPanel
from game.scenes.settings import SettingsPanel

ITEMS = ("play", "help", "settings", "quit")
BTN_W, BTN_H, BTN_GAP = 300, 46, 12
FIRST_Y = 446
HORIZON = 405  # the sun sets on this line; the buttons stand on the floor below it
TITLE_Y, SUBTITLE_Y = 150, 230
# the title stutters on: (seconds after the menu opens, brightness) until it holds steady
FLICKER = ((0.0, 0.0), (0.08, 0.9), (0.14, 0.1), (0.3, 1.0), (0.36, 0.25), (0.42, 1.0),
           (0.78, 0.55), (0.84, 1.0))  # fmt: skip
BREATH_S = 4.0  # afterwards the halo swells and fades once in this many seconds


def title_level(since_open: float) -> float:
    """How lit the title is `since_open` seconds after the menu opened (0..~1.1)."""
    level = 0.0
    for at, value in FLICKER:
        if since_open >= at:
            level = value
    if since_open >= FLICKER[-1][0]:
        level = 0.95 + 0.12 * math.sin(2 * math.pi * since_open / BREATH_S)
    return level


class MenuScene:
    def __init__(self, app) -> None:
        self.app = app
        self.sel = 0
        self._clock = 0.0
        self._opened = 0.0
        self.fx = hud.ButtonFx()
        self.settings = SettingsPanel(app)
        self.play_panel = PlayPanel(app)  # Play: Solo / Two players, then a room
        self.set_view(app.view)

    def set_view(self, v: View) -> None:
        """(Re)build everything that depends on the resolution."""
        self.view = v
        self.synth = Synthwave(v, HORIZON, floaters=True)

    def enter(self) -> None:
        """The menu is shown again: the title stutters on again."""
        self._opened = self._clock

    def idle_s(self) -> float:
        """How long the menu has been showing (since it opened)."""
        return self._clock - self._opened

    def _labels(self) -> list[str]:
        return [
            t("menu.play"),
            t("menu.help"),
            t("menu.settings"),
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

    def _choose(self, i: int) -> None:
        if i != self.sel:
            self.sel = i
            self.app.audio.play_hover()

    def activate(self, i: int) -> None:
        self.app.audio.play_click()
        self.fx.press(ITEMS[i], self._clock)
        item = ITEMS[i]
        if item == "play":
            self.play_panel.open()
        elif item == "help":
            self.app.open_help()
        elif item == "settings":
            self.settings.open()
        else:
            self.app.running = False

    def handle_event(self, e: pg.event.Event) -> None:
        if self.settings.is_open:
            self.settings.handle_event(e)
            return
        if self.play_panel.is_open:
            self.play_panel.handle_event(e)
            return
        if e.type == pg.MOUSEMOTION:
            for i, r in enumerate(self._rects()):
                if r.collidepoint(e.pos):
                    self._choose(i)
        elif e.type == pg.MOUSEBUTTONDOWN and e.button == 1:
            for i, r in enumerate(self._rects()):
                if r.collidepoint(e.pos):
                    self.sel = i
                    self.activate(i)
        elif e.type == pg.KEYDOWN:
            if e.key in (pg.K_UP, pg.K_w):
                self._choose((self.sel - 1) % len(ITEMS))
            elif e.key in (pg.K_DOWN, pg.K_s):
                self._choose((self.sel + 1) % len(ITEMS))
            elif e.key in (pg.K_RETURN, pg.K_KP_ENTER, pg.K_SPACE):
                self.activate(self.sel)

    def update(self, dt: float) -> None:
        self._clock += dt
        self.synth.update(dt)
        rects = dict(zip(ITEMS, self._rects(), strict=True))
        self.fx.update(dt, ITEMS[self.sel], rects, self._clock)
        self.settings.update(dt)
        self.play_panel.update(dt)

    def draw(self, canvas: pg.Surface) -> None:
        v = self.view
        for panel in (self.settings, self.play_panel):
            if panel.covers_scene(canvas.get_size()):  # the panel holds a picture of the menu
                panel.draw(canvas, v)
                return
        self.synth.draw(canvas, self._clock)
        cx = LOGICAL_SIZE[0] // 2
        level = title_level(self._clock - self._opened)
        face = C.lerp(C.scale(C.MAGENTA, 0.25), C.WHITE, min(1.0, level))
        hud.glow_text(canvas, v, t("app.title"), 116, face, C.MAGENTA, (cx, TITLE_Y),
                      strength=1.5 * level, face="display")  # fmt: skip
        hud.text(canvas, v, t("app.subtitle").upper(), 17, C.CYAN, (cx, SUBTITLE_Y), bold=True,
                 center=True, track=3.0)  # fmt: skip

        for item, rect, label in zip(ITEMS, self._rects(), self._labels(), strict=True):
            hud.live_button(canvas, v, rect, label, self.fx, item, self._clock, frame_glides=True,
                            size=20)  # fmt: skip
        hud.glide_frame(canvas, v, self.fx)
        hint = t("menu.hint")  # on a dark strip: never read text against the grid
        w = hud.text_width(v, hint, 14) + 36
        blit_rrect(canvas, v, cx - w / 2, LOGICAL_SIZE[1] - 36, w, 26, 13, C.BG, 0)
        hud.text(canvas, v, hint, 14, C.TEXT_DIM, (cx, LOGICAL_SIZE[1] - 23), center=True)
        self.settings.draw(canvas, v)
        self.play_panel.draw(canvas, v)
