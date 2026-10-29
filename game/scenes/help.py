"""How to play: six topics, one per page: a real picture of the game on the left, a few numbered
sentences on the right (the numbers match the numbers drawn on the picture).
"""

from __future__ import annotations

import pygame as pg

from game import i18n
from game.i18n import t
from game.render import hud
from game.render import palette as C
from game.render.draw import blit_dot, blit_rrect
from game.render.guide_art import Annot
from game.render.synth import Synthwave
from game.render.view import View
from game.scenes import help_pictures
from game.scenes.help_pictures import ART_H

# (key prefix, number of sentences, marker in front of each sentence: a step number or None)
TOPICS = (
    ("guide.p1", 4, (1, 2, 3, None)),
    ("guide.p2", 3, (None, None, None)),
    ("guide.p3", 5, (1, 2, 3, 4, None)),
    ("guide.p4", 3, (1, 2, 3)),
    ("guide.p5", 3, (None, None, None)),
    ("guide.p6", 1, (None,)),
)
CARD = pg.Rect(60, 92, 1160, 500)
ART_POS = (CARD.x + 24, CARD.y + (CARD.h - ART_H) / 2)
TEXT_X, TEXT_W = 740, 450
PREV = pg.Rect(60, 612, 170, 46)
NEXT = pg.Rect(1050, 612, 170, 46)
DOTS = [pg.Rect(640 - 3 * 26 + 4 + i * 26, 624, 18, 22) for i in range(len(TOPICS))]
HORIZON = 604  # the night behind: a low horizon, the floor grid under the page buttons


class HelpScene:
    def __init__(self, app) -> None:
        self.app = app
        self.page = 0
        self.back = None  # the scene Esc returns to (set by App.go_help)
        self._hover: object = None
        self._clock = 0.0
        self.fx = hud.ButtonFx()
        self.set_view(app.view)

    def set_view(self, v: View) -> None:
        self.view = v
        self._pictures: dict[tuple, pg.Surface] = {}
        self.synth = Synthwave(v, HORIZON, sun=False, dim=0.6)

    def shake_offset(self) -> tuple[float, float]:
        return 0.0, 0.0

    def update(self, dt: float) -> None:
        self._clock += dt
        self.synth.update(dt)
        chosen = self._hover if self._hover in ("prev", "next") else None
        self.fx.update(dt, chosen, {"prev": PREV, "next": NEXT}, self._clock)

    def _picture(self, index: int) -> pg.Surface:
        """The picture of a topic: made when first shown, and again after a language change."""
        key = (index, i18n.get_lang())
        if key not in self._pictures:
            self._pictures[key] = help_pictures.build(index, self.view)
        return self._pictures[key]

    # --- input -------------------------------------------------------------------------------
    def go(self, page: int) -> None:
        if page != self.page and 0 <= page < len(TOPICS):
            self.synth.pulse(PREV.centerx if page < self.page else NEXT.centerx, self._clock)
            self.page = page
            self.app.audio.play_click()

    def handle_event(self, e: pg.event.Event) -> None:
        if e.type == pg.KEYDOWN:
            if e.key in (pg.K_ESCAPE, pg.K_h):
                self.app.leave_help()
            elif e.key in (pg.K_RIGHT, pg.K_d, pg.K_RETURN, pg.K_SPACE):
                self.go(self.page + 1)
            elif e.key in (pg.K_LEFT, pg.K_a):
                self.go(self.page - 1)
        elif e.type == pg.MOUSEMOTION:
            self.synth.point_to(e.pos)
            target = self._target(e.pos)
            if target is not None and target != self._hover:
                self.app.audio.play_hover()
            self._hover = target
        elif e.type == pg.MOUSEBUTTONDOWN and e.button == 1:
            target = self._target(e.pos)
            if target in ("prev", "next"):
                self.fx.press(target, self._clock)
                self.go(self.page + (1 if target == "next" else -1))
            elif isinstance(target, int):
                self.go(target)

    @staticmethod
    def _target(pos) -> object:
        if PREV.collidepoint(pos):
            return "prev"
        if NEXT.collidepoint(pos):
            return "next"
        return next((i for i, r in enumerate(DOTS) if r.collidepoint(pos)), None)

    # --- drawing -----------------------------------------------------------------------------
    def draw(self, canvas: pg.Surface) -> None:
        v, i = self.view, self.page
        self.synth.draw(canvas, self._clock)
        hud.glow_text(canvas, v, t("guide.title"), 40, C.WHITE, C.MAGENTA, (60, 50), face="display",
                      align="left")  # fmt: skip
        hud.keycap(canvas, v, t("keycap.esc"), (1220 - 120, 42), 36)
        hud.text(canvas, v, t("guide.back_label"), 14, C.TEXT_DIM, (1220 - 76, 46))
        blit_rrect(canvas, v, CARD.x, CARD.y, CARD.w, CARD.h, 10, C.PANEL, 1.6, C.VIOLET, 0.5)
        canvas.blit(self._picture(i), v.ipt(ART_POS))
        hud.label(canvas, v, t("guide.page").format(n=i + 1, of=len(TOPICS)), (TEXT_X, 128),
                  C.TEXT_DIM, 11)  # fmt: skip
        hud.text(canvas, v, t(f"{TOPICS[i][0]}.title"), 28, C.CYAN, (TEXT_X, 148), bold=True)
        self._sentences(canvas, i)
        for key, rect, label in (("prev", PREV, "guide.prev"), ("next", NEXT, "guide.next")):
            off = (key == "prev" and i == 0) or (key == "next" and i == len(TOPICS) - 1)
            hud.live_button(canvas, v, rect, t(label), self.fx, key, self._clock,
                            primary=False, enabled=not off)  # fmt: skip
        for k, r in enumerate(DOTS):
            lit = k == i
            colour = C.ACCENT if lit else C.PANEL_EDGE
            blit_dot(canvas, v, r.center, 5 if lit else 4, colour, 0.9 if lit else 0.0)

    def _sentences(self, canvas: pg.Surface, topic: int, size: int = 18) -> None:
        """The topic's sentences, each behind its step number (or a small dot)."""
        v = self.view
        prefix, count, markers = TOPICS[topic]
        step, y = round(size * 1.55), 202.0
        for i in range(count):
            self._marker(canvas, markers[i], (TEXT_X + 12, y + size * 0.36))
            for line in hud.wrap(v, t(f"{prefix}.b{i + 1}"), size, TEXT_W - 36):
                hud.text(canvas, v, line, size, C.TEXT, (TEXT_X + 36, y))
                y += step
            y += step * 0.45

    def _marker(self, canvas: pg.Surface, n: int | None, c: tuple[float, float]) -> None:
        a = Annot(canvas, self.view)
        if n is None:
            a.disc(c, 3.5, C.ACCENT)
        else:
            a.step(n, c)
