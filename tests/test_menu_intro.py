"""After the opening screen a beam of light draws the menu from the top down
(docs/GAME_DESIGN.md "Phản hồi lần 26 và 27")."""

import pygame as pg
import pytest

from game import config, i18n
from game.app import App
from game.scenes import menu as m
from game.scenes import splash as sp


@pytest.fixture
def app(monkeypatch, tmp_path):
    monkeypatch.setenv("NEONPOOL_SETTINGS", str(tmp_path / "settings.json"))
    pg.init()
    a = App(pg.display.set_mode(config.LOGICAL_SIZE))
    a.skip_transition()
    yield a
    pg.quit()
    i18n.set_lang("vi")


def run(app, seconds):
    for _ in range(round(seconds * 60)):
        app.update(1 / 60)


def at(app, age):
    """The menu `age` seconds after the beam started, drawn."""
    app.menu.start_intro()
    run(app, config.MENU_INTRO_START_S + age)
    app.draw()
    return pg.display.get_surface()


def lit(screen, rect):
    """How many pixels of a logical rect are white-ish (the words; the night is pink and cyan)."""
    return sum(
        1
        for x in range(rect.left, rect.right, 2)
        for y in range(rect.top, rect.bottom, 2)
        if min(screen.get_at((x, y))[:3]) > 150
    )


TITLE = pg.Rect(420, 100, 440, 90)


def test_the_beam_starts_after_the_splash_and_ends_by_itself(app):
    app.start_splash()
    app.splash.finish()
    assert app.scene is app.menu and app.menu.mode == "intro"
    run(app, config.MENU_INTRO_START_S + config.MENU_INTRO_S + m.INTRO_SETTLE_S + 0.1)
    assert app.menu.mode == "menu"


def test_a_menu_that_is_simply_opened_has_no_beam(app):
    assert app.menu.mode == "menu"
    app.go_play()
    app.go_menu()
    assert app.menu.mode == "menu"


def test_before_the_beam_arrives_none_of_the_words_are_there(app):
    screen = at(app, -0.3)
    for rect in [TITLE, *app.menu._rects()]:
        assert lit(screen, rect) == 0, rect  # only the night is there


def test_what_the_beam_has_passed_is_there_and_what_it_has_not_is_not(app):
    screen = at(
        app, config.MENU_INTRO_S * 0.55
    )  # about y = 430: past the title, short of the buttons
    assert lit(screen, TITLE) > 100
    assert lit(screen, app.menu._rects()[3]) == 0
    run(app, config.MENU_INTRO_S)
    app.draw()
    assert lit(pg.display.get_surface(), app.menu._rects()[3]) > 20


def test_the_menu_is_whole_afterwards_and_looks_like_any_other_time(app):
    screen = at(app, config.MENU_INTRO_S + m.INTRO_SETTLE_S + 0.1)
    assert app.menu.mode == "menu"
    for rect in app.menu._rects():
        assert lit(screen, rect) > 20


def test_the_beam_is_a_bright_line_across_the_whole_screen(app):
    screen = at(app, config.MENU_INTRO_S * 0.8)
    y = round(screen.get_height() * 0.8)  # the beam runs from the top of the screen to the bottom
    for x in (5, 300, 640, 1000, 1270):
        assert max(min(screen.get_at((x, yy))[:3]) for yy in range(y - 6, y + 7)) > 120, x


def test_a_part_flickers_on_as_the_beam_reaches_it():
    levels = [m.MenuScene._flicker(a) for a in (-0.1, 0.0, 0.07, 0.13, 0.22, 0.4)]
    assert levels[0] == 0.0 and levels[-1] == 1.0
    assert 0.0 < min(levels[1:4]) < 1.0 and max(levels[1:]) == 1.0


def test_a_key_or_a_click_shows_the_menu_at_once_and_does_nothing_else(app):
    app.menu.start_intro()
    app.handle_event(pg.event.Event(pg.KEYDOWN, key=pg.K_RETURN))
    assert app.menu.mode == "menu" and not app.menu.play_panel.is_open
    app.menu.start_intro()
    app.handle_event(pg.event.Event(pg.MOUSEBUTTONDOWN, pos=app.menu._rects()[0].center, button=1))
    assert app.menu.mode == "menu" and not app.menu.play_panel.is_open


def test_the_sound_of_the_beam_plays_once_when_it_starts(app):
    heard = []
    app.audio.play_menu_sweep = lambda: heard.append(1)
    app.menu.start_intro()
    run(app, config.MENU_INTRO_START_S - 0.1)
    assert heard == []
    run(app, 0.3)
    run(app, 1.0)
    assert heard == [1]


def test_the_title_stutters_on_as_the_beam_arrives(app):
    app.menu.start_intro()
    arrives = app.menu._arrives(m.INTRO_TITLE.top)
    assert 0 < arrives < 0.3  # near the top of the screen, so soon after the beam starts
    assert app.menu._opened == pytest.approx(app.menu._clock + config.MENU_INTRO_START_S + arrives)


def test_a_new_window_size_ends_the_beam(app):
    app.menu.start_intro()
    run(app, 0.8)
    app.menu.set_view(app.menu.view.__class__.for_window((1920, 1080)))
    assert app.menu.mode == "menu"
    app.update(1 / 60)


@pytest.mark.parametrize("lang", i18n.LANGS)
@pytest.mark.parametrize("size", [(1280, 720), (1920, 1080), (900, 700)])
def test_every_moment_draws_in_both_languages_at_other_window_shapes(
    monkeypatch, tmp_path, lang, size
):
    monkeypatch.setenv("NEONPOOL_SETTINGS", str(tmp_path / "settings.json"))
    pg.init()
    app = App(pg.display.set_mode(size))
    app.skip_transition()
    i18n.set_lang(lang)
    app.menu.start_intro()
    for _ in range(100):
        app.update(1 / 60)
        app.draw()
    pg.quit()
    i18n.set_lang("vi")


def test_the_splash_hands_over_to_a_menu_that_draws_with_the_beam(app):
    app.start_splash()
    run(app, sp.SPLASH_S + 0.05)
    assert app.scene is app.menu and app.menu.mode == "intro"


# --- the pause and the black frame (design log no. 27) -------------------------------------------
def test_the_beam_waits_half_a_second_more_than_before_in_a_black_frame():
    assert config.MENU_INTRO_START_S == pytest.approx(0.35 + 0.5)


def test_the_whole_frame_is_black_until_the_beam_starts_not_just_the_words(app):
    app.menu.start_intro()
    for _ in range(round((config.MENU_INTRO_START_S - 0.05) * 60)):
        app.update(1 / 60)
        app.draw()
        screen = pg.display.get_surface()
        # the sky, the sun, the ribbons, the floor, the words: nothing is there
        assert all(
            max(screen.get_at((x, y))[:3]) <= 8  # (the scan lines of the whole game are on top)
            for x in range(0, 1280, 80)
            for y in range(0, 720, 60)
        )


def test_the_beam_draws_the_sky_and_the_floor_too_as_it_passes(app):
    screen = at(app, config.MENU_INTRO_S * 0.5)  # half way down
    assert any(sum(screen.get_at((x, 60))[:3]) > 25 for x in range(0, 1280, 20))  # the sky above
    sun = pg.Rect(560, 280, 160, 70)
    assert any(max(screen.get_at((x, y))[:3]) > 200 for x in range(sun.left, sun.right, 4)
               for y in range(sun.top, sun.bottom, 4))  # fmt: skip
    assert all(max(screen.get_at((x, 600))[:3]) == 0 for x in range(0, 1280, 40))  # below: black


def test_nothing_heavy_is_drawn_while_the_frame_is_black(app):
    drawn = []
    app.menu.synth.draw = lambda *a, **k: drawn.append(1)
    app.menu.start_intro()
    run(app, 0.3)
    app.draw()
    assert drawn == []
