"""The first screen: a boot log on the arcade monitor while the game makes what it needs before
the first picture (docs/GAME_DESIGN.md "Phản hồi lần 27")."""

import pygame as pg
import pytest

from game import config, i18n
from game.app import App
from game.render import hud
from game.scenes import loading as ld
from game.scenes.help import TOPICS


@pytest.fixture
def screen():
    pg.init()
    s = pg.display.set_mode(config.LOGICAL_SIZE)
    yield s
    pg.quit()
    i18n.set_lang("vi")


def lit(screen, rect):
    """How many pixels of the rect are bright in some colour (the words are cyan or green)."""
    return sum(
        1
        for x in range(rect.left, rect.right, 2)
        for y in range(rect.top, rect.bottom, 2)
        if max(screen.get_at((x, y))[:3]) > 200
    )


def test_a_line_appears_when_a_thing_starts_and_gets_its_ok_when_it_is_done(screen):
    scene = ld.LoadingScene(screen)
    scene.begin("loading.help")
    scene.begin("loading.help")  # (asking again does not add a second line)
    scene.begin("loading.music")
    assert [line[0] for line in scene.lines] == ["loading.help", "loading.music"]
    scene.done("loading.help")
    assert [line[1] for line in scene.lines] == [True, False]


def test_it_looks_like_the_opening_screen_glass_corners_black_the_words_lit(screen):
    scene = ld.LoadingScene(screen)
    scene.begin("loading.start")
    scene.done("loading.start")
    scene.begin("loading.help")
    scene.draw(screen)
    w, h = screen.get_size()
    for corner in ((2, 2), (w - 3, 2), (2, h - 3), (w - 3, h - 3)):
        assert sum(screen.get_at(corner)[:3]) == 0
    row = pg.Rect(ld.LOG_X, ld.LOG_Y - 6, ld.LOG_W, 2 * ld.LOG_STEP)
    assert lit(screen, row) > 20  # the lines are lit
    assert lit(screen, pg.Rect(300, 60, 680, 150)) == 0  # the title is there but not lit


@pytest.mark.parametrize("lang", i18n.LANGS)
@pytest.mark.parametrize("size", [(1280, 720), (1920, 1080), (900, 700)])
def test_every_line_fits_and_draws_in_both_languages_at_other_window_shapes(lang, size):
    pg.init()
    screen = pg.display.set_mode(size)
    i18n.set_lang(lang)
    scene = ld.LoadingScene(screen)
    app_steps = ["loading.start", "loading.help", "loading.panels", "loading.cards",
                 "loading.credits", "loading.looks", "loading.music", ld.READY_KEY]  # fmt: skip
    for key in app_steps:
        scene.begin(key)
        scene.draw(screen)
        scene.done(key)
    scene.draw(screen)
    for key in app_steps:  # no line is wider than the column it sits in
        assert hud.text_width(scene.view, f"> {i18n.t(key).lower()}", ld.LOG_PT, bold=True) < (
            ld.LOG_W - 80
        ), key
    pg.quit()
    i18n.set_lang("vi")


def test_closing_the_window_while_it_loads_stops_the_start(screen):
    pg.event.clear()
    pg.event.post(pg.event.Event(pg.QUIT))
    assert App.boot(screen) is None


def test_the_boot_makes_everything_ahead_and_opens_on_the_opening_screen(screen):
    app = App.boot(screen)
    assert app is not None and app.scene is app.splash
    n = len(TOPICS)
    assert all((i, i18n.get_lang()) in app.help._pages for i in range(n))  # every picture
    assert app._warmed == app._warm_key()
    assert app.help.prefetch is True


def test_the_music_is_made_during_the_loading_so_no_thread_works_against_the_first_frames(
    screen, monkeypatch
):
    monkeypatch.delenv("NEONPOOL_NO_MUSIC", raising=False)
    pg.mixer.quit()
    app = App.boot(screen)
    try:
        from game import music

        assert app.audio.available
        assert all(name in app.audio._tracks for name in music.TRACKS)
        app.update(1 / 60)
        assert app.audio._music_thread is None  # no thread was ever started
    finally:
        pg.mixer.quit()


def test_one_step_at_a_time_each_ends_and_each_has_its_words_in_both_languages(screen):
    app = App(screen)
    steps = app.prepare_steps()
    assert [k for k, _ in steps] == [
        "loading.help", "loading.panels", "loading.cards", "loading.credits", "loading.looks",
        "loading.music",
    ]  # fmt: skip
    for key, work in steps:
        assert key in i18n.table("vi") and key in i18n.table("en")
        for _ in range(100):
            if not work():
                break
        else:
            raise AssertionError(f"{key} never ended")


def test_the_pictures_made_ahead_are_not_made_again_every_frame_at_the_menu(screen):
    app = App.boot(screen)
    app.go_menu()
    app.skip_transition()
    calls = []
    real = app.menu.credits.prewarm
    app.menu.credits.prewarm = lambda: (calls.append(1), real())[1]
    for _ in range(round(5 * 60)):  # five seconds, long past the time the menu settles
        app.update(1 / 60)
    assert calls == []
    i18n.set_lang("en")  # a new language: the pictures are for the old one
    for _ in range(round(4 * 60)):
        app.update(1 / 60)
    assert calls == [1]  # made again once, not every frame


def test_prewarming_the_looks_leaves_the_menu_and_the_opening_screen_as_they_were(screen):
    app = App(screen)
    menu, splash = app.menu, app.splash
    before = (menu.mode, menu._mode_t, menu._opened, menu._clock, menu._credit_hot, splash.t)
    app._warm_looks(screen)
    assert (
        menu.mode,
        menu._mode_t,
        menu._opened,
        menu._clock,
        menu._credit_hot,
        splash.t,
    ) == before
