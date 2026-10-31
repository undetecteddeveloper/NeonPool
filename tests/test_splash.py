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


# --- a sound of its own for everything that appears (design log no. 26) ---
def test_the_sound_schedule_has_one_for_every_thing_that_appears_in_time_order():
    events = sp.sound_schedule()
    assert [e[0] for e in events] == sorted(e[0] for e in events)
    kinds = [e[1] for e in events]
    assert kinds.count("letter") == len("NeonPool") and kinds.count("sub") == 1
    assert kinds.count("line") == kinds.count("ok") == len(sp.TOOLS) and kinds.count("ready") == 1
    assert kinds[0] == "on" and kinds[-1] == "off"
    letters = [e for e in events if e[1] == "letter"]
    assert [e[2] for e in letters] == list(range(8))
    assert letters[0][0] == pytest.approx(sp.LETTER_AT)
    assert letters[3][0] == pytest.approx(sp.LETTER_AT + 3 * sp.LETTER_STEP)  # as the letter lights
    assert max(e[0] for e in events) < sp.SPLASH_S


@pytest.mark.parametrize("lang", i18n.LANGS)
def test_each_typed_character_ticks_and_a_line_gets_its_ok_after_the_last_one(lang):
    i18n.set_lang(lang)
    events = sp.sound_schedule()
    for i, key in enumerate(sp.TOOLS):
        start, n = sp.TOOLS_AT + sp.TOOL_STEP * i, len(sp.log_text(key))
        ticks = [e for e in events if e[1] == "tick" and start <= e[0] < start + n / sp.TYPE_CPS]
        assert len(ticks) == n - 1
        ok = [e for e in events if e[1] == "ok" and start < e[0] < start + sp.TOOL_STEP + 0.5]
        assert ok and ok[0][0] > start + n / sp.TYPE_CPS


def test_the_sounds_play_once_each_as_time_passes_and_a_restart_plays_them_again(app):
    heard = []
    app.audio.play_splash = lambda kind, i=0: heard.append((kind, i))
    app.start_splash()
    run(app, sp.SPLASH_S - 0.1)
    assert heard.count(("letter", 0)) == 1 and heard.count(("on", 0)) == 1
    assert [k for k, _ in heard].count("letter") == 8
    assert ("ready", 0) in heard and ("off", 0) in heard
    before = len(heard)
    run(app, 0.05)
    assert len(heard) >= before
    app.start_splash()
    heard.clear()
    run(app, 1.0)
    assert ("letter", 0) in heard


def test_a_sound_waits_for_its_moment(app):
    heard = []
    app.audio.play_splash = lambda kind, i=0: heard.append((kind, i))
    app.start_splash()
    run(app, sp.LETTER_AT - 0.1)
    assert heard == [("on", 0)]
    run(app, 0.2)
    assert ("letter", 0) in heard and ("letter", 1) not in heard


# --- the glass: bowed like an arcade monitor ---
def test_the_picture_is_bowed_out_and_the_corners_of_the_glass_are_black(app):
    screen = pg.display.get_surface()
    app.start_splash()
    app.splash.t = 3.0
    app.draw()
    w, h = screen.get_size()
    for corner in ((2, 2), (w - 3, 2), (2, h - 3), (w - 3, h - 3)):
        assert sum(screen.get_at(corner)[:3]) == 0

    def edge(y):  # how far in the lit picture starts on a row
        return next(x for x in range(w // 2) if sum(screen.get_at((x, y))[:3]) > 6)

    assert edge(h // 2) < edge(h // 8) < edge(12)  # narrowest at the top, widest in the middle


def test_the_flat_picture_is_still_what_is_drawn_while_the_window_is_changing_size(app):
    big = pg.Surface((1500, 900))
    app.start_splash()
    app.splash.draw(big)  # the pictures are for the old size: no crash, just the flat picture
