"""A lit panel that slides up over a scene and darkens it: the one component for it.

Settings and the Play panel are both this. While it opens the scene behind is kept as a picture
(`FrozenScene`), and once it has opened the dark picture with the frame and the title painted on
it is baked once and pasted whole; a subclass paints only what moves (`_paint_live`).
"""

from __future__ import annotations

import pygame as pg

from game.render import hud
from game.render import palette as C
from game.render.draw import blit_rrect, veil
from game.render.frozen import FrozenScene
from game.render.view import View


class FloatPanel:
    RECT: pg.Rect  # where it sits when open (logical px)
    DIM_ALPHA = 205  # how dark the scene behind goes
    OPEN_S, CLOSE_S = 0.22, 0.16  # it slides up in / back down in this long
    SLIDE_PX = 46  # ... from this far below

    def __init__(self) -> None:
        self.is_open = False
        self.k = 0.0  # 0 closed .. 1 fully open
        self._closing = False
        self._warm = 0.0  # the view scale the sprites were last made for (see prewarm)
        self._frozen = FrozenScene()  # the scene behind, kept as a picture while the panel is up

    # --- to fill in ---------------------------------------------------------------------------
    def title(self) -> str:
        raise NotImplementedError

    def _paint_live(self, canvas: pg.Surface, pv: View) -> None:
        raise NotImplementedError

    # --- opening and closing -------------------------------------------------------------------
    def _open(self) -> None:
        self.is_open, self._closing = True, False
        self._frozen.clear()

    def _close(self) -> None:
        self._closing = True

    def _animate(self, dt: float) -> None:
        if self._closing:
            self.k = max(0.0, self.k - dt / self.CLOSE_S)
            if self.k == 0.0:
                self.is_open, self._closing = False, False
                self._frozen.clear()
        elif self.is_open:
            self.k = min(1.0, self.k + dt / self.OPEN_S)

    # --- drawing -------------------------------------------------------------------------------
    def prewarm(self, v: View) -> None:
        """Draw the whole panel once, off screen, so every sprite it needs already exists when
        it is first opened (the real game does this once at start)."""
        if self._warm == v.s:
            return
        self._warm = v.s
        probe = pg.Surface(v.canvas)
        was = self.is_open, self.k, self._frozen
        self.is_open, self.k, self._frozen = True, 1.0, FrozenScene()
        self.draw(probe, v)
        self.is_open, self.k, self._frozen = was

    def covers_scene(self, size: tuple[int, int]) -> bool:
        """True when the scene behind need not be drawn: a frozen picture of it is used (it is
        under a dark veil, so nobody sees it stand still). Not while closing: the live scene is
        needed to come back to."""
        return self.is_open and not self._closing and self._frozen.covers(size)

    def draw(self, canvas: pg.Surface, v: View) -> None:
        if not self.is_open:
            return
        if self.k >= 1.0 and not self._closing:  # fully open: paste the baked picture
            self._frozen.paste_baked(
                canvas, self.DIM_ALPHA, lambda base: self._paint_static(base, v, 1.0)
            )
            self._paint_live(canvas, v)
            return
        e = 1 - (1 - self.k) ** 3
        if not self._closing:
            self._frozen.under(canvas)
        canvas.blit(veil(canvas.get_size(), round(self.DIM_ALPHA * e)), (0, 0))
        pv = View(v.s, v.ox, v.oy + round((1 - e) * self.SLIDE_PX * v.s), v.cw, v.ch)  # sliding up
        self._paint_static(canvas, pv, e)
        self._paint_live(canvas, pv)

    def _paint_static(self, canvas: pg.Surface, pv: View, e: float) -> None:
        """The panel's frame and title: they do not move once it is open."""
        # the frame's light stays full while it slides: a halo that changed every frame meant a
        # new sprite every frame (60 ms each), which made the opening stutter
        r = self.RECT
        blit_rrect(canvas, pv, r.x, r.y, r.w, r.h, 10, C.PANEL, 1.8, C.VIOLET, 1.0)
        hud.glow_text(canvas, pv, self.title(), 36, C.WHITE, C.MAGENTA, (r.centerx, r.y + 42),
                      face="display", strength=e)  # fmt: skip
