"""What the player sees of achievements: the little cup, and the card that slides in when one is
earned. The list itself is a panel (scenes/achievements.py) built on these.

`trophy` draws the cup as neon line art, smooth at the real resolution (made once per size and
colour, then pasted). `Toasts` keeps the queue of cards: one slides up into the bottom-left
corner, stays, slides away, and the next one follows. It never takes a click or a key, so a shot
is never held up by it. No game logic here: the app tells it which achievement to show.
"""

from __future__ import annotations

import math
from collections.abc import Callable

import pygame as pg

from game.config import LOGICAL_SIZE
from game.i18n import t
from game.render import hud
from game.render import palette as C
from game.render.draw import _trim, blit_rrect
from game.render.glow import lit
from game.render.view import View

TROPHY_SS = 8  # the cup is drawn this many times bigger than the screen, then shrunk
_trophies: dict[tuple, tuple[pg.Surface, int]] = {}

# the card
CARD_W, CARD_H = 296, 64  # (narrow: the hint line under the table starts to its right)
CARD_MARGIN = 24  # from the left and bottom edges of the canvas (logical px)
SLIDE_IN_S, HOLD_S, SLIDE_OUT_S = 0.38, 3.6, 0.3
GAP_S = 0.25  # a pause between two cards in a row
SLIDE_PX = CARD_H + CARD_MARGIN + 8  # it comes up from below the edge: this far (logical px)


def _bezier(p0, p1, p2, n: int = 14) -> list[tuple[float, float]]:
    out = []
    for i in range(n + 1):
        u = i / n
        a, b, c = (1 - u) ** 2, 2 * u * (1 - u), u**2
        out.append((a * p0[0] + b * p1[0] + c * p2[0], a * p0[1] + b * p1[1] + c * p2[1]))
    return out


def _cup_parts() -> tuple[list, list, list]:
    """The cup in a box 1 wide, centred on (0, 0): (the bowl outline, the two handles, the foot).
    Each is a list of points (or of lists of points)."""
    right = _bezier((0.30, -0.40), (0.34, -0.02), (0.09, 0.06))
    left = [(-x, y) for x, y in reversed(right)]
    bowl = left + right + [left[0]]  # the rim closes it
    handle_r = [(0.31 + 0.19 * math.sin(a), -0.31 + 0.2 * (1 - math.cos(a)) * 1.1)
                for a in (i * math.pi / 14 for i in range(15))]  # fmt: skip
    handles = [handle_r, [(-x, y) for x, y in handle_r]]
    foot = [[(0.0, 0.06), (0.0, 0.27)], [(-0.2, 0.36), (0.2, 0.36)], [(-0.12, 0.27), (0.12, 0.27)]]
    return bowl, handles, foot


def trophy_sprite(v: View, size: float, color, filled: bool, glow: float):
    """(premultiplied sprite, pad in logical px) of the cup `size` tall, centred in it."""
    glow = round(glow * 8) / 8
    key = (round(v.s, 4), size, color, filled, glow)
    if key not in _trophies:
        _trim(_trophies, 120)
        pad = math.ceil(7 * glow * C.LOOK.reach) + 2 if glow > 0 else 2
        side = v.i(size * 1.3 + 2 * pad)
        bv = View(v.s * TROPHY_SS)
        big = pg.Surface((side * TROPHY_SS, side * TROPHY_SS), pg.SRCALPHA)
        c = side * TROPHY_SS / 2
        k = bv.s * size  # one unit of the cup, in big pixels

        def pts(line):
            return [(c + x * k, c + y * k) for x, y in line]

        bowl, handles, foot = _cup_parts()
        width = max(2, round(0.075 * k))
        if filled:  # a dim body, so a cup that is lit reads as solid
            pg.draw.polygon(big, (*color, 70), pts(bowl))
        for line in (bowl, *handles, *foot):
            p = pts(line)
            pg.draw.lines(big, color, False, p, width)
            for q in (p[0], p[-1]):  # round ends
                pg.draw.circle(big, color, q, width / 2)
        core = big.premul_alpha()
        out = lit(core, bv.n(pad) * 0.6, 1.4 * glow * C.LOOK.glow) if glow > 0 else core
        _trophies[key] = (pg.transform.smoothscale(out, (side, side)), pad)
    return _trophies[key]


def trophy(canvas: pg.Surface, v: View, centre: tuple[float, float], size: float, color,
           filled: bool = True, glow: float = 0.0) -> None:  # fmt: skip
    """The cup, `size` tall (logical px), centred on `centre`."""
    spr, _ = trophy_sprite(v, size, color, filled, glow)
    cx, cy = v.pt(centre)
    canvas.blit(spr, (round(cx - spr.get_width() / 2), round(cy - spr.get_height() / 2)),
                special_flags=pg.BLEND_PREMULTIPLIED)  # fmt: skip


def group_colour(group: str):
    """The colour an achievement of this group is lit in (also the colour of its cup)."""
    return {"free": C.MAGENTA, "practice": C.CYAN, "duo": C.AMBER}.get(group, C.MAGENTA)


def toast_card(canvas: pg.Surface, v: View, x: float, y: float, name: str, color) -> None:
    """The card: a cup, "ACHIEVEMENT UNLOCKED" small over the name, on a solid dark ground."""
    blit_rrect(canvas, v, x, y, CARD_W, CARD_H, 10, C.PANEL, 1.6, color, 0.8)
    trophy(canvas, v, (x + 34, y + CARD_H / 2), 34, color, True, 0.6)
    hud.text(canvas, v, t("ach.unlocked"), 11, C.CYAN, (x + 66, y + 14), bold=True, track=1.6)
    hud.text(canvas, v, name, 19, C.WHITE, (x + 66, y + 33), bold=True)


class Toasts:
    """The queue of cards. `push(id, name_key, group)` adds one; `update(dt)` moves time on;
    `draw(canvas, v)` paints the one that is up. `on_start(id)` is called when a card begins to
    show (the app plays its sound then, so each of a row of cards is heard)."""

    def __init__(self, on_start: Callable[[str], object] | None = None) -> None:
        self._queue: list[tuple[str, str]] = []  # (achievement id, group)
        self._now: tuple[str, str] | None = None
        self._age = 0.0
        self._gap = 0.0
        self._on_start = on_start

    @property
    def active(self) -> bool:
        return self._now is not None or bool(self._queue)

    @property
    def showing(self) -> str | None:
        """The id of the card on screen now (None between cards)."""
        return self._now[0] if self._now else None

    def push(self, ach_id: str, group: str) -> None:
        self._queue.append((ach_id, group))

    def clear(self) -> None:
        self._queue.clear()
        self._now = None

    def update(self, dt: float) -> None:
        if self._now is None:
            self._gap = max(0.0, self._gap - dt)
            if self._queue and self._gap <= 0.0:
                self._now, self._age = self._queue.pop(0), 0.0
                if self._on_start is not None:
                    self._on_start(self._now[0])
            return
        self._age += dt
        if self._age >= SLIDE_IN_S + HOLD_S + SLIDE_OUT_S:
            self._now, self._gap = None, GAP_S

    def offset(self) -> float:
        """How far the card still has to rise (logical px, 0 = at rest) while it slides."""
        a = self._age
        if a < SLIDE_IN_S:
            return SLIDE_PX * (1 - a / SLIDE_IN_S) ** 3
        out = a - SLIDE_IN_S - HOLD_S
        return SLIDE_PX * (out / SLIDE_OUT_S) ** 2 if out > 0 else 0.0

    def draw(self, canvas: pg.Surface, v: View) -> None:
        if self._now is None:
            return
        ach_id, group = self._now
        y = LOGICAL_SIZE[1] - CARD_MARGIN - CARD_H + self.offset()
        toast_card(canvas, v, CARD_MARGIN, y, t(f"ach.{ach_id}"), group_colour(group))
