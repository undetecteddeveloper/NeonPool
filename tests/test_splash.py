"""The opening screen: the title first, then the tools it was made with, then the menu."""

import pygame as pg
import pytest

from game import config, i18n
from game.app import App
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


def lit(surface, rect):
    """The brightest channel found in a logical rect of the screen."""
    return max(max(surface.get_at((x, y))[:3]) for x in range(rect.left, rect.right, 3)
               for y in range(rect.top, rect.bottom, 3))  # fmt: skip


LOG = pg.Rect(sp.LOG_X, sp.LOG_Y - 5, sp.LOG_W, 4 * sp.LOG_STEP + 30)
TITLE = pg.Rect(sp.CX - 260, sp.TITLE_Y - 40, 520, 80)


def test_the_app_opens_on_the_menu_and_only_the_real_game_starts_on_the_splash(app):
    assert (
        app.scene is app.menu
    )  # tools and tests photograph the menu; run_forever starts the splash
    app.start_splash()
    assert app.scene is app.splash and app.splash.t == 0.0


def test_it_hands_over_to_the_menu_by_itself_and_the_title_stutters_on_there(app):
    app.start_splash()
    entered = []
    app.menu.enter = lambda: entered.append(1)
    run(app, sp.SPLASH_S + 0.1)
    assert app.scene is app.menu and entered == [1]


@pytest.mark.parametrize(
    "event",
    [
        pg.event.Event(pg.KEYDOWN, key=pg.K_SPACE),
        pg.event.Event(pg.KEYDOWN, key=pg.K_x),
        pg.event.Event(pg.MOUSEBUTTONDOWN, pos=(10, 10), button=1),
    ],
)
def test_any_key_or_click_skips_it(app, event):
    app.start_splash()
    run(app, 1.0)
    app.handle_event(event)
    assert app.scene is app.menu


def test_skipping_twice_goes_to_the_menu_once(app):
    app.start_splash()
    calls = []
    app.go_menu = lambda: calls.append(1)
    app.splash.finish()
    app.splash.finish()
    assert calls == [1]


def test_the_mouse_moving_does_not_skip_it(app):
    app.start_splash()
    app.handle_event(pg.event.Event(pg.MOUSEMOTION, pos=(5, 5), rel=(1, 1), buttons=(0, 0, 0)))
    assert app.scene is app.splash


def test_the_title_comes_first_then_the_tools(app):
    screen = pg.display.get_surface()
    app.start_splash()
    app.splash.t = sp.LETTER_AT + sp.LETTER_STEP * 8 + 0.3  # every letter is lit; no tool yet
    app.draw()
    assert lit(screen, TITLE) > 200 and lit(screen, LOG) < 60
    app.splash.t = sp.SPLASH_S - 0.2  # the end: all the tools have been typed
    app.draw()
    assert lit(screen, LOG) > 150


def test_the_screen_starts_dark_and_the_letters_light_one_by_one(app):
    screen = pg.display.get_surface()
    app.start_splash()
    app.splash.t = sp.LETTER_AT - 0.1
    app.draw()
    before = lit(screen, TITLE)
    app.splash.t = sp.LETTER_AT + sp.LETTER_STEP * 3.5
    app.draw()
    half = lit(screen, TITLE)
    assert before < 100 < half


def test_the_tools_are_typed_a_few_characters_at_a_time_and_each_ends_with_ok(app):
    assert sp.TOOLS_AT + sp.TOOL_STEP * len(sp.TOOLS) + 0.5 < sp.SPLASH_S  # time to read it all
    for key in sp.TOOLS:
        for lang in i18n.LANGS:
            assert key in i18n.table(lang)
    for lang in i18n.LANGS:
        assert i18n.table(lang)["splash.ok"] == "OK" and i18n.table(lang)["splash.ready"]


def test_the_music_is_quiet_during_the_splash(app):
    tracks = []
    app.audio.update_music = lambda dt, track, duck=False: tracks.append(track)
    app.start_splash()
    app.update(1 / 60)
    assert tracks[-1] is None
    app.go_menu()
    app.update(1 / 60)
    assert tracks[-1] == "menu"


def test_its_scan_lines_are_darker_than_the_games(app):
    assert app.splash.SCAN_DARK < config_scan() and not hasattr(app.menu, "SCAN_DARK")


def config_scan():
    from game.render import crt

    return crt.SCANLINE_DARK


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
    app.start_splash()
    for t in (0.0, 0.7, 1.6, 2.2, 3.0, 4.4, 5.6, sp.SPLASH_S - 0.05):
        app.splash.t = t
        app.draw()
    pg.quit()
    i18n.set_lang("vi")
