"""The credits: text falls into the menu's ribbons one piece a second, floats, drifts away, and the
menu's words come back (docs/GAME_DESIGN.md "Phản hồi lần 25")."""

import numpy as np
import pygame as pg
import pytest

from game import config, i18n
from game.app import App
from game.render.view import View
from game.scenes import credits
from game.scenes.menu import MenuScene


@pytest.fixture
def app(monkeypatch, tmp_path):
    monkeypatch.setenv("NEONPOOL_SETTINGS", str(tmp_path / "settings.json"))
    pg.init()
    a = App(pg.display.set_mode(config.LOGICAL_SIZE))
    a.skip_transition()
    yield a
    pg.quit()
    i18n.set_lang("vi")


def key(k):
    return pg.event.Event(pg.KEYDOWN, key=k)


def run(app, seconds):
    for _ in range(round(seconds * 60)):
        app.update(1 / 60)


def roll(app):
    """Open the credits and let the menu's words dim away: the pieces start to fall."""
    app.handle_event(key(pg.K_c))
    run(app, config.CREDIT_FADE_OUT_S + 0.05)
    assert app.menu.mode == "roll"
    return app.menu


# --- the pieces ------------------------------------------------------------------------------
@pytest.mark.parametrize("lang", i18n.LANGS)
def test_every_piece_has_its_words_and_is_narrow_enough_to_clear_the_one_before(lang):
    i18n.set_lang(lang)
    v = View(1.0)
    for piece in credits.PIECES:
        for k, _ in piece:
            assert k in i18n.table("vi") and k in i18n.table("en"), k
        assert credits.piece_width(v, piece) <= config.CREDIT_MAX_W, (lang, piece)
    i18n.set_lang("vi")


def test_the_current_carries_a_piece_clear_of_its_landing_spot_before_the_next_lands():
    assert config.CREDIT_FLOW * config.CREDIT_EVERY_S >= config.CREDIT_MAX_W + 20


def test_a_piece_is_built_in_both_languages_and_is_added_light_on_black():
    for lang in i18n.LANGS:
        i18n.set_lang(lang)
        for piece in credits.PIECES:
            surf, w, h = credits.build_piece(View(1.0), piece)
            assert surf.get_width() >= w and surf.get_height() >= h
            assert pg.transform.average_color(surf)[:3] != (0, 0, 0)  # something is lit
    i18n.set_lang("vi")


def test_the_credits_name_the_maker():
    assert i18n.table("vi")["credits.person"] == "Smith Nguyễn"


# --- opening and closing ---------------------------------------------------------------------
def test_the_corner_link_and_the_c_key_open_the_credits_and_the_words_dim_away(app):
    menu = app.menu
    assert menu.mode == "menu" and menu.ui_k() == 1.0
    app.handle_event(pg.event.Event(pg.MOUSEBUTTONDOWN, pos=menu._credit_rect().center, button=1))
    assert menu.mode == "out"
    run(app, config.CREDIT_FADE_OUT_S / 2)
    assert 0.0 < menu.ui_k() < 1.0
    run(app, config.CREDIT_FADE_OUT_S)
    assert menu.mode == "roll" and menu.ui_k() == 0.0


def test_the_menu_buttons_do_nothing_while_the_credits_roll(app):
    menu = roll(app)
    app.handle_event(pg.event.Event(pg.MOUSEBUTTONDOWN, pos=menu._rects()[0].center, button=1))
    app.handle_event(key(pg.K_RETURN))
    assert menu.mode == "roll" and not menu.play_panel.is_open and app.scene is menu


def test_c_does_not_open_the_credits_while_a_panel_is_open(app):
    app.menu.settings.open()
    app.handle_event(key(pg.K_c))
    assert app.menu.mode == "menu"


def test_space_brings_the_menu_back_and_the_title_stutters_on_again(app):
    menu = roll(app)
    run(app, 1.5)
    opened = menu._opened
    app.handle_event(key(pg.K_SPACE))
    assert menu.mode == "in" and menu.credits.pieces == [] and menu._opened > opened
    run(app, config.CREDIT_FADE_IN_S + 0.05)
    assert menu.mode == "menu" and menu.ui_k() == 1.0


def test_space_while_the_words_are_still_dimming_comes_back_from_where_they_are(app):
    app.handle_event(key(pg.K_c))
    run(app, config.CREDIT_FADE_OUT_S * 0.5)
    before = app.menu.ui_k()
    app.handle_event(key(pg.K_SPACE))
    assert app.menu.mode == "in" and app.menu.ui_k() == pytest.approx(before, abs=0.05)


def test_the_menu_comes_back_by_itself_when_the_last_piece_has_gone(app):
    menu = roll(app)
    seconds = 0.0
    while menu.mode == "roll" and seconds < 30:
        run(app, 0.5)
        seconds += 0.5
    assert menu.mode == "in" and seconds < 15
    run(app, config.CREDIT_FADE_IN_S + 0.05)
    assert menu.mode == "menu"


# --- the pieces falling ----------------------------------------------------------------------
def test_a_piece_falls_from_the_top_edge_one_a_second_in_order(app):
    menu = roll(app)
    started, count = [], 0
    for _ in range(round(6 * 60)):
        app.update(1 / 60)
        if menu.credits._next > count:
            count = menu.credits._next
            started.append(menu._mode_t)
    assert len(started) == 6  # all of them, in order (PIECES is read in order)
    gaps = [b - a for a, b in zip(started, started[1:], strict=False)]
    assert all(abs(g - config.CREDIT_EVERY_S) < 0.05 for g in gaps)


def test_a_new_piece_starts_above_the_screen(app):
    menu = roll(app)
    run(app, config.CREDIT_FIRST_S + 0.05)
    piece = menu.credits.pieces[0]
    top = menu.view.logical_bounds()[1]
    assert piece.y - piece.h < top and not piece.afloat


def test_the_pieces_never_overlap_on_the_water(app):
    menu = roll(app)
    for _ in range(round(14 * 60)):
        app.update(1 / 60)
        floating = sorted((p for p in menu.credits.pieces if p.afloat), key=lambda p: p.x)
        for a, b in zip(floating, floating[1:], strict=False):
            assert b.x - b.w / 2 > a.x + a.w / 2, (a.x, a.w, b.x, b.w)


def test_a_piece_lands_on_the_ribbons_floats_with_them_and_is_carried_to_the_right(app):
    menu = roll(app)
    strands = menu.synth.strands
    run(app, 2.0)
    piece = next(p for p in menu.credits.pieces if p.afloat)
    x0 = piece.x
    run(app, 1.0)
    water = np.mean([strands.surface(piece.x + k * piece.w / 3) for k in (-1, 0, 1)])
    assert abs(piece.y - (water + config.CREDIT_SINK)) < 25  # riding the waves
    assert piece.x - x0 == pytest.approx(config.CREDIT_FLOW, rel=0.05)  # carried by the current


def test_a_landing_splashes_the_ribbons_and_a_floating_piece_presses_them_down(app):
    menu = roll(app)
    strands = menu.synth.strands
    rest_vy = float(np.abs(strands.vy).max())
    kicked = 0.0
    for _ in range(round(2.4 * 60)):
        app.update(1 / 60)
        kicked = max(kicked, float(np.abs(strands.vy).max()))
    assert kicked > rest_vy + 60  # well beyond how the ribbons move by themselves
    s = strands
    before = s.vy.copy()
    s.press(500.0, 60.0, config.CREDIT_PRESS, 0.1)
    assert (s.vy - before).max() > 0  # pushed DOWN (y grows downwards)
    assert np.allclose((s.vy - before)[:, 0], 0, atol=1e-3)  # and only near the piece


def test_no_ball_comes_up_while_the_credits_roll_and_they_come_back_after(app):
    menu = app.menu
    run(app, 4.0)  # the first balls are up
    floaters = menu.synth.floaters
    made = floaters._spawned
    assert made > 0
    app.handle_event(key(pg.K_c))
    for _ in range(60 * 30):
        app.update(1 / 60)
        if menu.mode == "menu":
            break
        assert floaters._spawned == made  # nothing new comes up from the floor
    assert menu.mode == "menu"
    run(app, 6.0)
    assert floaters._spawned > made  # and with the menu back, they come again


def test_a_new_window_size_ends_the_credits_cleanly(app):
    menu = roll(app)
    run(app, 1.5)
    menu.set_view(View.for_window((1920, 1080)))
    assert menu.mode == "menu" and menu.credits.pieces == []
    app.update(1 / 60)


# --- drawing ---------------------------------------------------------------------------------
@pytest.mark.parametrize("lang", i18n.LANGS)
def test_every_moment_of_the_credits_draws_in_both_languages(app, lang):
    i18n.set_lang(lang)
    menu = app.menu
    app.handle_event(key(pg.K_c))
    for seconds in (0.2, 0.5, 1.2, 3.0):  # dimming, falling, floating, drifting
        run(app, seconds)
        app.draw()
    while menu.mode != "in":
        run(app, 1.0)
        app.draw()
    run(app, 0.3)
    app.draw()
    assert isinstance(menu, MenuScene)


def test_the_words_really_fade_and_come_back_on_the_screen(app):
    screen = pg.display.get_surface()

    def lit_in_buttons():
        app.draw()
        r = app.menu._rects()[1]
        return sum(sum(screen.get_at((x, r.centery))[:3]) for x in range(r.left, r.right, 4))

    whole = lit_in_buttons()
    app.handle_event(key(pg.K_c))
    run(app, config.CREDIT_FADE_OUT_S / 2)
    half = lit_in_buttons()
    run(app, config.CREDIT_FADE_OUT_S)
    gone = lit_in_buttons()
    assert gone < half < whole or gone < whole * 0.6
    app.handle_event(key(pg.K_SPACE))
    run(app, config.CREDIT_FADE_IN_S + 0.1)
    assert lit_in_buttons() > gone
