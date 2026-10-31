"""The credits: pieces of text fall from the top edge one a second into the menu's night.

Each piece lands on the ribbons like a ball does: it dips, the ribbons splash and sink under its
weight, then it floats and the current carries it to the right and off the screen. They all land
at the same spot, and the current is just fast enough (CREDIT_FLOW * CREDIT_EVERY_S) that a piece
has moved clear of the spot before the next one lands, so none overlap. The menu scene owns this
and hides its own words while it runs.
"""

from __future__ import annotations

from dataclasses import dataclass

import pygame as pg

from game.config import (
    CREDIT_DAMP,
    CREDIT_EVERY_S,
    CREDIT_FIRST_S,
    CREDIT_FLOW,
    CREDIT_GRAVITY,
    CREDIT_LANE_X,
    CREDIT_MAX_W,
    CREDIT_PRESS,
    CREDIT_SINK,
    CREDIT_SPLASH,
    CREDIT_SPLASH_MAX,
    CREDIT_SPRING,
)
from game.i18n import t
from game.render import hud
from game.render import palette as C
from game.render.synth import Strands
from game.render.view import View

PAD = 22  # logical px round a piece's words, for the light round them
# a piece is a few lines, each (i18n key, kind)
PIECES = (
    (("app.title", "title"), ("app.subtitle", "sub")),
    (("credits.made_by", "label"), ("credits.person", "name")),
    (
        ("credits.tools", "label"),
        ("tool.python", "name"),
        ("tool.pygame", "name"),
        ("tool.numpy", "name"),
    ),
    (("credits.assistant", "label"), ("tool.claude", "name")),
    (("credits.fonts", "label"), ("tool.tilt", "name"), ("tool.chakra", "name")),
    (("credits.thanks", "name"),),
)
# kind: (size, font face, letter spacing, height of the line), all logical
KINDS = {
    "title": (46, "display", 0.0, 54),
    "sub": (11, "bold", 2.0, 18),
    "label": (12, "bold", 1.6, 20),
    "name": (24, "bold", 0.0, 34),
}
PRESS_SIGMA = 0.35  # a floating piece presses on the ribbons over this share of its width
LAND_SPEED = 600.0  # a landing at this speed (px/s) kicks the ribbons at CREDIT_SPLASH


def _width(v: View, s: str, kind: str) -> float:
    size, face, track, _ = KINDS[kind]
    return hud.text_width(v, s, size, face=face) + track * max(0, len(s) - 1)


def lines_of(key: str, kind: str, v: View) -> list[str]:
    """The words of one line, broken so that none is wider than a piece may be."""
    s = t(key)
    if kind in ("sub", "label"):
        s = s.upper()
    if _width(v, s, kind) <= CREDIT_MAX_W:
        return [s]
    out: list[str] = []
    for word in s.split():
        trial = f"{out[-1]} {word}" if out else word
        if out and _width(v, trial, kind) <= CREDIT_MAX_W:
            out[-1] = trial
        else:
            out.append(word)
    return out


def piece_width(v: View, piece) -> float:
    """How wide a piece is (logical px), in the language now set."""
    return max(_width(v, line, kind) for key, kind in piece for line in lines_of(key, kind, v))


def build_piece(v: View, piece) -> tuple[pg.Surface, float, float]:
    """(picture on black, width of the words, height of the words), logical px. The picture has
    PAD of room on every side and is added to the night, never blitted over it."""
    rows = [(line, kind) for key, kind in piece for line in lines_of(key, kind, v)]
    w = max(_width(v, line, kind) for line, kind in rows)
    h = sum(KINDS[kind][3] for _, kind in rows)
    surf = pg.Surface((v.i(w + 2 * PAD), v.i(h + 2 * PAD)))
    fv, cx, y = View(v.s), PAD + w / 2, float(PAD)
    for line, kind in rows:
        size, face, track, step = KINDS[kind]
        mid = y + step / 2
        if kind == "title":
            hud.glow_text(surf, fv, line, size, C.WHITE, C.MAGENTA, (cx, mid), face=face)
        elif kind == "name":
            hud.glow_text(
                surf, fv, line, size, C.WHITE, C.VIOLET, (cx, mid), strength=0.6, face=face
            )
        else:
            colour = C.CYAN if kind == "sub" else C.TEXT_DIM
            hud.text(surf, fv, line, size, colour, (cx, mid), bold=True, center=True, track=track)
        y += step
    return surf, w, h


@dataclass
class Piece:
    sprite: pg.Surface
    w: float  # of the words (logical px)
    h: float
    x: float  # the middle of the words
    y: float  # the bottom of the words
    vy: float = 0.0
    afloat: bool = False


class CreditsRoll:
    def __init__(self, v: View, strands: Strands) -> None:
        self.v, self.strands = v, strands
        self.pieces: list[Piece] = []
        self._sprites: list[tuple[pg.Surface, float, float]] = []
        self._t = 0.0
        self._next = 0  # which piece falls next
        self.running = False

    # --- running ---------------------------------------------------------------------------
    def prewarm(self) -> None:
        """Make every picture once, off screen, so the fonts and halos are cached before the
        credits are first opened (the real game does this behind its loading line)."""
        for piece in PIECES:
            build_piece(self.v, piece)

    def start(self) -> None:
        """Make the pictures (in the language now set) and let the first piece fall soon."""
        self._sprites = [build_piece(self.v, p) for p in PIECES]
        self.pieces, self._t, self._next, self.running = [], 0.0, 0, True

    def clear(self) -> None:
        self.pieces, self._next, self.running = [], len(PIECES), False

    @property
    def finished(self) -> bool:
        return self.running and self._next >= len(PIECES) and not self.pieces

    def _water(self, p: Piece) -> float:
        """Where the bottom of the words sits: on the ribbons under the piece."""
        s, third = self.strands, p.w / 3
        mean = sum(s.surface(p.x + k * third) for k in (-1, 0, 1)) / 3
        return mean + CREDIT_SINK

    def _spawn(self) -> None:
        sprite, w, h = self._sprites[self._next]
        self._next += 1
        top = self.v.logical_bounds()[1]
        y = top - 4.0
        drop = max(1.0, self.strands.base_y + CREDIT_SINK - y)
        fall_s = (2 * drop / CREDIT_GRAVITY) ** 0.5
        self.pieces.append(Piece(sprite, w, h, CREDIT_LANE_X - CREDIT_FLOW * fall_s, y))

    def update(self, dt: float, clock: float) -> None:
        if not self.running:
            return
        dt = min(dt, 0.05)
        self._t += dt
        if self._next < len(PIECES) and self._t >= CREDIT_FIRST_S + self._next * CREDIT_EVERY_S:
            self._spawn()
        right = self.v.logical_bounds()[2]
        for p in self.pieces:
            self._move(p, dt, clock)
        self.pieces = [p for p in self.pieces if p.x - p.w / 2 < right + PAD]

    def _move(self, p: Piece, dt: float, clock: float) -> None:
        p.x += CREDIT_FLOW * dt
        water = self._water(p)
        if not p.afloat:
            p.vy += CREDIT_GRAVITY * dt
            p.y += p.vy * dt
            if p.y >= water:
                p.afloat = True
                self._land(p, clock)
            return
        p.vy += (-CREDIT_SPRING * (p.y - water) - CREDIT_DAMP * p.vy) * dt
        p.y += p.vy * dt
        self.strands.press(p.x, p.w * PRESS_SIGMA, CREDIT_PRESS, dt)

    def _land(self, p: Piece, clock: float) -> None:
        """The piece hits the water: the ribbons splash along its width and a light runs off."""
        strength = min(CREDIT_SPLASH_MAX, CREDIT_SPLASH * p.vy / LAND_SPEED)
        for k in (-1, 0, 1):
            self.strands.splash(p.x + k * p.w / 3, strength / 1.5)
        self.strands.pulse(p.x, clock)

    # --- drawing -----------------------------------------------------------------------------
    def draw(self, canvas: pg.Surface) -> None:
        v = self.v
        for p in self.pieces:
            left, top = v.ipt((p.x - p.w / 2 - PAD, p.y - p.h - PAD))
            canvas.blit(p.sprite, (left, top), special_flags=pg.BLEND_RGB_ADD)
