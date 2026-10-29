"""Text and the side panel at device resolution. Words come from i18n; digits are as-is."""

from __future__ import annotations

from functools import cache

import pygame as pg

from game.config import FEEL_ORDER, FEEL_SETS
from game.i18n import t
from game.render import fonts
from game.render import palette as C
from game.render.draw import BallSprites, blit_pm, blit_rrect, shrink_pm
from game.render.layout import PANEL_H, PANEL_W, PANEL_X, PANEL_Y
from game.render.view import View

MINI = 20  # side of a small ball in the "balls left" grid (logical px)
PANEL_KEYS = (  # key list at the bottom of the side panel (the help screen photographs it)
    "hud.key_restart",
    "hud.key_mute",
    "hud.key_feel",
    "hud.key_help",
    "hud.key_full",
    "hud.key_menu",
)
KEY_STEP = 17
KEYS_Y = PANEL_Y + PANEL_H - 14 - len(PANEL_KEYS) * KEY_STEP  # top of the first key line
BANNER_PAD = 16  # vertical padding of a notice (logical px), two lines make it 64 tall


@cache
def _text(text: str, dev_size: int, bold: bool, color: tuple[int, int, int]) -> pg.Surface:
    return fonts.get(dev_size, bold).render(text, True, color)


def text(
    canvas: pg.Surface,
    v: View,
    s: str,
    size: int,
    color: tuple[int, int, int] = C.TEXT,
    pos: tuple[float, float] = (0, 0),
    *,
    bold: bool = False,
    center: bool = False,
) -> pg.Rect:
    """Draw text; `size` and `pos` are logical, the glyphs are rendered at the device size."""
    surf = _text(s, max(6, v.i(size)), bold, color)
    p = v.ipt(pos)
    rect = surf.get_rect(center=p) if center else surf.get_rect(topleft=p)
    canvas.blit(surf, rect)
    return rect


def text_width(v: View, s: str, size: int, bold: bool = False) -> float:
    """Width in LOGICAL units of `s` at logical `size`."""
    return _text(s, max(6, v.i(size)), bold, C.TEXT).get_width() / v.s


def wrap(v: View, s: str, size: int, max_w: float, bold: bool = False) -> list[str]:
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


def text_outlined(
    canvas: pg.Surface,
    v: View,
    s: str,
    size: int,
    color: tuple[int, int, int],
    center: tuple[float, float],
    outline: float = 4,
) -> None:
    """Big title text with the thick cartoon outline."""
    dark = _text(s, max(6, v.i(size)), True, C.OUTLINE)
    o = max(1, v.i(outline))
    cx, cy = v.ipt(center)
    for dx in range(-o, o + 1):
        for dy in range(-o, o + 1):
            if dx * dx + dy * dy <= o * o + 1:
                canvas.blit(dark, dark.get_rect(center=(cx + dx, cy + dy)))
    text(canvas, v, s, size, color, center, bold=True, center=True)


_mini_cache: dict[tuple[float, int, bool], pg.Surface] = {}


def _mini_ball(sprites: BallSprites, v: View, number: int, gone: bool) -> pg.Surface:
    key = (round(v.s, 4), number, gone)
    if key not in _mini_cache:
        if len(_mini_cache) > 64:
            _mini_cache.clear()
        size = v.i(MINI)
        surf = pg.transform.smoothscale(sprites.get(number), (size, size))
        if gone:  # premultiplied: scale every channel together
            surf.fill((55, 55, 55, 55), special_flags=pg.BLEND_RGBA_MULT)
        _mini_cache[key] = surf
    return _mini_cache[key]


def draw_panel(
    canvas: pg.Surface,
    v: View,
    *,
    shots: int,
    fouls: int,
    pocketed: set[int],
    group: str | None,
    eight_next: bool,
    feel_key: str,
    muted: bool,
    moving: bool,
    sprites: BallSprites,
) -> None:
    """The side panel."""
    blit_rrect(canvas, v, PANEL_X, PANEL_Y, PANEL_W, PANEL_H, 14, C.PANEL, edge=5)
    x, y = PANEL_X + 16, PANEL_Y + 14

    text(canvas, v, t("app.title"), 20, C.ACCENT, (x, y), bold=True)
    y += 40

    text(canvas, v, t("hud.shots"), 13, C.TEXT_DIM, (x, y))
    text(canvas, v, str(shots), 38, C.TEXT, (x, y + 14), bold=True)
    text(canvas, v, t("hud.fouls"), 13, C.TEXT_DIM, (x + 86, y))
    text(canvas, v, str(fouls), 38, C.ERROR if fouls else C.TEXT, (x + 86, y + 14), bold=True)
    y += 66

    text(canvas, v, t("hud.group"), 13, C.TEXT_DIM, (x, y))
    if eight_next:
        text(canvas, v, t("hud.eight_next"), 18, C.ACCENT, (x, y + 16), bold=True)
    else:
        label = t(f"group.{group}") if group else t("group.open")
        text(canvas, v, label, 18, C.TEXT if group else C.TEXT_DIM, (x, y + 16), bold=True)
    y += 46

    for i, number in enumerate(range(1, 16)):  # 5 per row
        bx = x + (i % 5) * (MINI + 8)
        by = y + (i // 5) * (MINI + 6)
        blit_pm(canvas, _mini_ball(sprites, v, number, number in pocketed), v.pt((bx, by)))
    y += 3 * (MINI + 6) + 8

    text(canvas, v, t("hud.feel"), 13, C.TEXT_DIM, (x, y))
    text(canvas, v, t(FEEL_SETS[feel_key].name_key), 20, C.ACCENT, (x, y + 16), bold=True)
    dots = pg.Surface((v.i(60), v.i(14)), pg.SRCALPHA)
    big = pg.Surface((dots.get_width() * 4, dots.get_height() * 4), pg.SRCALPHA)
    for i, key in enumerate(FEEL_ORDER):  # three dots, the active one lit
        cx = v.n(8 + i * 16) * 4
        pg.draw.circle(
            big,
            C.ACCENT if key == feel_key else C.PANEL_EDGE,
            (cx, big.get_height() / 2),
            v.n(5) * 4,
        )
    blit_pm(canvas, shrink_pm(big, dots.get_size()), v.pt((x + PANEL_W - 32 - 40, y + 23)))
    y += 50

    text(canvas, v, t("hud.moving") if moving else t("hud.ready"), 14, C.TEXT, (x, y))
    text(canvas, v, t("hud.muted") if muted else t("hud.sound_on"), 13, C.TEXT_DIM, (x, y + 20))
    ky = KEYS_Y
    pg.draw.line(
        canvas,
        C.PANEL_EDGE,
        v.ipt((x, ky - 8)),
        v.ipt((PANEL_X + PANEL_W - 16, ky - 8)),
        max(1, v.i(1)),
    )
    for i, k in enumerate(PANEL_KEYS):
        text(canvas, v, t(k), 12, C.TEXT_DIM, (x, ky + i * KEY_STEP))


# --- buttons, the table banner and the result card -----------------------------------------
def button(
    canvas: pg.Surface,
    v: View,
    rect: pg.Rect,
    label: str,
    fill: tuple[int, int, int],
    color: tuple[int, int, int],
    size: int = 18,
) -> None:
    blit_rrect(canvas, v, rect.x, rect.y, rect.w, rect.h, 12, fill, edge=4)
    text(canvas, v, label, size, color, rect.center, bold=True, center=True)


def banner(
    canvas: pg.Surface,
    v: View,
    lines: list[tuple[str, tuple[int, int, int]]],
    top_centre: tuple[float, float],
) -> None:
    """A short notice (dark pill, one or two lines) hanging from `top_centre`.

    It sits OUTSIDE the table, below it: on the cloth it would hide balls rolling near a cushion.
    """
    if not lines:
        return
    size, step = 16, 24
    w = max(text_width(v, s, size, True) for s, _ in lines) + 40
    x, y = top_centre[0] - w / 2, top_centre[1]
    blit_rrect(canvas, v, x, y, w, BANNER_PAD + step * len(lines), 12, C.PANEL, edge=4)
    for i, (s, color) in enumerate(lines):
        pos = (top_centre[0], y + BANNER_PAD / 2 + step * (i + 0.5))
        text(canvas, v, s, size, color, pos, bold=True, center=True)


RESULT_CARD = pg.Rect(334, 207, 400, 300)  # between the head spot and the rack (logical px)
RESULT_BUTTONS = {
    "new": pg.Rect(RESULT_CARD.x + 30, RESULT_CARD.y + 236, 160, 48),
    "menu": pg.Rect(RESULT_CARD.right - 190, RESULT_CARD.y + 236, 160, 48),
}
_dim_cache: dict[tuple[int, int], pg.Surface] = {}


def draw_result(
    canvas: pg.Surface,
    v: View,
    *,
    won: bool,
    reason: str | None,
    rows: list[tuple[str, str]],
    hover: str | None,
) -> None:
    """The end-of-game card: dims the table, title, why, the numbers and two buttons."""
    size = canvas.get_size()
    if size not in _dim_cache:
        _dim_cache.clear()
        dim = pg.Surface(size, pg.SRCALPHA)
        dim.fill((6, 8, 14, 170))
        _dim_cache[size] = dim
    canvas.blit(_dim_cache[size], (0, 0))
    c = RESULT_CARD
    blit_rrect(canvas, v, c.x, c.y, c.w, c.h, 16, C.PANEL, edge=5)
    cx = c.centerx
    title = t("result.won") if won else t("result.lost")
    text(canvas, v, title, 36, C.OK if won else C.ERROR, (cx, c.y + 44), bold=True, center=True)
    if reason:
        text(canvas, v, reason, 15, C.TEXT_DIM, (cx, c.y + 82), center=True)
    for i, (label, value) in enumerate(rows):
        row = c.y + 112 + i * 26
        text(canvas, v, label, 15, C.TEXT_DIM, (c.x + 40, row + 2))
        text(
            canvas,
            v,
            value,
            18,
            C.TEXT,
            (c.right - 40 - text_width(v, value, 18, True), row),
            bold=True,
        )
    for key, rect in RESULT_BUTTONS.items():
        primary = key == "new"
        lit = hover == key
        fill = C.ACCENT if primary else C.PANEL_EDGE if lit else C.BG
        color = C.OUTLINE if primary else C.TEXT
        button(canvas, v, rect, t(f"result.{key}"), fill, color)
