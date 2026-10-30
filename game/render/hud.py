"""Text, arcade digits and the side panel at device resolution. Words come from i18n.

Text is placed by its CAPITAL LETTERS, not by the font's box: `pos` y is the top of the capitals
(centred text: the middle of the capitals), so Vietnamese marks above a letter never push a word
down, and a number in a badge sits in the middle of the badge.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from functools import cache

import pygame as pg

from game.i18n import t
from game.render import fonts, glow
from game.render import palette as C
from game.render.draw import (
    Aa,
    BallSprites,
    blit_add,
    blit_dot,
    blit_pm,
    blit_rrect,
    rrect_sprite,
    veil,
)
from game.render.layout import PANEL_H, PANEL_W, PANEL_X, PANEL_Y
from game.render.view import View

MINI = 22  # side of a small ball in the "balls left" grid (logical px)
PANEL_KEYS = (  # (key cap, what it does) at the bottom of the side panel (help page 6 shows it)
    ("keycap.r", "hud.key_restart"),
    ("keycap.m", "hud.key_mute"),
    ("keycap.h", "hud.key_help"),
    ("keycap.f11", "hud.key_full"),
    ("keycap.esc", "hud.key_menu"),
)
KEY_STEP = 21
KEYS_Y = PANEL_Y + PANEL_H - 18 - len(PANEL_KEYS) * KEY_STEP  # top of the first key row
BANNER_PAD = 16  # vertical padding of a notice (logical px), two lines make it 64 tall
FLASH_S = 0.6  # a number that just changed glows this long
ROLL_S = 0.32  # ... and rolls to its new value like a slot machine in this long
SHRINK_S = 0.3  # a ball that just went in shrinks in the list before it is struck off
POCKET_FLASH_S = 0.7  # a ball that just went in is struck off with a pulse this long


# --- text ------------------------------------------------------------------------------------
# A capital with two marks (an O with a hat and a tilde, ...) reaches above the font ascent:
# the font makes its surface TALLER AT THE TOP, so the baseline is not at a fixed row. Every
# placement here goes through the baseline, measured from the bottom (font descent).
def _baseline(surf: pg.Surface, font: pg.font.Font) -> int:
    """Row of the baseline inside a surface rendered by `font`."""
    return surf.get_height() + font.get_descent()


@cache
def _render(s: str, dev: int, name: str, color: tuple, track: int) -> tuple[pg.Surface, int]:
    """(surface, baseline row). With `track` the letters are spaced out, each on the baseline."""
    font = fonts.face(dev, name)
    if not track:
        surf = font.render(s, True, color)
        return surf, _baseline(surf, font)
    glyphs = [font.render(ch, True, color) for ch in s]
    base = max([_baseline(g, font) for g in glyphs] or [font.get_ascent()])
    w = sum(g.get_width() for g in glyphs) + track * max(0, len(glyphs) - 1)
    out = pg.Surface((max(1, w), base - font.get_descent()), pg.SRCALPHA)
    x = 0
    for g in glyphs:
        out.blit(g, (x, base - _baseline(g, font)))  # every letter on the same baseline
        x += g.get_width() + track
    return out, base


@cache
def _cap(dev: int, name: str) -> int:
    """Height of the capitals (the top of an H above the baseline) in device px."""
    return fonts.face(dev, name).metrics("H")[0][3]


@cache
def _ink_x(s: str, dev: int, name: str, track: int) -> tuple[int, int]:
    """(left, width) of the ink of `s` inside its rendered surface."""
    r = _render(s, dev, name, (255, 255, 255), track)[0].get_bounding_rect()
    return r.x, r.w


def text(
    canvas: pg.Surface,
    v: View,
    s: str,
    size: float,
    color: tuple[int, int, int] = C.TEXT,
    pos: tuple[float, float] = (0, 0),
    *,
    bold: bool = False,
    center: bool = False,
    align: str = "left",
    face: str | None = None,
    track: float = 0.0,
) -> pg.Rect:
    """Draw text. `size`, `pos` and `track` (extra space between letters) are logical.

    `pos` is (x, top of the capitals); `align` is "left", "right" or "center" on x. With
    `center` the capitals are centred on `pos` both ways (the ink, not the advance, on x).
    """
    name = face or ("bold" if bold else "body")
    dev = max(6, v.i(size))
    tr = v.i(track)
    surf, base = _render(s, dev, name, tuple(color), tr)
    cap = _cap(dev, name)
    x, y = v.pt(pos)
    if center:
        ink_left, ink_w = _ink_x(s, dev, name, tr)
        left = x - ink_left - ink_w / 2
        top = y + cap / 2 - base
    else:
        w = surf.get_width()
        left = x - w if align == "right" else x - w / 2 if align == "center" else x
        top = y + cap - base
    rect = surf.get_rect(topleft=(round(left), round(top)))
    canvas.blit(surf, rect)
    return rect


def text_width(v: View, s: str, size: float, bold: bool = False, face: str | None = None) -> float:
    """Width in LOGICAL units of `s` at logical `size`."""
    name = face or ("bold" if bold else "body")
    return _render(s, max(6, v.i(size)), name, C.TEXT, 0)[0].get_width() / v.s


def wrap(v: View, s: str, size: float, max_w: float, bold: bool = False) -> list[str]:
    """Break `s` into lines no wider than `max_w` logical units (a single long word stays whole)."""
    lines: list[str] = []
    line = ""
    for word in s.split():
        trial = f"{line} {word}".strip()
        if line and text_width(v, trial, size, bold) > max_w:
            lines.append(line)
            line = word
        else:
            line = trial
    return [*lines, line] if line else lines


def label(canvas: pg.Surface, v: View, s: str, pos, color=C.TEXT_DIM, size: float = 11, **kw):
    """A small spaced-out capital label (arcade style) above a value."""
    return text(canvas, v, s.upper(), size, color, pos, bold=True, track=1.6, **kw)


@cache
def _lit_text(
    s: str, dev: int, name: str, color: tuple, halo_color: tuple, radius: float, gain: float
) -> tuple[pg.Surface, pg.Surface, int]:
    """(halo, face, pad): the light round a text, the text itself, and the halo's margin."""
    font = fonts.face(dev, name)
    face_s = font.render(s, True, color)
    pad = math.ceil(radius * 2) + 2
    w, h = face_s.get_size()
    base = pg.Surface((w + 2 * pad, h + 2 * pad), pg.SRCALPHA)
    base.blit(font.render(s, True, halo_color), (pad, pad))
    return glow.halo(base.premul_alpha(), radius, gain), face_s, pad


def glow_text(
    canvas: pg.Surface,
    v: View,
    s: str,
    size: float,
    color: tuple[int, int, int],
    halo_color: tuple[int, int, int],
    pos: tuple[float, float],
    *,
    strength: float = 1.0,
    face: str = "bold",
    align: str = "center",
) -> None:
    """Text that gives light: the letters, and a soft halo of `halo_color` round them.

    `pos` is the middle of the capitals (align "center") or (left x, middle of the capitals)
    (align "left"). `strength` scales the halo; it is rounded to tenths so only a handful of
    halos are ever made (the title breathes and flickers through a few of them).
    """
    dev = max(6, v.i(size))
    radius = dev * 0.16 * C.LOOK.reach
    gain = round(1.1 * strength * C.LOOK.glow, 1)
    cap = _cap(dev, face)
    x, y = v.pt(pos)
    if gain > 0:
        light, face_s, pad = _lit_text(s, dev, face, tuple(color), tuple(halo_color), radius, gain)
    else:
        (face_s, _), pad, light = _render(s, dev, face, tuple(color), 0), 0, None
    top = y + cap / 2 - _baseline(face_s, fonts.face(dev, face))
    left = x - face_s.get_width() / 2 if align == "center" else x
    if light is not None:
        blit_add(canvas, light, (left - pad, top - pad))
    canvas.blit(face_s, (round(left), round(top)))


# --- arcade digits: seven lit segments, the unlit ones faintly visible -------------------------
SEGMENTS = {
    "0": "abcdef",
    "1": "bc",
    "2": "abged",
    "3": "abgcd",
    "4": "fgbc",
    "5": "afgcd",
    "6": "afgedc",
    "7": "abc",
    "8": "abcdefg",
    "9": "abcdfg",
    " ": "",
}
DIGIT_W = 0.56  # width of a digit cell / its height
DIGIT_GAP = 0.16  # space between digits / height
SLANT = 0.1  # the digits lean forward like on an arcade cabinet


def _segment_polys(x: float, y: float, h: float) -> dict[str, list[tuple[float, float]]]:
    """The seven segments of one digit cell (top-left x, y, height h) as hexagons."""
    w, th = h * DIGIT_W, h * 0.13
    g = th * 0.22  # small gap where two segments meet
    xl, xr, yt, ym, yb = x + th / 2, x + w - th / 2, y + th / 2, y + h / 2, y + h - th / 2

    def hor(x0, x1, yy):
        x0, x1 = x0 + g, x1 - g
        return [(x0, yy), (x0 + th / 2, yy - th / 2), (x1 - th / 2, yy - th / 2), (x1, yy),
                (x1 - th / 2, yy + th / 2), (x0 + th / 2, yy + th / 2)]  # fmt: skip

    def ver(xx, y0, y1):
        y0, y1 = y0 + g, y1 - g
        return [(xx, y0), (xx + th / 2, y0 + th / 2), (xx + th / 2, y1 - th / 2), (xx, y1),
                (xx - th / 2, y1 - th / 2), (xx - th / 2, y0 + th / 2)]  # fmt: skip

    polys = {
        "a": hor(xl, xr, yt),
        "g": hor(xl, xr, ym),
        "d": hor(xl, xr, yb),
        "f": ver(xl, yt, ym),
        "b": ver(xr, yt, ym),
        "e": ver(xl, ym, yb),
        "c": ver(xr, ym, yb),
    }
    lean = h * SLANT
    return {
        k: [(px + lean * (1 - (py - y) / h) - lean / 2, py) for px, py in pts]
        for k, pts in polys.items()
    }


def digits_width(n: int, height: float) -> float:
    return n * height * DIGIT_W + (n - 1) * height * DIGIT_GAP


_digit_cache: dict[tuple, tuple[pg.Surface, int]] = {}


def _digit_sprite(v: View, s: str, height: float, color, ghost, glow_k: float):
    key = (round(v.s, 4), s, height, color, ghost, round(glow_k, 2))
    if key not in _digit_cache:
        if len(_digit_cache) > 160:
            _digit_cache.clear()
        pad = math.ceil(height * 0.35)
        w = digits_width(len(s), height) + 2 * pad
        bv = v.framed().scaled(v.ss())
        lit = pg.Surface((bv.i(w), bv.i(height + 2 * pad)), pg.SRCALPHA)
        dim = lit.copy()
        for i, ch in enumerate(s):
            x = pad + i * height * (DIGIT_W + DIGIT_GAP)
            on = SEGMENTS.get(ch, "")
            for name, pts in _segment_polys(x, pad, height).items():
                target, col = (lit, color) if name in on else (dim, ghost)
                pg.draw.polygon(target, col, [bv.pt(p) for p in pts])
        lit_pm = lit.premul_alpha()
        out = dim.premul_alpha()
        if glow_k > 0:
            light = glow.halo(lit_pm, bv.n(height * 0.16), 1.5 * glow_k * C.LOOK.glow)
            out.blit(light, (0, 0), special_flags=pg.BLEND_RGBA_ADD)
        out.blit(lit_pm, (0, 0), special_flags=pg.BLEND_PREMULTIPLIED)
        _digit_cache[key] = (pg.transform.smoothscale(out, (v.i(w), v.i(height + 2 * pad))), pad)
    return _digit_cache[key]


def seg_number(
    canvas: pg.Surface,
    v: View,
    value: int,
    n: int,
    pos: tuple[float, float],
    height: float,
    color=C.CYAN,
    *,
    glow_k: float = 0.7,
    align: str = "left",
) -> None:
    """`value` in `n` arcade digits (blank, not 0, in front); `pos` is the top-left of the cells
    (or top-right with align "right")."""
    s = str(max(0, value))[-n:].rjust(n)
    spr, pad = _digit_sprite(v, s, height, tuple(color), C.scale(C.PANEL_EDGE, 0.55), glow_k)
    x = pos[0] - digits_width(n, height) if align == "right" else pos[0]
    blit_pm(canvas, spr, v.pt((x - pad, pos[1] - pad)))


# --- the side panel: an arcade score board --------------------------------------------------
@dataclass
class Scoreboard:
    """Remembers when each number last changed, so it can flash and roll (scene clock)."""

    values: dict[str, int] = field(default_factory=dict)
    previous: dict[str, int] = field(default_factory=dict)
    changed: dict[str, float] = field(default_factory=dict)

    def flash(self, name: str, value: int, clock: float) -> float:
        """1.0 just after `value` changed, fading to 0.0 over FLASH_S."""
        if self.values.get(name) != value:
            if name in self.values:
                self.changed[name] = clock
                self.previous[name] = self.values[name]
            self.values[name] = value
        age = clock - self.changed.get(name, -99.0)
        return max(0.0, 1.0 - age / FLASH_S) if age >= 0 else 0.0

    def roll(self, name: str, clock: float) -> tuple[int | None, float]:
        """(the old value, how far the roll to the new one has got 0..1); (None, 1) when still."""
        age = clock - self.changed.get(name, -99.0)
        if 0 <= age < ROLL_S and name in self.previous:
            return self.previous[name], 1 - (1 - age / ROLL_S) ** 3
        return None, 1.0


def rolling_number(canvas, v: View, board: Scoreboard, name: str, value: int, n: int, pos,
                   height: float, color, glow_k: float, clock: float) -> None:  # fmt: skip
    """An arcade counter that rolls: the old number slides up and out, the new one in from below."""
    old, k = board.roll(name, clock)
    if old is None:
        seg_number(canvas, v, value, n, pos, height, color, glow_k=glow_k)
        return
    pad = height * 0.35
    clip = v.rect(pos[0] - pad, pos[1] - 2, digits_width(n, height) + 2 * pad, height + 4)
    before = canvas.get_clip()
    canvas.set_clip(clip.clip(before) if before else clip)
    step = height * 1.25
    seg_number(canvas, v, old, n, (pos[0], pos[1] - k * step), height, color, glow_k=glow_k)
    seg_number(canvas, v, value, n, (pos[0], pos[1] + (1 - k) * step), height, color, glow_k=glow_k)
    canvas.set_clip(before)


_mini_cache: dict[tuple[float, int, bool], pg.Surface] = {}


def _mini_ball(sprites: BallSprites, v: View, number: int, gone: bool) -> pg.Surface:
    key = (round(v.s, 4), number, gone)
    if key not in _mini_cache:
        if len(_mini_cache) > 64:
            _mini_cache.clear()
        size = v.i(MINI)
        surf = pg.transform.smoothscale(sprites.core(number), (size, size))
        if gone:  # premultiplied: scale every channel together
            surf.fill((60, 60, 60, 60), special_flags=pg.BLEND_RGBA_MULT)
        _mini_cache[key] = surf
    return _mini_cache[key]


def _rule(canvas: pg.Surface, v: View, x0: float, x1: float, y: float) -> None:
    """A thin lit divider fading from cyan to pink."""
    layer = Aa(canvas, v, v.rect(x0 - 2, y - 3, x1 - x0 + 4, 6), ss=2)
    steps = 24
    for i in range(steps):
        a = x0 + (x1 - x0) * i / steps
        b = x0 + (x1 - x0) * (i + 1) / steps
        col = (*C.lerp(C.CYAN, C.MAGENTA, i / (steps - 1)), 200)
        pg.draw.line(layer.surf, col, layer.pt((a, y)), layer.pt((b, y)), max(1, round(layer.n(1))))
    layer.done()


def draw_panel(
    canvas: pg.Surface,
    v: View,
    *,
    shots: int,
    fouls: int,
    pocketed: set[int],
    group: str | None,
    eight_next: bool,
    muted: bool,
    moving: bool,
    sprites: BallSprites,
    clock: float = 0.0,
    board: Scoreboard | None = None,
    pocket_times: dict[int, float] | None = None,
) -> None:
    """The side panel: the logo, the score in arcade digits, your group, the balls still on the
    table (the ones that went in are struck off), what the table is doing, and the keys."""
    board = board or Scoreboard()
    pocket_times = pocket_times or {}
    blit_rrect(canvas, v, PANEL_X, PANEL_Y, PANEL_W, PANEL_H, 10, C.PANEL, 1.4, C.VIOLET, 0.5)
    x0, x1 = PANEL_X + 18, PANEL_X + PANEL_W - 18
    y = PANEL_Y + 30

    glow_text(
        canvas, v, t("app.title"), 30, C.WHITE, C.MAGENTA, (x0, y), face="display", align="left"
    )
    y += 26
    _rule(canvas, v, x0, x1, y)

    y += 18  # the score: two arcade counters
    col2 = x0 + 84
    label(canvas, v, t("hud.shots"), (x0, y))
    label(canvas, v, t("hud.fouls"), (col2, y))
    y += 14
    f_shots = board.flash("shots", shots, clock)
    f_fouls = board.flash("fouls", fouls, clock)
    shot_col = C.lerp(C.CYAN, C.WHITE, f_shots)
    foul_col = C.lerp(C.ERROR if fouls else C.CYAN, C.WHITE, f_fouls)
    rolling_number(canvas, v, board, "shots", shots, 3, (x0, y), 32, shot_col,
                   0.6 + 0.8 * f_shots, clock)  # fmt: skip
    rolling_number(canvas, v, board, "fouls", fouls, 2, (col2, y), 32, foul_col,
                   0.6 + 0.8 * f_fouls, clock)  # fmt: skip
    y += 32 + 24

    label(canvas, v, t("hud.group"), (x0, y))
    y += 16
    if eight_next:
        value, colour = t("hud.eight_next"), C.MAGENTA
    elif group:
        value, colour = t(f"group.{group}"), C.TEXT
    else:
        value, colour = t("group.open"), C.TEXT_DIM
    text(canvas, v, value, 17, colour, (x0, y), bold=True)
    y += 38

    label(canvas, v, t("hud.balls"), (x0, y))
    y += 16
    step_x, step_y = (x1 - x0 - MINI) / 4, MINI + 7
    for i, number in enumerate(range(1, 16)):  # 5 per row
        bx, by = x0 + (i % 5) * step_x, y + (i // 5) * step_y
        gone = number in pocketed
        age = clock - pocket_times.get(number, -99.0)
        if gone and 0 <= age < SHRINK_S:  # just went in: it shrinks first, still lit
            k = 1 - 0.4 * (1 - (1 - age / SHRINK_S) ** 2)
            spr = _mini_ball(sprites, v, number, False)
            size = max(2, round(spr.get_width() * k))
            small = pg.transform.smoothscale(spr, (size, size))
            c = v.pt((bx + MINI / 2, by + MINI / 2))
            blit_pm(canvas, small, (c[0] - size / 2, c[1] - size / 2))
            continue
        blit_pm(canvas, _mini_ball(sprites, v, number, gone), v.pt((bx, by)))
        if gone:
            _strike(canvas, v, (bx + MINI / 2, by + MINI / 2), age - SHRINK_S)
    y += 3 * step_y + 22

    pulse = 0.5 + 0.5 * math.sin(clock * (9.0 if moving else 3.0))
    state_col = C.AMBER if moving else C.OK
    blit_dot(canvas, v, (x0 + 4, y + 4), 3.5, C.lerp(state_col, C.WHITE, 0.3 * pulse), 0.6 + pulse)
    label(canvas, v, t("hud.moving") if moving else t("hud.ready"), (x0 + 16, y), state_col, 12)
    y += 20
    label(canvas, v, t("hud.muted") if muted else t("hud.sound_on"), (x0 + 16, y), size=10.5)

    ky = KEYS_Y
    pg.draw.line(canvas, C.PANEL_EDGE, v.ipt((x0, ky - 12)), v.ipt((x1, ky - 12)), max(1, v.i(1)))
    for i, (cap, what) in enumerate(PANEL_KEYS):
        row = ky + i * KEY_STEP
        keycap(canvas, v, t(cap), (x0, row), 34)
        text(canvas, v, t(what), 12, C.TEXT_DIM, (x0 + 44, row + 4))


def keycap(canvas: pg.Surface, v: View, s: str, pos: tuple[float, float], w: float) -> None:
    """A key drawn as a small lit cap; `pos` is its top-left corner (16 logical px tall)."""
    blit_rrect(canvas, v, pos[0], pos[1], w, 16, 4, C.PANEL_HOT, 1.0, C.CYAN_DIM)
    text(canvas, v, s, 10, C.CYAN, (pos[0] + w / 2, pos[1] + 8), bold=True, center=True)


def _strike(canvas: pg.Surface, v: View, c: tuple[float, float], age: float) -> None:
    """A ball that went in: struck off by a pink line; a ring of light while it is new."""
    r = MINI / 2
    layer = Aa(canvas, v, v.rect(c[0] - r - 8, c[1] - r - 8, 2 * r + 16, 2 * r + 16), ss=3)
    k = min(1.0, max(0.0, age / 0.18))  # the line sweeps across first
    a, b = (c[0] - r * 0.8, c[1] + r * 0.8), (c[0] + r * 0.8, c[1] - r * 0.8)
    end = (a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k)
    if k > 0:
        pg.draw.line(layer.surf, (*C.MAGENTA, 230), layer.pt(a), layer.pt(end), round(layer.n(1.8)))
    if 0 <= age < POCKET_FLASH_S:
        f = age / POCKET_FLASH_S
        pg.draw.circle(
            layer.surf,
            (*C.MAGENTA, round(220 * (1 - f))),
            layer.pt(c),
            layer.n(r + 6 * f),
            max(1, round(layer.n(1.6))),
        )
    layer.done()


# --- buttons, the table banner, the big arcade call-out and the result card ----------------------
# state -> (fill, edge colour, glow, text colour)
BUTTON_STATES = {
    "normal": (C.PANEL, C.PANEL_EDGE, 0.0, C.TEXT),
    "hover": (C.PANEL_HOT, C.CYAN, 0.7, C.WHITE),
    "primary": (C.PANEL_HOT, C.MAGENTA, 1.0, C.WHITE),
    "off": (C.BG, C.scale(C.PANEL_EDGE, 0.6), 0.0, C.scale(C.TEXT_DIM, 0.6)),
}


def button(
    canvas: pg.Surface,
    v: View,
    rect: pg.Rect,
    label_s: str,
    state: str = "normal",
    size: float = 18,
) -> None:
    """A solid arcade button; the chosen one is lit and carries a small arrow on its left."""
    fill, edge, glow_k, color = BUTTON_STATES[state]
    blit_rrect(canvas, v, rect.x, rect.y, rect.w, rect.h, 6, fill, 1.6, edge, glow_k)
    if state in ("primary", "hover"):
        arrow(canvas, v, (rect.x + 18, rect.centery), edge)
    text(canvas, v, label_s, size, color, rect.center, bold=True, center=True)


def arrow(canvas: pg.Surface, v: View, c: tuple[float, float], color, size: float = 6) -> None:
    """A small lit triangle pointing right, centred on `c`."""
    layer = Aa(canvas, v, v.rect(c[0] - size - 4, c[1] - size - 4, 2 * size + 8, 2 * size + 8), 3)
    pts = [
        (c[0] - size * 0.6, c[1] - size),
        (c[0] + size * 0.8, c[1]),
        (c[0] - size * 0.6, c[1] + size),
    ]
    pg.draw.polygon(layer.surf, color, [layer.pt(p) for p in pts])
    layer.done()


def banner(
    canvas: pg.Surface,
    v: View,
    lines: list[tuple[str, tuple[int, int, int]]],
    top_centre: tuple[float, float],
) -> None:
    """A short notice (solid pill, one or two lines) hanging from `top_centre`.

    The edge is lit in the colour of the first line (red for a foul). It sits OUTSIDE the table,
    below it: on the cloth it would hide balls rolling near a cushion.
    """
    if not lines:
        return
    size, step = 16, 24
    w = max(text_width(v, s, size, True) for s, _ in lines) + 44
    x, y = top_centre[0] - w / 2, top_centre[1]
    edge = lines[0][1] if lines[0][1] != C.TEXT else C.CYAN_DIM
    blit_rrect(canvas, v, x, y, w, BANNER_PAD + step * len(lines), 8, C.PANEL, 1.5, edge, 0.7)
    for i, (s, color) in enumerate(lines):
        pos = (top_centre[0], y + BANNER_PAD / 2 + step * (i + 0.5))
        text(canvas, v, s, size, color, pos, bold=True, center=True)


CALLOUT_IN_S = 0.14  # the big word grows in ...
CALLOUT_HOLD_S = 0.75  # ... stays ...
CALLOUT_OUT_S = 0.25  # ... and shrinks away towards the notice under the table
CALLOUT_S = CALLOUT_IN_S + CALLOUT_HOLD_S + CALLOUT_OUT_S


def draw_callout(
    canvas: pg.Surface,
    v: View,
    s: str,
    color: tuple[int, int, int],
    age: float,
    centre: tuple[float, float],
    home: tuple[float, float],
) -> None:
    """An arcade call-out ("FOUL!", "STRIPES!"): a big lit word that pops at `centre`, holds, then
    shrinks and slides to `home` (where the notice hangs) and goes out."""
    if not 0 <= age < CALLOUT_S:
        return
    if age < CALLOUT_IN_S:
        k = age / CALLOUT_IN_S
        scale_k, alpha, pos = 0.6 + 0.55 * k - 0.15 * k * k, k, centre
    elif age < CALLOUT_IN_S + CALLOUT_HOLD_S:
        scale_k, alpha, pos = 1.0, 1.0, centre
    else:
        k = (age - CALLOUT_IN_S - CALLOUT_HOLD_S) / CALLOUT_OUT_S
        e = k * k
        scale_k, alpha = 1.0 - 0.7 * e, 1.0 - k
        pos = (centre[0] + (home[0] - centre[0]) * e, centre[1] + (home[1] - centre[1]) * e)
    size = round(56 * scale_k)
    if size < 8:
        return
    bright = C.scale(color, alpha)
    glow_text(
        canvas,
        v,
        s,
        size,
        C.lerp(C.BG, C.WHITE, alpha),
        bright,
        pos,
        strength=1.6 * alpha,
        face="heavy",
    )


RESULT_CARD = pg.Rect(334, 163, 400, 388)  # centred on the table (logical px)
RESULT_BUTTONS = {
    "new": pg.Rect(RESULT_CARD.x + 28, RESULT_CARD.y + 314, 164, 46),
    "menu": pg.Rect(RESULT_CARD.right - 192, RESULT_CARD.y + 314, 164, 46),
}
RESULT_SCORE_Y, RESULT_SCORE_H = 140, 44  # the score line under the title (and the reason)
RESULT_ROWS_Y, RESULT_ROW_STEP = 218, 46  # shots and fouls under the hairline below it
RESULT_IN_S = 0.3  # the card grows in
RESULT_DIM_ALPHA = 185  # how dark the table behind the card goes


def draw_result_frame(
    canvas: pg.Surface, v: View, *, won: bool, reason: str | None, row_names: list[str]
) -> None:
    """The card's parts that never move: frame, title, why, the labels and the hairline."""
    c = RESULT_CARD
    mood = C.OK if won else C.ERROR
    blit_rrect(canvas, v, c.x, c.y, c.w, c.h, 10, C.PANEL, 1.8, mood, 1.0)
    title = t("result.won") if won else t("result.lost")
    glow_text(
        canvas, v, title, 46, C.WHITE, mood, (c.centerx, c.y + 54), strength=1.3, face="display"
    )
    if reason:
        for i, line in enumerate(wrap(v, reason, 14, c.w - 60)[:2]):
            text(canvas, v, line, 14, C.TEXT_DIM, (c.centerx, c.y + 98 + i * 19), center=True)
    top = c.y + RESULT_SCORE_Y
    label(canvas, v, t("result.score"), (c.x + 44, top + RESULT_SCORE_H / 2 - 5), C.TEXT, 14)
    blit_rrect(canvas, v, c.x + 44, top + RESULT_SCORE_H + 18, c.w - 88, 1.5, 0.75, C.PANEL_EDGE, 0)
    for i, name in enumerate(row_names):
        label(canvas, v, name, (c.x + 44, c.y + RESULT_ROWS_Y + i * RESULT_ROW_STEP + 12), size=12)


def draw_result_live(
    canvas: pg.Surface,
    v: View,
    *,
    score: int,
    values: list[int],
    fx: ButtonFx | None,
    clock: float,
    flashes: tuple[float, float, float] = (0.0, 0.0, 0.0),
) -> None:
    """The card's parts that move: the numbers (they count up: see game/tally.py; `flashes`,
    score first, are 1 just after a number stopped and fade to 0, making it glow whiter) and the
    two buttons."""
    c = RESULT_CARD
    fl = [round(f * 4) / 4 for f in flashes]  # in steps: a flash is a few sprites, not one a frame
    gold = C.lerp(C.SUN_TOP, C.WHITE, 0.6 * fl[0])
    seg_number(canvas, v, score, 4, (c.right - 44, c.y + RESULT_SCORE_Y), RESULT_SCORE_H, gold,
               glow_k=0.7 + 0.9 * fl[0], align="right")  # fmt: skip
    for i, value in enumerate(values):
        row = c.y + RESULT_ROWS_Y + i * RESULT_ROW_STEP
        seg_number(canvas, v, value, 3, (c.right - 44, row), 30,
                   C.lerp(C.CYAN, C.WHITE, 0.6 * fl[1 + i]), glow_k=0.7 + 0.9 * fl[1 + i],
                   align="right")  # fmt: skip
    fx = fx or ButtonFx(lit={"new": 1.0}, chosen="new")
    for key, rect in RESULT_BUTTONS.items():
        live_button(canvas, v, rect, t(f"result.{key}"), fx, key, clock, primary=key == "new")


_result_warm = [0.0]  # the view scale the card's sprites were last made for


def prewarm_result(v: View) -> None:
    """Draw the card once off screen (growing and whole, win and loss) so its sprites exist
    before the first game ends: the real game calls this while the menu idles."""
    if _result_warm[0] == v.s:
        return
    _result_warm[0] = v.s
    probe = pg.Surface(v.canvas)
    for won in (True, False):
        for age in (RESULT_IN_S / 2, 1.0):
            rows = [("", 0), ("", 0)]
            draw_result(probe, v, won=won, reason=None, score=0, rows=rows, hover=None, age=age)


def draw_result(
    canvas: pg.Surface,
    v: View,
    *,
    won: bool,
    reason: str | None,
    score: int,
    rows: list[tuple[str, int]],
    hover: str | None,
    age: float = 1.0,
    fx: ButtonFx | None = None,
    clock: float = 0.0,
    flashes: tuple[float, float, float] = (0.0, 0.0, 0.0),
) -> None:
    """The end-of-game card: dims the table, then the frame growing in, then the whole card.
    (PlayScene pastes a baked copy of the table and the card's unmoving parts once it has settled,
    and only calls `draw_result_live` after that.)"""
    canvas.blit(veil(canvas.get_size(), RESULT_DIM_ALPHA), (0, 0))
    c = RESULT_CARD
    k = min(1.0, max(0.0, age / RESULT_IN_S))
    if k < 1.0:  # growing in: just the lit frame, getting bigger
        # ONE full-size sprite, shrunk a little each frame (never enlarged): a new sprite for
        # every size meant 20-50 ms a frame while the card opened
        e = 1 - (1 - k) ** 3
        spr, _ = rrect_sprite(v, c.w, c.h, 10, C.PANEL, 1.8, C.OK if won else C.ERROR, 1.0)
        f = 0.7 + 0.3 * e
        small = pg.transform.smoothscale(
            spr, (max(1, round(spr.get_width() * f)), max(1, round(spr.get_height() * f)))
        )
        cx, cy = v.pt((c.centerx, c.centery))
        blit_pm(canvas, small, (cx - small.get_width() / 2, cy - small.get_height() / 2))
        return
    draw_result_frame(canvas, v, won=won, reason=reason, row_names=[n for n, _ in rows])
    draw_result_live(canvas, v, score=score, values=[x for _, x in rows], fx=fx, clock=clock,
                     flashes=flashes)  # fmt: skip


# --- buttons that move: lit, pressed, a light running round, a frame that glides ----------------
BTN_EASE_S = 0.12  # a button lights up / goes out in this long
PRESS_S = 0.18  # a pressed button dips and flashes this long
SWEEP_S = 0.45  # a light runs once round a button that has just been chosen
GLIDE_RATE = 16.0  # the highlight frame catches up with the chosen button this fast (1/s)


@dataclass
class ButtonFx:
    """How a group of buttons moves: how lit each one is, when it was pressed, where the
    highlight frame is on its way to the chosen one. Driven by the scene's clock."""

    lit: dict = field(default_factory=dict)
    pressed: dict = field(default_factory=dict)
    chosen_at: dict = field(default_factory=dict)
    chosen: object = None
    frame: list | None = None  # [x, y, w, h] of the gliding highlight (logical)

    def update(self, dt: float, chosen, rects: dict, clock: float) -> None:
        if chosen != self.chosen:
            self.chosen = chosen
            if chosen is not None:
                self.chosen_at[chosen] = clock
        for key in rects:
            cur = self.lit.get(key, 0.0)
            target = 1.0 if key == chosen else 0.0
            step = dt / BTN_EASE_S
            self.lit[key] = min(target, cur + step) if target > cur else max(target, cur - step)
        if chosen in rects:
            r = rects[chosen]
            goal = [r.x, r.y, r.w, r.h]
            if self.frame is None:
                self.frame = goal
            else:
                k = 1 - math.exp(-GLIDE_RATE * dt)
                self.frame = [a + (b - a) * k for a, b in zip(self.frame, goal, strict=True)]
        else:
            self.frame = None

    def press(self, key, clock: float) -> None:
        self.pressed[key] = clock

    def press_k(self, key, clock: float) -> float:
        """1 just after a press, 0 after PRESS_S."""
        age = clock - self.pressed.get(key, -99.0)
        return max(0.0, 1.0 - age / PRESS_S) if age >= 0 else 0.0


def _sweep(canvas: pg.Surface, v: View, rect: pg.Rect, t: float, colour) -> None:
    """A short bright light running once round the edge of `rect` (t: 0 -> 1)."""
    x, y, w, h = rect.x, rect.y, rect.w, rect.h
    per = 2 * (w + h)

    def at(d: float) -> tuple[float, float]:
        d %= per
        if d < w:
            return x + d, y
        if d < w + h:
            return x + w, y + d - w
        if d < 2 * w + h:
            return x + w - (d - w - h), y + h
        return x, y + h - (d - 2 * w - h)

    head = per * t + w * 0.5
    layer = Aa(canvas, v, v.rect(x - 6, y - 6, w + 12, h + 12), ss=2)
    fade = math.sin(math.pi * t)
    for i in range(18):  # the tail behind the head
        f = 1 - i / 18
        a, b = layer.pt(at(head - i * 5)), layer.pt(at(head - (i + 1) * 5))
        pg.draw.line(
            layer.surf, (*colour, round(230 * f * fade)), a, b, max(1, round(layer.n(2.2)))
        )
    layer.done()


def live_button(canvas: pg.Surface, v: View, rect: pg.Rect, label_s: str, fx: ButtonFx, key,
                clock: float, *, primary: bool = True, enabled: bool = True,
                frame_glides: bool = False, size: float = 18) -> None:  # fmt: skip
    """A button that answers the player: lit and a little bigger while chosen, an arrow slides in,
    a light runs round it once; pressed, it dips and flashes. With `frame_glides` the lit edge is
    left to the gliding frame (draw it with `glide_frame`)."""
    lit = fx.lit.get(key, 0.0) if enabled else 0.0
    press = fx.press_k(key, clock)
    accent = C.MAGENTA if primary else C.CYAN
    grow = 1.0 + 0.03 * lit - 0.05 * press
    w, h = round(rect.w * grow * 2) / 2, round(rect.h * grow * 2) / 2
    x, y = rect.centerx - w / 2, rect.centery - h / 2
    fill = C.lerp(C.lerp(C.PANEL, C.PANEL_HOT, lit), C.lerp(accent, C.WHITE, 0.3), 0.35 * press)
    if not enabled:
        fill = C.BG
    edge = C.lerp(C.PANEL_EDGE, accent, 0.0 if frame_glides else lit)
    if not enabled:
        edge = C.scale(C.PANEL_EDGE, 0.6)
    blit_rrect(canvas, v, x, y, w, h, 6, fill, 1.6, edge, 0.0 if frame_glides else lit)
    if lit > 0.02:  # the arrow slides in from the left as the button lights up
        arrow(canvas, v, (rect.x + 18 - 10 * (1 - lit), rect.centery), C.lerp(fill, accent, lit))
        age = clock - fx.chosen_at.get(key, -99.0)
        if 0 <= age < SWEEP_S and fx.chosen == key:
            _sweep(canvas, v, pg.Rect(round(x), round(y), round(w), round(h)), age / SWEEP_S,
                   C.lerp(accent, C.WHITE, 0.5))  # fmt: skip
    colour = C.lerp(C.TEXT, C.WHITE, lit) if enabled else C.scale(C.TEXT_DIM, 0.6)
    text(canvas, v, label_s, size, colour, rect.center, bold=True, center=True)


def glide_frame(canvas: pg.Surface, v: View, fx: ButtonFx, colour=C.MAGENTA) -> None:
    """The lit frame that slides from the button chosen before to the one chosen now."""
    if fx.frame is None:
        return
    x, y, w, h = fx.frame
    blit_rrect(canvas, v, x, y, w, h, 6, None, 1.8, colour, 1.0)
