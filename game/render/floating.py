"""A lit panel that slides up over a scene and darkens it: the one component for it.

Settings and the Play panel are both this. While it opens the scene behind is kept as a picture
(`FrozenScene`), and once it has opened the dark picture with the frame and the title painted on
it is baked once and pasted whole; a subclass paints only what moves (`_paint_live`).

A panel with steps of different sizes sets `RESIZES` and answers `fit_h()` (the height of what it
shows now): the frame is as tall as that and sits centred. Changing step means calling
`_morph_begin(new_height)` just before the content changes; the old content fades out, the frame
glides to the new height, the new content fades in.
"""

from __future__ import annotations

from dataclasses import dataclass

import pygame as pg

from game.render import hud
from game.render import palette as C
from game.render.draw import blit_rrect, blit_rrect_stretch, veil
from game.render.frozen import FrozenScene
from game.render.view import View

MORPH_S = 0.32  # a change of step takes this long ...
OUT_END = 0.09  # ... the old content is gone by here,
GLIDE_FROM, GLIDE_TO = 0.06, 0.26  # the frame changes height between these,
IN_FROM = 0.20  # ... and the new content fades in from here to the end
EDGE_PX = 5  # the content area sits this far inside the frame (the lit edge stays untouched)


@dataclass
class _Morph:
    from_h: float
    to_h: float
    old: tuple[pg.Surface, tuple[int, int]] | None  # picture of the old content, and where it goes
    t: float = 0.0


def _unit(x: float) -> float:
    return max(0.0, min(1.0, x))


class FloatPanel:
    RECT: pg.Rect  # where it sits when open (logical px); a resizing panel keeps its centre
    RESIZES = False  # True: the height follows `fit_h()`
    DIM_ALPHA = 205  # how dark the scene behind goes
    OPEN_S, CLOSE_S = 0.22, 0.16  # it slides up in / back down in this long
    SLIDE_PX = 46  # ... from this far below

    def __init__(self) -> None:
        self.is_open = False
        self.k = 0.0  # 0 closed .. 1 fully open
        self._closing = False
        self._warm = 0.0  # the view scale the sprites were last made for (see prewarm)
        self._frozen = FrozenScene()  # the scene behind, kept as a picture while the panel is up
        self._v: View | None = None  # the view it was last drawn with
        self._h: float | None = None  # the height now, while it glides (None: `fit_h()`)
        self._morph: _Morph | None = None
        self._ground: tuple[float, tuple[int, int, int]] = (0.0, C.PANEL)  # see `_inside`

    # --- to fill in ---------------------------------------------------------------------------
    def title(self) -> str:
        raise NotImplementedError

    def _paint_live(self, canvas: pg.Surface, pv: View) -> None:
        raise NotImplementedError

    def fit_h(self) -> float:
        return self.RECT.h

    # --- where it is ---------------------------------------------------------------------------
    def rect(self) -> pg.Rect:
        """The frame as it is right now (logical px)."""
        r = self.RECT
        if not self.RESIZES:
            return r
        h = self.fit_h() if self._h is None else self._h
        return pg.Rect(r.x, round(r.centery - h / 2), r.w, round(h))

    @staticmethod
    def _inner(r: pg.Rect) -> pg.Rect:
        return r.inflate(-2 * EDGE_PX, -2 * EDGE_PX)

    def _inside(self, v: View) -> tuple[int, int, int]:
        """The colour inside the frame as it is drawn: a hair off `C.PANEL` (the sprite is
        premultiplied and shrunk), so what fades into it must use this one, or a faint box shows."""
        if self._ground[0] != v.s:
            r = self.RECT
            probe = pg.Surface(v.rect(0, 0, r.w + 40, r.h + 40).size)
            self._paint_frame(probe, View(v.s), pg.Rect(20, 20, r.w, r.h))
            self._ground = (v.s, tuple(probe.get_at(v.ipt((20 + r.w / 2, 20 + r.h / 2)))[:3]))
        return self._ground[1]

    # --- opening and closing -------------------------------------------------------------------
    def _open(self) -> None:
        self.is_open, self._closing = True, False
        self._h = self._morph = None
        self._frozen.clear()

    def _close(self) -> None:
        self._closing = True
        self._h = self._morph = None

    def _animate(self, dt: float) -> None:
        if self._closing:
            self.k = max(0.0, self.k - dt / self.CLOSE_S)
            if self.k == 0.0:
                self.is_open, self._closing = False, False
                self._frozen.clear()
        elif self.is_open:
            self.k = min(1.0, self.k + dt / self.OPEN_S)
        m = self._morph
        if m is None:
            return
        m.t += dt
        if m.t >= MORPH_S:
            self._morph, self._h = None, m.to_h
            self._frozen.rebake()  # at rest again: the frame and title are painted on the picture
        else:
            u = _unit((m.t - GLIDE_FROM) / (GLIDE_TO - GLIDE_FROM))
            self._h = m.from_h + (m.to_h - m.from_h) * (1 - (1 - u) ** 3)

    # --- changing step -------------------------------------------------------------------------
    def _morph_begin(self, to_h: float) -> None:
        """Call BEFORE the content changes: it keeps a picture of the old content to fade out."""
        v = self._v
        live = self.RESIZES and self.is_open and not self._closing and self.k >= 1.0 and v
        if not live:
            self._h, self._morph = to_h, None
            return
        r = self.rect()
        old = None
        if self._morph is None:  # (mid-glide the old content is not whole: it just goes)
            box = v.rect(*self._inner(r))
            surf = pg.Surface(box.size)
            surf.fill(self._inside(v))
            sv = v.shifted(box.x, box.y)
            self._paint_title(surf, sv, r, 1.0)
            self._paint_live(surf, sv)
            old = (surf, box.topleft)
        self._morph = _Morph(r.h, to_h, old)
        self._h = r.h

    # --- drawing -------------------------------------------------------------------------------
    def prewarm(self, v: View) -> None:
        """Draw the whole panel once, off screen, so every sprite it needs already exists when
        it is first opened (the real game does this once at start)."""
        if self._warm == v.s:
            return
        self._warm = v.s
        probe = pg.Surface(v.canvas)
        was = self.is_open, self.k, self._frozen, self._morph, self._h
        self.is_open, self.k, self._frozen, self._morph, self._h = (
            True,
            1.0,
            FrozenScene(),
            None,
            None,
        )
        self.draw(probe, v)
        self.is_open, self.k, self._frozen, self._morph, self._h = was

    def covers_scene(self, size: tuple[int, int]) -> bool:
        """True when the scene behind need not be drawn: a frozen picture of it is used (it is
        under a dark veil, so nobody sees it stand still). Not while closing: the live scene is
        needed to come back to."""
        return self.is_open and not self._closing and self._frozen.covers(size)

    def draw(self, canvas: pg.Surface, v: View) -> None:
        if not self.is_open:
            return
        self._v = v
        if self.k >= 1.0 and not self._closing:  # fully open
            if self._morph is None:  # at rest: paste the baked picture
                self._frozen.paste_baked(
                    canvas, self.DIM_ALPHA, lambda base: self._paint_static(base, v, 1.0)
                )
                self._paint_live(canvas, v)
            else:  # changing step: the dark scene only; the frame and its content are painted live
                self._frozen.paste_baked(canvas, self.DIM_ALPHA, lambda base: None)
                self._paint_morph(canvas, v, self._morph)
            return
        e = 1 - (1 - self.k) ** 3
        if not self._closing:
            self._frozen.under(canvas)
        canvas.blit(veil(canvas.get_size(), round(self.DIM_ALPHA * e)), (0, 0))
        pv = View(v.s, v.ox, v.oy + round((1 - e) * self.SLIDE_PX * v.s), v.cw, v.ch)  # sliding up
        self._paint_static(canvas, pv, e)
        self._paint_live(canvas, pv)

    def _paint_frame(self, canvas: pg.Surface, pv: View, r: pg.Rect) -> None:
        # the frame's light stays full while it slides: a halo that changed every frame meant a
        # new sprite every frame (60 ms each), which made the opening stutter
        paint = blit_rrect_stretch if self.RESIZES else blit_rrect
        paint(canvas, pv, r.x, r.y, r.w, r.h, 10, C.PANEL, 1.8, C.VIOLET, 1.0)

    def _paint_title(self, canvas: pg.Surface, pv: View, r: pg.Rect, e: float) -> None:
        hud.glow_text(canvas, pv, self.title(), 36, C.WHITE, C.MAGENTA, (r.centerx, r.y + 42),
                      face="display", strength=e)  # fmt: skip

    def _paint_static(self, canvas: pg.Surface, pv: View, e: float) -> None:
        """The panel's frame and title: they do not move once it is open."""
        r = self.rect()
        self._paint_frame(canvas, pv, r)
        self._paint_title(canvas, pv, r, e)

    def _paint_morph(self, canvas: pg.Surface, v: View, m: _Morph) -> None:
        r = self.rect()
        self._paint_frame(canvas, v, r)
        area = v.rect(*self._inner(r))
        kept = canvas.get_clip()
        canvas.set_clip(area)
        gone = _unit(m.t / OUT_END)  # 0 whole .. 1 gone
        if m.old is not None and gone < 1.0:
            canvas.blit(m.old[0], m.old[1])
            self._cover(canvas, area, gone, self._inside(v))
        shown = _unit((m.t - IN_FROM) / (MORPH_S - IN_FROM))  # 0 not there .. 1 whole
        if shown > 0.0:
            self._paint_title(canvas, v, r, 1.0)
            self._paint_live(canvas, v)
            self._cover(canvas, area, 1.0 - shown, self._inside(v))
        canvas.set_clip(kept)

    @staticmethod
    def _cover(canvas: pg.Surface, area: pg.Rect, k: float, ground) -> None:
        """Wash `area` toward the colour inside the frame (k 0 untouched .. 1 blank): what is
        painted under it fades."""
        if k > 0.0:
            sheet = pg.Surface(area.size)
            sheet.fill(ground)
            sheet.set_alpha(round(255 * min(k, 1.0)))
            canvas.blit(sheet, area.topleft)
