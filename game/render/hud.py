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
    pocketed: set[int],
    feel_key: str,
    muted: bool,
    moving: bool,
    sprites: BallSprites,
) -> None:
    blit_rrect(canvas, v, PANEL_X, PANEL_Y, PANEL_W, PANEL_H, 14, C.PANEL, edge=5)
    x, y = PANEL_X + 16, PANEL_Y + 14

    text(canvas, v, t("app.title"), 20, C.ACCENT, (x, y), bold=True)
    y += 40

    text(canvas, v, t("hud.shots"), 13, C.TEXT_DIM, (x, y))
    text(canvas, v, str(shots), 38, C.TEXT, (x, y + 14), bold=True)
    y += 66

    text(canvas, v, t("hud.balls_left"), 13, C.TEXT_DIM, (x, y))
    text(canvas, v, str(15 - len(pocketed)), 38, C.TEXT, (x, y + 14), bold=True)
    y += 66

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

    keys = (
        "hud.key_restart",
        "hud.key_mute",
        "hud.key_grid",
        "hud.key_feel",
        "hud.key_full",
        "hud.key_menu",
    )
    ky = PANEL_Y + PANEL_H - 14 - len(keys) * 17
    pg.draw.line(
        canvas,
        C.PANEL_EDGE,
        v.ipt((x, ky - 8)),
        v.ipt((PANEL_X + PANEL_W - 16, ky - 8)),
        max(1, v.i(1)),
    )
    for i, k in enumerate(keys):
        text(canvas, v, t(k), 12, C.TEXT_DIM, (x, ky + i * 17))
