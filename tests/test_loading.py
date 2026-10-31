"""The first screen: "Getting ready" on the arcade monitor while the game makes what it needs
before the first picture (docs/GAME_DESIGN.md "Phản hồi lần 27 và 28")."""

import pygame as pg
import pytest

from game import config, i18n
from game.app import App
from game.scenes import loading as ld
from game.scenes.help import TOPICS


@pytest.fixture
def screen():
    pg.init()
    s = pg.display.set_mode(config.LOGICAL_SIZE)
    yield s
    pg.quit()
    i18n.set_lang("vi")


def bright(screen, rect):
    """How many pixels of the rect are lit in some colour."""
    return sum(
        1
        for x in range(rect.left, rect.right, 2)
        for y in range(rect.top, rect.bottom, 2)
        if max(screen.get_at((x, y))[:3]) > 60
    )


MIDDLE = pg.Rect(500, 335, 280, 50)  # where the one small line is


@pytest.mark.parametrize("lang", i18n.LANGS)
def test_it_is_one_small_line_in_the_middle_of_a_dark_screen_and_nothing_else(screen, lang):
    i18n.set_lang(lang)
    ld.LoadingScene(screen).draw(screen)
    assert bright(screen, MIDDLE) > 20  # the line is lit
    for rect in (pg.Rect(300, 60, 680, 240), pg.Rect(300, 400, 680, 240)):
        assert bright(screen, rect) == 0  # no title, no log, no buttons
    assert i18n.t("app.loading") != "app.loading"  # it has its words in this language


def test_it_has_the_glass_of_the_opening_screen_black_corners_bowed_sides(screen):
    ld.LoadingScene(screen).draw(screen)
    w, h = screen.get_size()
    for corner in ((2, 2), (w - 3, 2), (2, h - 3), (w - 3, h - 3)):
        assert sum(screen.get_at(corner)[:3]) == 0

    def edge(y):  # how far in the lit picture starts on a row
        return next(x for x in range(w // 2) if sum(screen.get_at((x, y))[:3]) > 6)

    assert edge(h // 2) < edge(h // 8)  # the sides bulge out in the middle


@pytest.mark.parametrize("lang", i18n.LANGS)
@pytest.mark.parametrize("size", [(1280, 720), (1920, 1080), (900, 700)])
def test_it_draws_in_both_languages_at_other_window_shapes(lang, size):
    pg.init()
    screen = pg.display.set_mode(size)
    i18n.set_lang(lang)
    scene = ld.LoadingScene(screen)
    scene.draw(screen)
    assert scene.show(screen)
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


def test_every_step_is_a_small_piece_that_ends(screen):
    app = App(screen)
    steps = app.prepare_steps()
    assert len(steps) == 6
    for work in steps:
        for _ in range(100):
            if not work():
                break
        else:
            raise AssertionError("a step never ended")


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
