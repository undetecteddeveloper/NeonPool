"""App: owns the canvas (at the REAL window resolution), routes events to the scene."""

from __future__ import annotations

import ctypes
import logging
import sys
import time

import pygame as pg

from game.audio import Audio
from game.config import LOGICAL_SIZE
from game.render import palette as C
from game.render.view import View
from game.render.viewport import window_to_logical
from game.rules.eight_ball import PLAYING
from game.scenes.menu import MenuScene
from game.scenes.play import PlayScene

log = logging.getLogger("mathofpool")
_MOUSE_EVENTS = (pg.MOUSEBUTTONDOWN, pg.MOUSEBUTTONUP, pg.MOUSEMOTION)
RESIZE_SETTLE_S = 0.2  # rebuild the sharp assets once the window stops changing size
MAX_START_SCALE = 1.5
WINDOW_MARGIN = (40, 130)  # room for the title bar, borders and taskbar


class App:
    def __init__(self, screen: pg.Surface) -> None:
        self.screen = screen
        self.view = View.for_window(screen.get_size())
        self.canvas = pg.Surface(self.view.size)
        self.audio = Audio()
        self.play = PlayScene(self)  # kept alive so Esc -> menu -> Resume continues the game
        self.menu = MenuScene(self)
        self.scene = self.menu
        self.running = True
        self._window = screen.get_size()
        self._window_changed_at = float("-inf")

    def go_play(self) -> None:
        self.scene = self.play

    def go_menu(self) -> None:
        self.play.drag.cancel()
        self.scene = self.menu

    def game_in_progress(self) -> bool:
        return self.play.rules.shots > 0 and self.play.rules.phase == PLAYING

    # --- contract used by tools/smoke.py and tools/shot.py ---------------------------------
    def handle_event(self, e: pg.event.Event) -> None:
        if e.type == pg.QUIT:
            self.running = False
            return
        if e.type == pg.KEYDOWN:
            if e.key == pg.K_F11:
                _toggle_fullscreen()
                return
            if e.key == pg.K_m:
                self.audio.toggle_mute()
                return
        if e.type in _MOUSE_EVENTS:
            pos = window_to_logical(e.pos, self._window_size(), LOGICAL_SIZE)
            e = pg.event.Event(e.type, {**e.dict, "pos": pos})
        self.scene.handle_event(e)

    def update(self, dt: float) -> None:
        self.scene.update(dt)

    def sync_view(self, force: bool = False) -> None:
        """Rebuild sharp assets for the current window size (after it stopped changing)."""
        window = self._window_size()
        now = time.monotonic()
        if window != self._window:
            self._window, self._window_changed_at = window, now
        target = View.for_window(window)
        if not target.same_as(self.view) and (
            force or now - self._window_changed_at >= RESIZE_SETTLE_S
        ):
            self.view = target
            self.canvas = pg.Surface(target.size)
            self.play.set_view(target)
            self.menu.set_view(target)

    def draw(self) -> None:
        screen = pg.display.get_surface() or self.screen
        self.sync_view()
        self.scene.draw(self.canvas)
        target = View.for_window(screen.get_size())
        # While the window is still being resized the assets are for the old size:
        # stretch for a moment (soft but never wrong), then sync_view() makes it sharp again.
        frame = self.canvas
        if not target.same_as(self.view):
            frame = pg.transform.smoothscale(self.canvas, target.size)
        shake_x, shake_y = self.scene.shake_offset()
        fw, fh = frame.get_size()
        sw, sh = screen.get_size()
        screen.fill(C.OUTLINE)
        screen.blit(
            frame,
            (
                (sw - fw) // 2 + round(shake_x * target.s),
                (sh - fh) // 2 + round(shake_y * target.s),
            ),
        )

    def _window_size(self) -> tuple[int, int]:
        return (pg.display.get_surface() or self.screen).get_size()

    # --- real window ---------------------------------------------------------------------------
    @staticmethod
    def run_forever() -> None:
        logging.basicConfig(level=logging.INFO)
        _enable_dpi_awareness()
        pg.init()
        pg.display.set_caption("MathofPool")
        screen = pg.display.set_mode(_start_size(), pg.RESIZABLE)
        app = App(screen)
        clock = pg.time.Clock()
        while app.running:
            dt = clock.tick(60) / 1000
            for e in pg.event.get():
                app.handle_event(e)
            app.update(dt)
            app.draw()
            pg.display.flip()
        pg.quit()


def _enable_dpi_awareness() -> None:
    """Without this Windows stretches the window on laptops with display scaling (blurry)."""
    if sys.platform != "win32":
        return
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except (AttributeError, OSError):
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except (AttributeError, OSError) as exc:
            log.warning("could not set DPI awareness: %s", exc)


def _start_size() -> tuple[int, int]:
    """Biggest 16:9 window that fits the screen (a 1280x720 laptop cannot show 1280x720)."""
    lw, lh = LOGICAL_SIZE
    try:
        dw, dh = pg.display.get_desktop_sizes()[0]
    except (pg.error, IndexError):
        return lw, lh
    scale = min((dw - WINDOW_MARGIN[0]) / lw, (dh - WINDOW_MARGIN[1]) / lh, MAX_START_SCALE)
    scale = max(0.5, scale)
    return round(lw * scale), round(lh * scale)


def _toggle_fullscreen() -> None:
    try:
        pg.display.toggle_fullscreen()
    except pg.error as exc:  # not every driver supports it
        log.warning("fullscreen toggle failed: %s", exc)
