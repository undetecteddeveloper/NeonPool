"""App: owns the canvas (the WHOLE window, at its real resolution), routes events to the scene.

The game opens full screen; F11 switches between full screen and a window. The 1280x720 frame
sits in the middle at the right shape and every scene paints its background to all four edges.
Changing scene looks like an old tube switching off and on: the old picture folds into a bright
line, the new one opens out of it. The player's settings are loaded at start and saved on change.
"""

from __future__ import annotations

import ctypes
import logging
import sys
import time

import pygame as pg

from game import i18n, settings
from game.audio import Audio
from game.config import LOGICAL_SIZE
from game.i18n import t
from game.render import crt, hud
from game.render import palette as C
from game.render.view import View
from game.render.viewport import window_to_logical
from game.rules.eight_ball import PLAYING
from game.scenes.help import HelpPanel
from game.scenes.menu import MenuScene
from game.scenes.play import PlayScene

log = logging.getLogger("neonpool")
_MOUSE_EVENTS = (pg.MOUSEBUTTONDOWN, pg.MOUSEBUTTONUP, pg.MOUSEMOTION)
RESIZE_SETTLE_S = 0.2  # rebuild the sharp assets once the window stops changing size
MAX_START_SCALE = 1.5
WINDOW_MARGIN = (40, 130)  # room for the title bar, borders and taskbar
TUBE_OFF_S = 0.14  # changing scene: the old picture folds into a line ...
TUBE_ON_S = 0.2  # ... and the new one opens out of it
PREFETCH_AFTER_S = 1.5  # the menu has been up this long: time to make the how-to-play pictures
FPS_SMOOTH = 0.1  # the FPS counter follows the frame time this quickly (0..1 per frame)


class App:
    def __init__(self, screen: pg.Surface) -> None:
        self.screen = screen
        self.settings = settings.load()
        i18n.set_lang(self.settings.lang)
        self.view = View.for_window(screen.get_size())
        self.canvas = pg.Surface(self.view.canvas)
        self.audio = Audio()
        self.audio.volume = self.settings.volume
        self.audio.music_volume = self.settings.music
        self.play = PlayScene(self)  # kept alive so Esc -> menu -> Resume continues the game
        self.menu = MenuScene(self)
        self.help = HelpPanel(self)  # a card over the menu or the table, not a scene
        self.scene = self.menu
        self.running = True
        self.fps = 60.0
        self._window = screen.get_size()
        self._window_changed_at = float("-inf")
        self._old_frame: pg.Surface | None = None  # the picture that is switching off
        self._tube = TUBE_OFF_S  # time into the switch; past TUBE_OFF_S + TUBE_ON_S: done

    # --- scenes ----------------------------------------------------------------------------
    def _switch(self, scene) -> None:
        if scene is self.scene:
            return
        screen = pg.display.get_surface() or self.screen
        self._old_frame = screen.copy()
        self._tube = 0.0
        self.scene = scene

    def skip_transition(self) -> None:
        """Show the current scene at once (tools that photograph a scene use this)."""
        self._tube = TUBE_OFF_S + TUBE_ON_S
        self._old_frame = None

    def go_play(self) -> None:
        self._switch(self.play)

    def open_help(self) -> None:
        """Open the how-to-play card over the current scene (menu or table); Esc closes it."""
        self.play.drag.cancel()
        self.play.placing = False
        self.help.open()

    def go_menu(self) -> None:
        self.play.drag.cancel()
        if self.scene is not self.menu:
            self.menu.enter()
        self._switch(self.menu)

    def game_in_progress(self) -> bool:
        return self.play.rules.shots > 0 and self.play.rules.phase == PLAYING

    # --- settings ----------------------------------------------------------------------------
    def change_settings(self, **changes) -> None:
        """Change some settings, apply them now and save them for the next time."""
        for name, value in changes.items():
            setattr(self.settings, name, value)
        i18n.set_lang(self.settings.lang)
        self.audio.volume = self.settings.volume
        self.audio.music_volume = self.settings.music
        settings.save(self.settings)

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
        if self.help.is_open:  # the card takes every key and click while it is there
            self.help.handle_event(e)
            return
        self.scene.handle_event(e)

    def update(self, dt: float) -> None:
        if dt > 0:
            self.fps += (1.0 / dt - self.fps) * FPS_SMOOTH
        self._tube = min(TUBE_OFF_S + TUBE_ON_S, self._tube + dt)
        self.help.update(dt)
        if (  # the menu has settled (the title is lit): make the first picture before it is needed
            self.help.prefetch
            and self.scene is self.menu
            and not self.help.is_open
            and self.menu.idle_s() > PREFETCH_AFTER_S
            and not self.help.prefetch_one()  # the pictures are done: now the panels
        ):
            self.menu.settings.prewarm(self.view)
            hud.prewarm_result(self.view)
        self.audio.update_music(
            dt,
            "menu" if self.scene is self.menu else "play",
            duck=self.scene is self.play and self.play.rules.phase != PLAYING,
        )
        if not (self.help.is_open and self.scene is self.play):  # the game waits behind the card
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
            self.canvas = pg.Surface(target.canvas)
            self._old_frame = None
            self.play.set_view(target)
            self.menu.set_view(target)
            self.help.set_view(target)

    def draw(self) -> None:
        screen = pg.display.get_surface() or self.screen
        self.sync_view()
        target = View.for_window(screen.get_size())
        shake_x, shake_y = (0.0, 0.0) if self.help.is_open else self.scene.shake_offset()
        switching = self._tube < TUBE_OFF_S + TUBE_ON_S
        same_size = self.canvas.get_size() == screen.get_size()
        if not (shake_x or shake_y or switching) and same_size:
            if not self.help.covers_scene(screen.get_size()):
                self.scene.draw(screen)  # the usual case: straight onto the screen, no copy
            self.help.draw(screen)
        else:
            # shaking, switching scene, or the window is being resized and the assets are for
            # the old size: draw on the canvas, then shift / fold / stretch it for a moment
            folding_old = switching and self._tube < TUBE_OFF_S and self._old_frame is not None
            if not folding_old:  # while the old picture folds away the new one is not seen yet
                if not self.help.covers_scene(self.canvas.get_size()):
                    self.scene.draw(self.canvas)
                self.help.draw(self.canvas)
            frame = self.canvas
            if not same_size and not folding_old:
                frame = pg.transform.smoothscale(self.canvas, screen.get_size())
            if switching:
                self._draw_tube(screen, frame)
            else:
                screen.fill(C.BG)
                screen.blit(frame, (round(shake_x * target.s), round(shake_y * target.s)))
        if self.settings.show_fps:
            self._draw_fps(screen, target)
        crt.scanlines(screen, target.s)

    def _draw_tube(self, screen: pg.Surface, frame: pg.Surface) -> None:
        """An old tube switching: the old picture folds to a bright line, the new opens out."""
        w, h = screen.get_size()
        screen.fill(C.OUTLINE)
        if self._tube < TUBE_OFF_S:
            k = self._tube / TUBE_OFF_S
            picture, open_k = self._old_frame, (1 - k) ** 2
        else:
            k = (self._tube - TUBE_OFF_S) / TUBE_ON_S
            picture, open_k = frame, 1 - (1 - k) ** 3
        rows = max(2, round(h * open_k))
        if picture is not None and picture.get_size() == (w, h):
            screen.blit(pg.transform.scale(picture, (w, rows)), (0, (h - rows) // 2))
        line = max(0.0, 1.0 - open_k * 1.6)  # the bright line is strongest when folded
        if line > 0:
            glow = max(2, round(h * 0.012))
            for thick, kk in ((glow * 3, 0.25), (glow, 0.6), (max(1, glow // 3), 1.0)):
                colour = C.scale(C.lerp(C.CYAN, C.WHITE, 0.6), kk * line)
                rect = pg.Rect(0, h // 2 - thick // 2, w, thick)
                screen.fill(colour, rect, special_flags=pg.BLEND_RGB_ADD)

    def _draw_fps(self, screen: pg.Surface, v: View) -> None:
        """Frames per second, small and dim, in the top-left corner of the screen."""
        left, top, _, _ = v.logical_bounds()
        fps = round(self.fps)
        colour = C.CYAN_DIM if fps >= 50 else C.AMBER if fps >= 30 else C.ERROR
        n = len(str(fps))  # no unlit digits in front: a dim 8 would read as part of the number
        hud.seg_number(screen, v, fps, n, (left + 14, top + 12), 13, colour, glow_k=0.3)
        label_x = left + 14 + hud.digits_width(n, 13) + 8
        hud.label(screen, v, t("hud.fps"), (label_x, top + 14), colour, 10)

    def _window_size(self) -> tuple[int, int]:
        return (pg.display.get_surface() or self.screen).get_size()

    # --- real window ---------------------------------------------------------------------------
    @staticmethod
    def run_forever() -> None:
        logging.basicConfig(level=logging.INFO)
        _enable_dpi_awareness()
        pg.init()
        pg.display.set_caption("NeonPool")
        screen = pg.display.set_mode((0, 0), pg.FULLSCREEN)  # the whole desktop, at its resolution
        app = App(screen)
        app.help.prefetch = True
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
    """Full screen <-> a window that fits the desktop (the app rebuilds itself for the new size)."""
    surf = pg.display.get_surface()
    try:
        if surf is not None and surf.get_flags() & pg.FULLSCREEN:
            pg.display.set_mode(_start_size(), pg.RESIZABLE)
        else:
            pg.display.set_mode((0, 0), pg.FULLSCREEN)
    except pg.error as exc:  # not every driver supports it
        log.warning("fullscreen toggle failed: %s", exc)
