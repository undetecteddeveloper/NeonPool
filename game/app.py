"""App: owns the logical canvas, scales it to the window, routes events to the scene."""

from __future__ import annotations

import logging

import pygame as pg

from game.config import LOGICAL_SIZE
from game.render import palette as C
from game.render.viewport import fit, window_to_logical
from game.scenes.play import PlayScene

log = logging.getLogger("mathofpool")
_MOUSE_EVENTS = (pg.MOUSEBUTTONDOWN, pg.MOUSEBUTTONUP, pg.MOUSEMOTION)


class App:
    def __init__(self, screen: pg.Surface) -> None:
        self.screen = screen
        self.canvas = pg.Surface(LOGICAL_SIZE)
        self.scene = PlayScene(self)
        self.running = True

    # --- contract used by tools/smoke.py and tools/shot.py ---------------------------------
    def handle_event(self, e: pg.event.Event) -> None:
        if e.type == pg.QUIT:
            self.running = False
            return
        if e.type == pg.KEYDOWN and e.key == pg.K_F11:
            _toggle_fullscreen()
            return
        if e.type in _MOUSE_EVENTS:
            pos = window_to_logical(e.pos, self._window_size(), LOGICAL_SIZE)
            e = pg.event.Event(e.type, {**e.dict, "pos": pos})
        self.scene.handle_event(e)

    def update(self, dt: float) -> None:
        self.scene.update(dt)

    def draw(self) -> None:
        self.scene.draw(self.canvas)
        screen = pg.display.get_surface() or self.screen
        screen.fill(C.OUTLINE)
        _, x, y, w, h = fit(screen.get_size(), LOGICAL_SIZE)
        if (w, h) == LOGICAL_SIZE:
            screen.blit(self.canvas, (x, y))
        else:
            screen.blit(pg.transform.smoothscale(self.canvas, (w, h)), (x, y))

    def _window_size(self) -> tuple[int, int]:
        return (pg.display.get_surface() or self.screen).get_size()

    # --- real window ---------------------------------------------------------------------------
    @staticmethod
    def run_forever() -> None:
        logging.basicConfig(level=logging.INFO)
        pg.init()
        pg.display.set_caption("MathofPool")
        screen = pg.display.set_mode(LOGICAL_SIZE, pg.RESIZABLE)
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


def _toggle_fullscreen() -> None:
    try:
        pg.display.toggle_fullscreen()
    except pg.error as exc:  # not every driver supports it
        log.warning("fullscreen toggle failed: %s", exc)
