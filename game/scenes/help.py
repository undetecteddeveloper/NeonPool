"""How to play: a small carousel that opens over whatever is behind it (the menu, or the table
during a game), which goes dark. Seven topics, one per page: a real picture of the game and a few
numbered sentences (the numbers match the numbers drawn on the picture). Arrows (or the keys)
turn the pages round and round.

Motion: the card opens out of a bright horizontal line (like an old tube) and closes back into
it. Turning a page slides it the way the arrow points while it fades: the old page leaves
sideways, the new one comes in from the other side.
"""

from __future__ import annotations

from dataclasses import dataclass

import pygame as pg

from game import i18n
from game.i18n import t
from game.render import hud
from game.render import palette as C
from game.render.draw import Aa, blit_dot, blit_rrect, veil
from game.render.frozen import FrozenScene
from game.render.guide_art import Annot
from game.render.view import View
from game.scenes import help_pictures
from game.scenes.help_pictures import ART_W

# (key prefix, number of sentences, marker in front of each sentence: a step number or None)
TOPICS = (
    ("guide.p1", 5, (1, 2, 3, None, None)),
    ("guide.p2", 3, (None, None, None)),
    ("guide.p3", 5, (1, 2, 3, 4, None)),
    ("guide.p4", 3, (1, 2, 3)),
    ("guide.p5", 3, (None, None, None)),
    ("guide.p6", 2, (None, None)),
    ("guide.p7", 5, (None, None, None, None, None)),
)
OPEN_S, CLOSE_S = 0.28, 0.2  # the card opens out of a line / folds back into it in this long
DIM_ALPHA = 228  # how dark the scene behind goes (nearly black: only a glimmer of it shows)
FLIP_S = 0.26  # turning a page: the old one slides out and fades, the new one slides in
FLIP_SLIDE_PX = 72  # ... this far (logical px)
EDGE_PAD = 24  # the card's glow reaches this far past its edge (logical px)
DOT_STEP = 26


@dataclass(frozen=True)
class Layout:
    """Where everything stands (logical px); the module uses `LAYOUT`."""

    card: pg.Rect
    content: pg.Rect  # the part that flips: picture, page label, topic title, sentences
    art_k: float  # the picture's size, relative to ART_W x ART_H
    art: tuple[float, float]  # top-left of the picture
    label: tuple[float, float]  # "Page 1/6"
    title: tuple[float, float]
    title_size: float
    text: tuple[float, float]  # top-left of the first sentence
    text_w: float
    text_size: float
    prev: pg.Rect
    next: pg.Rect
    close: pg.Rect
    dots_y: float
    header: tuple[float, float]  # the title of the card, left-middle


def _wide() -> Layout:
    """A wide card: picture on the left, words on the right, round arrows outside the card."""
    card = pg.Rect(150, 112, 980, 496)
    content = pg.Rect(card.x + 16, card.y + 70, card.w - 32, 386)
    art = (card.x + 34, content.y + 46)
    tx = art[0] + ART_W * 0.76 + 30
    return Layout(
        card=card,
        content=content,
        art_k=0.76,
        art=art,
        label=(tx, content.y + 30),
        title=(tx, content.y + 50),
        title_size=24,
        text=(tx, content.y + 94),
        text_w=card.right - 34 - tx,
        text_size=15,
        prev=pg.Rect(card.x - 74, card.centery - 26, 52, 52),
        next=pg.Rect(card.right + 22, card.centery - 26, 52, 52),
        close=pg.Rect(card.right - 34 - 36, card.y + 18, 36, 36),
        dots_y=card.bottom - 32,
        header=(card.x + 34, card.y + 36),
    )


LAYOUT = _wide()


def dot_rect(i: int, layout: Layout | None = None) -> pg.Rect:
    layout = layout or LAYOUT
    left = layout.card.centerx - len(TOPICS) * DOT_STEP / 2 + 4
    return pg.Rect(round(left + i * DOT_STEP), round(layout.dots_y - 11), 18, 22)


# --- drawing helpers ---------------------------------------------------------------------------
def _light_line(canvas: pg.Surface, v: View, x: float, y: float, w: float, strength: float) -> None:
    """A bright horizontal line (the tube's picture folded flat), glowing `strength` 0..1."""
    blit_rrect(canvas, v, x, y - 1.5, w, 3, 1.5, C.WHITE, 1.0, C.CYAN, round(0.4 + strength, 1))


def flip_state(age: float, direction: int) -> tuple[tuple[float, float], tuple[float, float]]:
    """How a page turn looks `age` seconds in: ((x, opacity) of the old page, (x, opacity) of
    the new one), x in logical px from where a page rests. `direction` 1 = forward (the old page
    leaves to the left), -1 = back. Both ease out; the two opacities always add up to 1."""
    u = min(1.0, max(0.0, age / FLIP_S))
    e = 1 - (1 - u) ** 3
    return (-direction * FLIP_SLIDE_PX * e, 1 - e), (direction * FLIP_SLIDE_PX * (1 - e), e)


def _chevron(canvas: pg.Surface, v: View, c: tuple[float, float], d: int, colour) -> None:
    """A "<" (d = 1) or ">" (d = -1) drawn as a line."""
    size = 9.0
    layer = Aa(canvas, v, v.rect(c[0] - size - 4, c[1] - size - 4, 2 * size + 8, 2 * size + 8), 3)
    pts = [
        (c[0] + d * size * 0.45, c[1] - size),
        (c[0] - d * size * 0.45, c[1]),
        (c[0] + d * size * 0.45, c[1] + size),
    ]
    pg.draw.lines(layer.surf, colour, False, [layer.pt(p) for p in pts], round(layer.n(3.0)))
    layer.done()


def _cross(canvas: pg.Surface, v: View, c: tuple[float, float], colour) -> None:
    size = 6.5
    layer = Aa(canvas, v, v.rect(c[0] - size - 4, c[1] - size - 4, 2 * size + 8, 2 * size + 8), 3)
    for a, b in (((-1, -1), (1, 1)), ((-1, 1), (1, -1))):
        p = (c[0] + a[0] * size, c[1] + a[1] * size)
        q = (c[0] + b[0] * size, c[1] + b[1] * size)
        pg.draw.line(layer.surf, colour, layer.pt(p), layer.pt(q), round(layer.n(2.6)))
    layer.done()


class HelpPanel:
    def __init__(self, app) -> None:
        self.app = app
        self.is_open = False
        self.page = 0  # kept between visits: H in a game goes back to where you left off
        self.k = 0.0  # 0 closed .. 1 fully open
        self._closing = False
        self._hover: object = None
        self._clock = 0.0
        self._flip_at: float | None = None  # when the last page turn started
        self._frozen = FrozenScene()  # the scene behind, kept as a picture while the card is up
        self._from = 0  # the page that is sliding away
        self._flip_dir = 1  # 1: forward (the arrow to the right), -1: back
        self.fx = hud.ButtonFx()
        self.prefetch = False  # the real game makes the pages ahead of time (see prefetch_one)
        self.set_view(app.view)

    def set_view(self, v: View) -> None:
        self.view = v
        self._pages: dict[tuple, pg.Surface] = {}
        self._fill: tuple[int, int, int] | None = None
        self._frozen.clear()

    def _card_fill(self) -> tuple[int, int, int]:
        """The colour of the card's inside (the frame tints it a little): a page is painted on it,
        so no lighter rectangle shows round the picture."""
        if self._fill is None:
            card, v = LAYOUT.card, self.view
            probe = pg.Surface(v.rect(card.x - 30, card.y - 30, card.w + 60, card.h + 60).size)
            probe.fill(C.BG)
            pv = v.shifted(*v.ipt((card.x - 30, card.y - 30)))
            blit_rrect(probe, pv, card.x, card.y, card.w, card.h, 10, C.PANEL, 1.8, C.VIOLET, 1.0)
            self._fill = tuple(probe.get_at(pv.ipt((card.x + 40, card.centery)))[:3])
        return self._fill

    # --- opening and closing -------------------------------------------------------------------
    def open(self) -> None:
        self.is_open, self._closing, self._flip_at = True, False, None
        self._hover = None
        self._frozen.clear()

    def close(self) -> None:
        if self.is_open and not self._closing:
            self._closing = True
            self.app.audio.play_click()

    def go(self, page: int, via: str | None = None, direction: int | None = None) -> None:
        """Turn to `page` (the arrows wrap round). `via` is the button that flashes; `direction`
        is which way the page slides (1 forward, -1 back; by default towards the higher page)."""
        page %= len(TOPICS)
        if via:
            self.fx.press(via, self._clock)
        if page != self.page:
            self._flip_dir = direction or (1 if page > self.page else -1)
            self._from, self.page, self._flip_at = self.page, page, self._clock
            self.app.audio.play_click()

    # --- input ---------------------------------------------------------------------------------
    def handle_event(self, e: pg.event.Event) -> None:
        if self._closing:
            return
        if e.type == pg.KEYDOWN:
            if e.key in (pg.K_ESCAPE, pg.K_h):
                self.close()
            elif e.key in (pg.K_RIGHT, pg.K_d, pg.K_RETURN, pg.K_KP_ENTER, pg.K_SPACE):
                self.go(self.page + 1, "next", 1)
            elif e.key in (pg.K_LEFT, pg.K_a):
                self.go(self.page - 1, "prev", -1)
        elif e.type == pg.MOUSEMOTION:
            target = self._target(e.pos)
            if target not in (None, "card") and target != self._hover:
                self.app.audio.play_hover()
            self._hover = target
        elif e.type == pg.MOUSEBUTTONDOWN and e.button == 1:
            target = self._target(e.pos)
            if target is None:
                self.close()  # a click outside the card closes it
            elif target == "close":
                self.fx.press("close", self._clock)
                self.close()
            elif target in ("prev", "next"):
                self.go(
                    self.page + (1 if target == "next" else -1),
                    target,
                    1 if target == "next" else -1,
                )
            elif isinstance(target, int):
                self.go(target)

    def _target(self, pos) -> object:
        layout = LAYOUT
        if layout.prev.collidepoint(pos):
            return "prev"
        if layout.next.collidepoint(pos):
            return "next"
        if layout.close.collidepoint(pos):
            return "close"
        dot = next((i for i in range(len(TOPICS)) if dot_rect(i).collidepoint(pos)), None)
        if dot is not None:
            return dot
        return "card" if layout.card.collidepoint(pos) else None

    # --- time ----------------------------------------------------------------------------------
    def update(self, dt: float) -> None:
        if not self.is_open:
            return
        self._clock += dt
        if self._closing:
            self.k = max(0.0, self.k - dt / CLOSE_S)
            if self.k == 0.0:
                self.is_open, self._closing = False, False
                self._frozen.clear()
        else:
            self.k = min(1.0, self.k + dt / OPEN_S)
        if self._flip_at is not None and self._clock - self._flip_at >= FLIP_S:
            self._flip_at = None
        if self.prefetch and self.k >= 1.0 and not self._closing and self._flip_at is None:
            self.prefetch_one()  # the card stands still: a good moment
        chosen = self._hover if self._hover in ("prev", "next", "close") else None
        rects = {"prev": LAYOUT.prev, "next": LAYOUT.next, "close": LAYOUT.close}
        self.fx.update(dt, chosen, rects, self._clock)

    # --- one page, made once ---------------------------------------------------------------------
    def _page(self, index: int) -> pg.Surface:
        """The flipping part of a page, in device px: made when first shown, and again after a
        language or window-size change."""
        key = (index, i18n.get_lang())
        if key not in self._pages:
            self._pages[key] = self._make_page(index)
        return self._pages[key]

    def prefetch_one(self) -> bool:
        """Make ONE page that is not made yet (this one first, then its neighbours): done while
        nothing moves, so the first opening and the page turns never stall on a picture. Returns
        whether it had anything to make."""
        n, lang = len(TOPICS), i18n.get_lang()
        for i in (self.page, (self.page + 1) % n, (self.page - 1) % n, *range(n)):
            if (i, lang) not in self._pages:
                self._page(i)
                return True
        return False

    def _make_page(self, index: int) -> pg.Surface:
        v, layout = self.view, LAYOUT
        surf = pg.Surface(v.rect(*layout.content).size)
        surf.fill(self._card_fill())
        cv = v.shifted(*v.ipt(layout.content.topleft))  # draw with the page's own corner as origin
        pic = help_pictures.build(index, View(v.s * layout.art_k))
        surf.blit(pic, cv.ipt(layout.art))
        prefix, count, markers = TOPICS[index]
        hud.label(surf, cv, t("guide.page").format(n=index + 1, of=len(TOPICS)), layout.label,
                  C.TEXT_DIM, 11)  # fmt: skip
        hud.text(surf, cv, t(f"{prefix}.title"), layout.title_size, C.CYAN, layout.title, bold=True)
        size = layout.text_size
        step, y = round(size * 1.5), layout.text[1]
        for i in range(count):
            self._marker(surf, cv, markers[i], (layout.text[0] + 10, y + size * 0.36))
            for line in hud.wrap(cv, t(f"{prefix}.b{i + 1}"), size, layout.text_w - 30):
                hud.text(surf, cv, line, size, C.TEXT, (layout.text[0] + 30, y))
                y += step
            y += step * 0.45
        return surf

    @staticmethod
    def _marker(surf: pg.Surface, cv: View, n: int | None, c: tuple[float, float]) -> None:
        a = Annot(surf, cv)
        if n is None:
            a.disc(c, 3.5, C.ACCENT)
        else:
            a.step(n, c)

    # --- drawing ---------------------------------------------------------------------------------
    def covers_scene(self, size: tuple[int, int]) -> bool:
        """True when the scene behind need not be drawn: a frozen copy of it is used instead (it
        is under a nearly black veil, so nobody sees it stand still). Not while closing: the live
        scene must be there to come back to."""
        return self.is_open and not self._closing and self._frozen.covers(size)

    def draw(self, canvas: pg.Surface) -> None:
        if not self.is_open:
            return
        v, layout, size = self.view, LAYOUT, canvas.get_size()
        if self.k >= 1.0 and not self._closing:
            self._draw_open(canvas, v)
            return
        e = 1 - (1 - self.k) ** 3
        if not self._closing:  # (closing: the live scene is on the canvas, to come back to)
            self._frozen.under(canvas)
        canvas.blit(veil(size, round(DIM_ALPHA * e)), (0, 0))
        card = layout.card
        opening = self.k < 1.0
        if opening:  # only a band round the middle line is lit, and it grows to the whole card
            half = card.h * e / 2
            canvas.set_clip(v.rect(card.x - EDGE_PAD, card.centery - half, card.w + 2 * EDGE_PAD,
                                   2 * half))  # fmt: skip
        self._paint(canvas, v)
        if opening:
            canvas.set_clip(None)
            glow = 1 - e
            for y in (card.centery - half, card.centery + half):
                _light_line(canvas, v, card.x, y, card.w, glow)

    def _draw_open(self, canvas: pg.Surface, v: View) -> None:
        """The card is fully open: one dark picture with the card's frame is pasted (baked once),
        and only what moves (page, arrows, dots) is drawn over it."""
        self._frozen.paste_baked(canvas, DIM_ALPHA, lambda base: self._paint_static(base, v))
        self._paint_live(canvas, v)

    def _paint(self, canvas: pg.Surface, v: View) -> None:
        self._paint_static(canvas, v)
        self._paint_live(canvas, v)

    @staticmethod
    def _paint_static(canvas: pg.Surface, v: View) -> None:
        """The card's frame and title: they never move."""
        layout = LAYOUT
        card = layout.card
        blit_rrect(canvas, v, card.x, card.y, card.w, card.h, 10, C.PANEL, 1.8, C.VIOLET, 1.0)
        hud.glow_text(canvas, v, t("guide.title"), 26, C.WHITE, C.MAGENTA, layout.header,
                      face="display", align="left")  # fmt: skip

    def _paint_live(self, canvas: pg.Surface, v: View) -> None:
        layout = LAYOUT
        self._content(canvas, v)
        for key, rect, d in (("prev", layout.prev, 1), ("next", layout.next, -1)):
            self._arrow_button(canvas, v, rect, d, key)
        self._close_button(canvas, v, layout.close)
        for i in range(len(TOPICS)):
            lit = i == self.page
            colour = C.ACCENT if lit else C.PANEL_EDGE
            blit_dot(canvas, v, dot_rect(i).center, 5 if lit else 4, colour, 0.9 if lit else 0.0)

    def _content(self, canvas: pg.Surface, v: View) -> None:
        rect = LAYOUT.content
        if self._flip_at is None:
            canvas.blit(self._page(self.page), v.ipt(rect.topleft))
            return
        dev = v.rect(*rect)
        old, new = flip_state(self._clock - self._flip_at, self._flip_dir)
        canvas.set_clip(dev)  # a page never shows outside its place on the card
        for surf, (dx, opacity) in ((self._page(self._from), old), (self._page(self.page), new)):
            if opacity <= 0.0:
                continue
            surf.set_alpha(round(255 * opacity))
            canvas.blit(surf, (dev.x + v.i(dx), dev.y))
            surf.set_alpha(None)
        canvas.set_clip(None)

    def _arrow_button(self, canvas, v: View, rect: pg.Rect, d: int, key: str) -> None:
        lit, press = self.fx.lit.get(key, 0.0), self.fx.press_k(key, self._clock)
        grow = 1.0 + 0.08 * lit - 0.1 * press
        w, h = rect.w * grow, rect.h * grow
        fill = C.lerp(C.lerp(C.PANEL, C.PANEL_HOT, lit), C.lerp(C.CYAN, C.WHITE, 0.3), 0.35 * press)
        edge = C.lerp(C.PANEL_EDGE, C.CYAN, lit)
        blit_rrect(canvas, v, rect.centerx - w / 2, rect.centery - h / 2, w, h, min(w, h) / 2, fill,
                   1.6, edge, lit)  # fmt: skip
        nudge = 3.0 * lit * d  # the chevron leans the way it points
        _chevron(
            canvas, v, (rect.centerx + nudge, rect.centery), d, C.lerp(C.TEXT_DIM, C.WHITE, lit)
        )

    def _close_button(self, canvas, v: View, rect: pg.Rect) -> None:
        lit, press = self.fx.lit.get("close", 0.0), self.fx.press_k("close", self._clock)
        grow = 1.0 + 0.08 * lit - 0.1 * press
        w, h = rect.w * grow, rect.h * grow
        fill = C.lerp(C.PANEL, C.PANEL_HOT, lit)
        edge = C.lerp(C.PANEL_EDGE, C.CYAN, lit)
        blit_rrect(
            canvas, v, rect.centerx - w / 2, rect.centery - h / 2, w, h, 8, fill, 1.4, edge, lit
        )
        _cross(canvas, v, rect.center, C.lerp(C.TEXT_DIM, C.WHITE, lit))
