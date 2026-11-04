"""The side panel looks the same however it is built: from scratch, again, or after a change.

The panel (Free play and Practice) has a part that never moves (frame, title, rule, the score
words, the key list); it may be painted once and pasted. These tests hold what the player sees:
a second draw is the same picture as the first, what lies behind the panel hardly shows through
it, and a change of language, window size or key list repaints it (a stale picture would show
the old words or the old size).

"Hardly": the glass fill is 253/255 opaque in its middle (shrinking the sprite rounds its alpha
down), so a background that changes shows through by up to 2 of 255 levels. The table behind the
panel stands still, so in the game the pasted part is byte for byte the painted one.
"""

import numpy as np
import pygame as pg
import pytest

from game import i18n
from game.render import hud
from game.render.draw import BallSprites
from game.render.layout import PANEL_H, PANEL_W, PANEL_X, PANEL_Y
from game.render.view import View

SIZES = ((1280, 720), (1050, 590))
INSET = 14  # logical px: inside this the panel is as solid as it gets (no corner, no edge glow)
SHOW_THROUGH = 2  # levels (of 255) of the background that may show through the glass fill


@pytest.fixture(autouse=True)
def _pygame():
    pg.init()
    yield
    i18n.set_lang("vi")
    pg.quit()


def noise(size: tuple[int, int], seed: int) -> np.ndarray:
    return np.random.default_rng(seed).integers(0, 255, size=(*size, 3), dtype=np.uint8)


def draw_free(canvas, v, sprites, keys=hud.PANEL_KEYS) -> None:
    hud.draw_panel(
        canvas,
        v,
        shots=7,
        fouls=2,
        pocketed={1, 2, 9},
        group="solid",
        eight_next=False,
        muted=False,
        moving=True,
        sprites=sprites,
        clock=3.3,
        spin=0.5,
        spin_lit=0.6,
        spin_on=True,
        keys=keys,
    )


def draw_practice(canvas, v, sprites, keys=hud.PANEL_KEYS) -> None:
    hud.draw_practice_panel(
        canvas,
        v,
        streak=5,
        lives=2,
        best=12,
        target=6,
        target_shown=True,
        pocketed={1, 2, 3},
        muted=False,
        moving=False,
        sprites=sprites,
        clock=1.5,
        spin=-0.5,
        spin_lit=0.3,
        spin_on=True,
        count=22,
        counting_down=False,
        keys=keys,
    )


PANELS = pytest.mark.parametrize("draw", [draw_free, draw_practice], ids=["free", "practice"])


def picture(size, draw, behind, *, v=None, sprites=None, lang="vi", **kw) -> bytes:
    i18n.set_lang(lang)
    v = v or View.for_window(size)
    sprites = sprites or BallSprites(v)
    canvas = pg.Surface(size)
    pg.surfarray.blit_array(canvas, behind)
    draw(canvas, v, sprites, **kw)
    return pg.image.tobytes(canvas, "RGB")


def inside(size, data: bytes) -> np.ndarray:
    """The part of a picture that lies well inside the panel (no corner, no glow past the edge)."""
    v = View.for_window(size)
    r = v.rect(PANEL_X + INSET, PANEL_Y + INSET, PANEL_W - 2 * INSET, PANEL_H - 2 * INSET)
    surf = pg.image.frombytes(data, size, "RGB")
    return pg.surfarray.array3d(surf.subsurface(r)).astype(int)


@PANELS
@pytest.mark.parametrize("size", SIZES)
@pytest.mark.parametrize("lang", ["vi", "en"])
def test_a_second_draw_is_the_same_picture(draw, size, lang):
    v = View.for_window(size)
    sprites = BallSprites(v)
    behind = noise(size, 1)
    first = picture(size, draw, behind, v=v, sprites=sprites, lang=lang)
    second = picture(size, draw, behind, v=v, sprites=sprites, lang=lang)
    assert first == second


@PANELS
@pytest.mark.parametrize("size", SIZES)
def test_what_is_behind_the_panel_hardly_shows_through(draw, size):
    v = View.for_window(size)
    sprites = BallSprites(v)
    a = picture(size, draw, noise(size, 1), v=v, sprites=sprites)
    b = picture(size, draw, noise(size, 2), v=v, sprites=sprites)  # a hit when there is a cache
    assert np.abs(inside(size, a) - inside(size, b)).max() <= SHOW_THROUGH
    assert a != b  # the edge of the panel and the table beside it do follow what is behind


@PANELS
def test_a_change_of_language_repaints_the_words(draw):
    size = SIZES[0]
    v = View.for_window(size)
    sprites = BallSprites(v)
    behind = noise(size, 3)
    vi1 = picture(size, draw, behind, v=v, sprites=sprites, lang="vi")
    en = picture(size, draw, behind, v=v, sprites=sprites, lang="en")
    vi2 = picture(size, draw, behind, v=v, sprites=sprites, lang="vi")
    assert vi1 != en
    assert vi1 == vi2


@PANELS
def test_a_change_of_window_size_repaints_the_panel(draw):
    big, small = SIZES
    behind_big, behind_small = noise(big, 4), noise(small, 4)
    first = picture(big, draw, behind_big)
    other = picture(small, draw, behind_small)
    again = picture(big, draw, behind_big)
    assert len(other) != len(first)
    assert first == again


@PANELS
def test_a_change_of_key_list_repaints_the_keys(draw):
    size = SIZES[0]
    v = View.for_window(size)
    sprites = BallSprites(v)
    behind = noise(size, 5)
    std1 = picture(size, draw, behind, v=v, sprites=sprites, keys=hud.PANEL_KEYS)
    net = picture(size, draw, behind, v=v, sprites=sprites, keys=hud.NET_PANEL_KEYS)
    std2 = picture(size, draw, behind, v=v, sprites=sprites, keys=hud.PANEL_KEYS)
    assert std1 != net
    assert std1 == std2
