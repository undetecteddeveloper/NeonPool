"""The moving lights: the rim runner, the living ribbons and the night of the menu, the rings
of light, the arcade digits and the glow text.
All time-driven: the same clock gives the same picture (a photo of a scene is repeatable)."""

import math

import numpy as np
import pygame as pg
import pytest

from game import config, i18n
from game.render import crt, hud, synth, table
from game.render import palette as C
from game.render.fx import KINDS, Fx
from game.render.layout import (
    OUTER_H,
    OUTER_W,
    OUTER_X,
    OUTER_Y,
)
from game.render.view import View

V = View(1.0)


def _canvas(v: View = V) -> pg.Surface:
    surf = pg.Surface(v.size)
    surf.fill((0, 0, 0))
    return surf


def _bytes(surf: pg.Surface) -> bytes:
    return pg.image.tobytes(surf, "RGB")


# --- the wave over the table when a ball drops ----------------------------------------------
def test_the_table_lines_form_one_closed_rim_and_six_cushions():
    paths = table.neon_paths()
    assert len(paths) == 7
    rim_path = paths[0]
    assert math.dist(rim_path[0], rim_path[-1]) < 1e-6  # closed
    gaps = [math.dist(a, b) for a, b in zip(rim_path, rim_path[1:], strict=False)]
    assert max(gaps) < table.RIM_STEP * 1.6  # evenly spaced, no jump
    for x, y in rim_path:
        assert OUTER_X - 1 <= x <= OUTER_X + OUTER_W + 1
        assert OUTER_Y - 1 <= y <= OUTER_Y + OUTER_H + 1


def test_a_dropped_ball_sends_a_wave_of_its_colour_over_the_table_that_dies_out():
    fx = Fx()
    fx.add_drop(11, 0.3, 0.3, 0)  # a stripe: the wave is the colour of its band
    assert len(fx.waves) == 1 and fx.waves[0].colour == C.BALL_COLORS[3]
    assert not fx.ripples  # no small ripple at the pocket any more: the big wave replaces it
    fx.update(config.TABLE_WAVE_S * 0.5)
    assert fx.waves and fx.waves[0].radius() > 300  # it has run a long way over the table
    fx.update(config.TABLE_WAVE_S)
    assert not fx.waves and not fx.drops


def test_the_wave_lights_the_table_and_nothing_outside_it():
    fx = Fx()
    fx.add_drop(5, 2.5, 1.2, 3)  # bottom-right corner pocket, orange
    fx.update(0.4)
    canvas = _canvas()
    fx.draw(canvas, V, type("S", (), {"size": 10})())
    lit = sum(
        1
        for x in range(0, 1280, 6)
        for y in range(0, 720, 6)
        if sum(canvas.get_at((x, y))[:3]) > 40
    )
    assert lit > 150  # a big ring of light
    box = pg.Rect(OUTER_X - 8, OUTER_Y - 8, OUTER_W + 16, OUTER_H + 16)
    outside = [(5, 5), (box.right + 20, box.centery), (box.centerx, box.bottom + 30)]
    assert all(tuple(canvas.get_at(p))[:3] == (0, 0, 0) for p in outside)


def test_a_harder_hit_shakes_the_screen_harder():
    soft, hard = Fx(), Fx()
    soft.shake(0.35)
    hard.shake(1.0)
    soft.update(0.02)
    hard.update(0.02)
    assert abs(hard.shake_offset()[1]) > abs(soft.shake_offset()[1])


# --- the living ribbons and the synthwave night -----------------------------------------------
def _strands() -> synth.Strands:
    return synth.Strands(0.0, 1280.0, 400.0)


def _run(st: synth.Strands, seconds: float) -> None:
    for _ in range(round(seconds * 60)):
        st.update(1 / 60)


def test_the_strands_move_on_their_own_and_the_same_time_gives_the_same_shape():
    a, b = _strands(), _strands()
    _run(a, 1.0)
    _run(b, 1.0)
    assert np.array_equal(a.y, b.y)  # no randomness
    start = _strands().y.copy()
    assert np.abs(a.y - start).max() > 2.0  # they breathe without any input


def test_the_strands_lean_towards_the_pointer():
    still, leaning = _strands(), _strands()
    leaning.point_to((300.0, 520.0))  # below the horizon, on the left
    _run(still, 1.5)
    _run(leaning, 1.5)
    near = np.abs(leaning.x - 300.0).argmin()
    far = np.abs(leaning.x - 1100.0).argmin()
    assert (leaning.y[:, near] - still.y[:, near]).mean() > 25  # pulled down towards it
    assert abs((leaning.y[:, far] - still.y[:, far]).mean()) < 5  # ... only there


def test_a_click_makes_a_splash_that_runs_out_and_dies_down():
    calm, hit = _strands(), _strands()
    hit.splash(640.0)
    _run(calm, 0.25)
    _run(hit, 0.25)
    diff = np.abs(hit.y - calm.y).mean(axis=0)
    centre = np.abs(hit.x - 640.0).argmin()
    assert diff[centre] > 3.0
    _run(calm, 4.0)
    _run(hit, 4.0)
    assert np.abs(hit.y - calm.y).max() < 1.0  # damped away after a few seconds


def test_a_pulse_of_light_runs_both_ways_along_the_strands():
    st = _strands()
    st.pulse(640.0, 0.0)
    st.vy[:] = 0.0  # leave out the kick: look only at the light of the pulse
    light = st.glow_at(0.5)
    peak_left = st.x[np.argmax(np.where(st.x < 640, light, 0))]
    peak_right = st.x[np.argmax(np.where(st.x > 640, light, 0))]
    gone = synth.PULSE_SPEED * 0.5
    assert abs((640 - peak_left) - gone) < 30 and abs((peak_right - 640) - gone) < 30
    assert st.glow_at(synth.PULSE_S + 0.1).max() < light.max()  # and it fades


def test_a_ball_landing_on_the_ribbon_leaves_it_alone():
    with_balls = synth.Synthwave(V, 405, floaters=True)
    without = synth.Synthwave(V, 405)
    landed = False
    for _ in range(12 * 60):
        with_balls.update(1 / 60)
        without.update(1 / 60)
        landed = landed or any(b[3] for b in with_balls.floaters.balls)
    assert landed
    assert np.array_equal(with_balls.strands.y, without.strands.y)  # no dip, no ripple


def test_the_balls_are_drawn_over_the_ribbons_so_that_nothing_dims_them():
    sw = synth.Synthwave(V, 405, floaters=True)
    fl = sw.floaters
    x = 600.0
    y = sw.strands.surface(x) + fl.r * synth.FLOAT_SINK
    fl.balls = [[3, x, y, True]]
    fl._next = 1e9  # no other ball
    sw._draw_strands = lambda layer, clock: layer.fill((255, 255, 255))  # ribbon light everywhere
    canvas = _canvas()
    sw.draw(canvas, 0.0)
    px, py = V.pt((x + 0.45 * fl.r, y))  # the dark body of the ball, clear of its number
    assert sum(canvas.get_at((round(px), round(py)))[:3]) < 300  # not the white light behind it


def test_balls_float_up_one_by_one_land_on_the_ribbon_and_drift_away():
    sw = synth.Synthwave(V, 405, floaters=True)
    fl = sw.floaters
    seen, landed = set(), False
    for _ in range(30 * 60):  # half a minute of menu
        sw.update(1 / 60)
        assert len(fl.balls) <= synth.FLOAT_MAX
        for number, x, y, floating in fl.balls:
            seen.add(number)
            if floating:
                landed = True
                assert abs(y - (sw.strands.surface(x) + fl.r * synth.FLOAT_SINK)) < 1e-6
    assert landed
    assert seen == set(range(1, len(seen) + 1)) and len(seen) >= synth.FLOAT_MAX  # 1, 2, 3 ...
    first = synth.Synthwave(V, 405, floaters=True)
    second = synth.Synthwave(V, 405, floaters=True)
    for _ in range(300):
        first.update(1 / 60)
        second.update(1 / 60)
    assert first.floaters.balls == second.floaters.balls  # no randomness


def test_a_floating_ball_drifts_the_way_the_waves_run_and_leaves_the_screen():
    sw = synth.Synthwave(V, 405, floaters=True)
    fl = sw.floaters
    fl.balls = [[3, 600.0, sw.strands.surface(600.0), True]]
    fl._next = 1e9  # no new balls
    sw.update(1.0)
    assert fl.balls[0][1] > 600.0  # to the right
    for _ in range(60 * 40):
        sw.update(1 / 60)
    assert fl.balls == []  # gone off the right edge


@pytest.mark.parametrize("window", [(1280, 720), (1920, 1200), (2560, 1080)])
def test_the_night_fills_any_window_to_its_edges(window):
    v = View.for_window(window)
    sw = synth.Synthwave(v, 405)
    canvas = pg.Surface(v.canvas)
    canvas.fill((255, 0, 255))
    sw.draw(canvas, 1.0)
    for p in ((0, 0), (window[0] - 1, 0), (0, window[1] - 1), (window[0] - 1, window[1] - 1)):
        assert tuple(canvas.get_at(p))[:3] != (255, 0, 255)  # painted right to every corner


def test_the_sun_sits_on_the_horizon_with_stripes_that_slide_down():
    sw = synth.Synthwave(V, 405)
    a, b = _canvas(), _canvas()
    sw.draw(a, 0.0)
    sw.draw(b, synth.SUN_STRIPE_S * 0.5)
    sun_top = V.pt((640, 405 - 140))
    assert sum(a.get_at((round(sun_top[0]), round(sun_top[1])))[:3]) > 400  # yellow, lit
    lower = pg.Rect(640 - 100, 405 - 60, 200, 55)  # the striped lower part changes ...
    assert pg.image.tobytes(a.subsurface(lower), "RGB") != pg.image.tobytes(
        b.subsurface(lower), "RGB"
    )


def test_the_crt_lines_are_faint_and_the_corners_darker():
    screen = pg.Surface((400, 300))
    screen.fill((200, 200, 200))
    crt.scanlines(screen)
    column = [screen.get_at((200, y))[0] for y in range(0, 30)]
    step = crt.period(1.0)
    dark = [y for y, c in enumerate(column) if c < 200]
    assert dark == list(range(step - 1, 30, step))  # one thin row in every `step`
    assert abs(min(column) - 200 * crt.SCANLINE_DARK) <= 1.5  # and only a little darker
    vig = crt.vignette((400, 300))
    assert vig.get_at((0, 0))[0] < vig.get_at((200, 150))[0] - 30  # corners darker


# --- arcade digits, text placement, the title ------------------------------------------------
def test_arcade_digits_light_only_their_segments():
    assert set(hud.SEGMENTS["8"]) == set("abcdefg") and hud.SEGMENTS["1"] == "bc"
    one, eight = _canvas(), _canvas()
    hud.seg_number(one, V, 1, 1, (100, 100), 40, C.CYAN, glow_k=0)
    hud.seg_number(eight, V, 8, 1, (100, 100), 40, C.CYAN, glow_k=0)

    def lit(surf):
        return sum(
            1 for x in range(80, 140) for y in range(90, 150) if surf.get_at((x, y))[1] > 150
        )

    assert lit(eight) > 2.5 * lit(one)


def test_text_is_placed_by_its_capitals_so_marks_never_push_it_down():
    a, b = _canvas(), _canvas()
    ra = hud.text(a, V, "HA", 30, C.WHITE, (100, 100))
    rb = hud.text(b, V, "HỘI", 30, C.WHITE, (100, 100))
    top_a = min(
        y
        for y in range(ra.top, ra.bottom)
        for x in range(ra.left, ra.right)
        if a.get_at((x, y))[0] > 128 and x < ra.left + 12
    )
    top_b = min(
        y
        for y in range(rb.top, rb.bottom)
        for x in range(rb.left, rb.left + 12)
        if b.get_at((x, y))[0] > 128
    )
    assert abs(top_a - top_b) <= 1  # the H starts on the same line with or without marks
    assert abs(top_a - 100) <= 2


def test_a_number_is_centred_in_its_badge():
    canvas = _canvas()
    hud.text(canvas, V, "1", 15, C.WHITE, (200, 200), bold=True, center=True)
    pts = [
        (x, y) for x in range(185, 216) for y in range(185, 216) if canvas.get_at((x, y))[0] > 128
    ]
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    cx, cy = (min(xs) + max(xs) + 1) / 2, (min(ys) + max(ys) + 1) / 2  # the middle of the ink
    assert abs(cx - 200) <= 1 and abs(cy - 200) <= 1


def test_the_title_stutters_on_then_hums():
    from game.scenes.menu import title_level

    assert title_level(0.0) == 0.0
    levels = [title_level(t / 100) for t in range(0, 90)]
    assert min(levels[10:]) < 0.5 < max(levels)  # it flickers while coming on
    steady = [title_level(2 + t / 10) for t in range(60)]
    assert min(steady) > 0.8  # then it stays lit


def test_the_scoreboard_flashes_a_number_that_changed():
    board = hud.Scoreboard()
    assert board.flash("shots", 0, 0.0) == 0.0  # the first value is not a change
    assert board.flash("shots", 1, 1.0) == 1.0
    assert 0.0 < board.flash("shots", 1, 1.0 + hud.FLASH_S / 2) < 1.0
    assert board.flash("shots", 1, 1.0 + hud.FLASH_S + 0.01) == 0.0


# --- rings of light ------------------------------------------------------------------------
def test_each_kind_of_hit_has_its_own_colour():
    colours = {kind: spec[0] for kind, spec in KINDS.items()}
    assert set(KINDS) == {"ball", "cushion"} and len(set(colours.values())) == 2


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
