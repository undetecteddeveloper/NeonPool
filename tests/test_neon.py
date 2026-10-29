"""The moving lights: the rim runner, the ribbons of the menu, the rings of light, the glow text.
All time-driven: the same clock gives the same picture (a photo of a scene is repeatable)."""

import pygame as pg
import pytest

from game import config, i18n
from game.render import hud, rim, waves
from game.render import palette as C
from game.render.fx import KINDS, Fx
from game.render.layout import (
    FIELD_H,
    FIELD_W,
    FIELD_X,
    FIELD_Y,
    OUTER_H,
    OUTER_W,
    OUTER_X,
    OUTER_Y,
)
from game.render.table import FRAME_R
from game.render.view import View

V = View(1.0)


def _canvas(v: View = V) -> pg.Surface:
    surf = pg.Surface(v.size)
    surf.fill((0, 0, 0))
    return surf


def _bytes(surf: pg.Surface) -> bytes:
    return pg.image.tobytes(surf, "RGB")


# --- the rim runner -------------------------------------------------------------------------
def test_the_rim_path_is_closed_evenly_spaced_and_hugs_the_rim():
    path = rim.rim_path()
    assert len(path) > 600  # about 3000 px of rim, a point every 3 px
    gaps = [
        ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5
        for a, b in zip(path, [*path[1:], path[0]], strict=True)
    ]
    assert max(gaps) < rim.STEP * 1.6  # no jump anywhere, also where the path closes
    for x, y in path:
        assert (
            OUTER_X - 1 <= x <= OUTER_X + OUTER_W + 1 and OUTER_Y - 1 <= y <= OUTER_Y + OUTER_H + 1
        )
        on_edge = min(x - OUTER_X, OUTER_X + OUTER_W - x, y - OUTER_Y, OUTER_Y + OUTER_H - y)
        assert on_edge < FRAME_R * 0.3 + 1.5  # on the rim (a corner arc cuts in by at most this)


def test_the_runner_is_repeatable_moves_and_leaves_the_cloth_alone():
    a, b = _canvas(), _canvas()
    rim.RimRunner(V).draw(a, 3.0)
    rim.RimRunner(V).draw(b, 3.0)
    assert _bytes(a) == _bytes(b)  # the same clock, the same picture
    later = _canvas()
    rim.RimRunner(V).draw(later, 9.0)
    assert _bytes(later) != _bytes(a)  # it moves
    assert any(a.get_at((x, OUTER_Y)) != (0, 0, 0, 255) for x in range(OUTER_X, OUTER_X + OUTER_W))
    centre = (FIELD_X + FIELD_W // 2, FIELD_Y + FIELD_H // 2)
    assert tuple(a.get_at(centre))[:3] == (0, 0, 0)  # nothing on the cloth


def test_the_runner_leaves_no_trail_when_it_moves_on():
    runner, fresh = rim.RimRunner(V), rim.RimRunner(V)
    first = _canvas()
    runner.draw(first, 1.0)
    second, expected = _canvas(), _canvas()
    runner.draw(second, 20.0)  # the same runner, after drawing elsewhere ...
    fresh.draw(expected, 20.0)  # ... must look like one that never drew there
    assert _bytes(second) == _bytes(expected)


def test_the_two_lights_run_half_a_lap_apart_in_two_colours():
    assert len(rim.LIGHTS) == 2
    (head_a, mid_a, _), (head_b, mid_b, _) = rim.LIGHTS
    assert mid_a == C.CYAN and mid_b == C.MAGENTA
    assert head_a != head_b


# --- the ribbons ---------------------------------------------------------------------------
RIBBON = waves.Ribbon(100, 100, 10, 3, 0.4, (C.CYAN, C.MAGENTA), 50)  # a lap of 100 px in 2 s


def test_a_ribbon_is_lit_around_its_line_and_dark_far_from_it():
    canvas = _canvas()
    waves.Waves(V, (RIBBON,)).draw(canvas, 0.0)
    near = max(sum(canvas.get_at((x, y))[:3]) for x in range(0, 300, 7) for y in range(90, 112))
    assert near > 200
    assert all(tuple(canvas.get_at((x, 300)))[:3] == (0, 0, 0) for x in range(0, 300, 11))


def test_a_ribbon_travels_and_comes_round_after_one_wavelength():
    w = waves.Waves(V, (RIBBON,))
    a, b, c = _canvas(), _canvas(), _canvas()
    w.draw(a, 0.0)
    w.draw(b, 0.5)  # a quarter of a lap: it has moved
    w.draw(c, 2.0)  # a whole lap (100 px at 50 px/s): it is back
    assert _bytes(a) != _bytes(b)
    assert _bytes(a) == _bytes(c)


@pytest.mark.parametrize("ribbons", [waves.MENU, waves.HELP])
def test_the_real_ribbons_fit_the_screen_at_two_sizes(ribbons):
    for v in (View(1.0), View(0.82)):
        canvas = _canvas(v)
        waves.Waves(v, ribbons).draw(canvas, 1.25)
        assert _bytes(canvas) != _bytes(_canvas(v))


# --- rings of light ------------------------------------------------------------------------
def test_a_ball_in_a_pocket_sends_a_pocket_wave_that_dies_down():
    fx = Fx()
    fx.add_drop(5, 0.3, 0.3, 0)
    assert [r.kind for r in fx.ripples] == ["pocket"]
    fx.update(config.POCKET_WAVE_S * 0.5)
    assert fx.ripples
    fx.update(config.POCKET_WAVE_S)
    assert not fx.ripples and not fx.drops


def test_each_kind_of_hit_has_its_own_colour_and_lasts_its_own_time():
    colours = {kind: spec[0] for kind, spec in KINDS.items()}
    assert len(set(colours.values())) == 3
    assert KINDS["pocket"][2] > KINDS["ball"][2]  # the pocket wave lingers longer


def test_ripples_are_capped_and_drawn_where_the_hit_was():
    fx = Fx()
    for _ in range(config.MAX_RIPPLES + 6):
        fx.add_ripple(1.0, 0.6, "ball")
    assert len(fx.ripples) == config.MAX_RIPPLES
    fx.clear()
    fx.add_ripple(1.0, 0.6, "ball")
    fx.update(0.1)
    canvas = _canvas()
    sprites = type("S", (), {"size": 10})()
    fx.draw(canvas, V, sprites)
    from game.render.layout import to_px

    cx, cy = to_px(1.0, 0.6)
    lit = [
        (x, y)
        for x in range(int(cx) - 60, int(cx) + 60)
        for y in range(int(cy) - 60, int(cy) + 60)
        if sum(canvas.get_at((x, y))[:3]) > 90
    ]
    assert lit
    assert all(abs(x - cx) < 60 and abs(y - cy) < 60 for x, y in lit)
    empty = _canvas()
    Fx().draw(empty, V, sprites)
    assert _bytes(empty) == _bytes(_canvas())  # no ripples, no light


# --- the glow text ------------------------------------------------------------------------
@pytest.fixture
def vi():
    i18n.set_lang("vi")
    yield
    i18n.set_lang("vi")


def test_glow_text_gives_light_round_the_letters_and_breathes(vi):
    pg.font.init()
    plain, bright, dim = _canvas(), _canvas(), _canvas()
    centre = (640, 150)
    hud.glow_text(plain, V, "NeonPool", 76, C.WHITE, C.CYAN, centre, strength=0.0)
    hud.glow_text(bright, V, "NeonPool", 76, C.WHITE, C.CYAN, centre, strength=1.1)
    hud.glow_text(dim, V, "NeonPool", 76, C.WHITE, C.CYAN, centre, strength=0.7)

    def light(surf: pg.Surface) -> int:
        return sum(
            sum(surf.get_at((x, y))[:3]) for x in range(440, 840, 3) for y in range(60, 240, 3)
        )

    assert light(bright) > light(dim) > light(plain)  # the halo swells and fades
