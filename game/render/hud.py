"""Text and the side panel. All words come from i18n; digits are drawn as-is."""

from __future__ import annotations

from functools import cache

import pygame as pg

from game.config import FEEL_ORDER, FEEL_SETS
from game.i18n import t
from game.render import fonts
from game.render import palette as C
from game.render.draw import BallSprites
from game.render.layout import PANEL_H, PANEL_W, PANEL_X, PANEL_Y

MINI = 20  # side of a small ball in the "balls left" grid


@cache
def _text(text: str, size: int, bold: bool, color: tuple[int, int, int]) -> pg.Surface:
    return fonts.get(size, bold).render(text, True, color)


def text(
    canvas: pg.Surface,
    s: str,
    size: int,
    color: tuple[int, int, int] = C.TEXT,
    pos: tuple[int, int] = (0, 0),
    *,
    bold: bool = False,
    center: bool = False,
) -> pg.Rect:
    surf = _text(s, size, bold, color)
    rect = surf.get_rect(center=pos) if center else surf.get_rect(topleft=pos)
    canvas.blit(surf, rect)
    return rect


def text_outlined(
    canvas: pg.Surface,
    s: str,
    size: int,
    color: tuple[int, int, int],
    center: tuple[int, int],
    outline: int = 4,
) -> None:
    """Big title text with the thick cartoon outline."""
    dark = _text(s, size, True, C.OUTLINE)
    for dx in range(-outline, outline + 1, 2):
        for dy in range(-outline, outline + 1, 2):
            canvas.blit(dark, dark.get_rect(center=(center[0] + dx, center[1] + dy)))
    text(canvas, s, size, color, center, bold=True, center=True)


_mini_cache: dict[tuple[int, bool], pg.Surface] = {}


def _mini_ball(sprites: BallSprites, number: int, gone: bool) -> pg.Surface:
    key = (number, gone)
    if key not in _mini_cache:
        surf = pg.transform.smoothscale(sprites.get(number), (MINI, MINI))
        if gone:
            surf.set_alpha(55)
        _mini_cache[key] = surf
    return _mini_cache[key]


def draw_panel(
    canvas: pg.Surface,
    *,
    shots: int,
    pocketed: set[int],
    feel_key: str,
    muted: bool,
    moving: bool,
    sprites: BallSprites,
) -> None:
    rect = pg.Rect(PANEL_X, PANEL_Y, PANEL_W, PANEL_H)
    pg.draw.rect(canvas, C.OUTLINE, rect.inflate(10, 10), border_radius=18)
    pg.draw.rect(canvas, C.PANEL, rect, border_radius=14)
    x, y = rect.x + 16, rect.y + 14

    text(canvas, t("app.title"), 20, C.ACCENT, (x, y), bold=True)
    y += 40

    text(canvas, t("hud.shots"), 13, C.TEXT_DIM, (x, y))
    text(canvas, str(shots), 38, C.TEXT, (x, y + 14), bold=True)
    y += 66

    left = 15 - len(pocketed)
    text(canvas, t("hud.balls_left"), 13, C.TEXT_DIM, (x, y))
    text(canvas, str(left), 38, C.TEXT, (x, y + 14), bold=True)
    y += 66

    for i, number in enumerate(range(1, 16)):  # 5 per row
        bx = x + (i % 5) * (MINI + 8)
        by = y + (i // 5) * (MINI + 6)
        canvas.blit(_mini_ball(sprites, number, number in pocketed), (bx, by))
    y += 3 * (MINI + 6) + 8

    text(canvas, t("hud.feel"), 13, C.TEXT_DIM, (x, y))
    name = t(FEEL_SETS[feel_key].name_key)
    text(canvas, name, 20, C.ACCENT, (x, y + 16), bold=True)
    for i, key in enumerate(FEEL_ORDER):  # three dots, the active one lit
        cx = x + PANEL_W - 32 - (len(FEEL_ORDER) - 1 - i) * 16
        pg.draw.circle(canvas, C.ACCENT if key == feel_key else C.PANEL_EDGE, (cx, y + 30), 5)
    y += 50

    text(canvas, t("hud.moving") if moving else t("hud.ready"), 14, C.TEXT, (x, y))
    text(canvas, t("hud.muted") if muted else t("hud.sound_on"), 13, C.TEXT_DIM, (x, y + 20))

    keys = (
        "hud.key_restart",
        "hud.key_mute",
        "hud.key_grid",
        "hud.key_feel",
        "hud.key_full",
        "hud.key_menu",
    )
    ky = rect.bottom - 14 - len(keys) * 17
    pg.draw.line(canvas, C.PANEL_EDGE, (x, ky - 8), (rect.right - 16, ky - 8), 1)
    for i, k in enumerate(keys):
        text(canvas, t(k), 12, C.TEXT_DIM, (x, ky + i * 17))
