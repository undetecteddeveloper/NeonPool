"""AC9/AC10: app wiring, headless. Window mapping and drag maths have their own tests."""

import pygame as pg
import pytest

from game import config, i18n
from game.app import App
from game.render.layout import to_px


@pytest.fixture
def app():
    pg.init()
    screen = pg.display.set_mode(config.LOGICAL_SIZE)
    a = App(screen)
    yield a
    pg.quit()
    i18n.set_lang("vi")


def key(k):
    return pg.event.Event(pg.KEYDOWN, key=k)


def click(pos):
    return pg.event.Event(pg.MOUSEBUTTONDOWN, pos=pos, button=1)


def test_app_opens_on_the_menu_and_play_enters_the_table(app):
    assert app.scene is app.menu
    app.handle_event(key(pg.K_RETURN))  # first item = Play: the panel with Solo / Two players
    assert app.scene is app.menu and app.menu.play_panel.is_open
    app.handle_event(key(pg.K_RETURN))  # its first choice = Solo
    assert app.scene is app.play and not app.menu.play_panel.is_open


def test_the_menu_has_settings_where_the_language_now_lives(app):
    from game.scenes.menu import ITEMS

    assert ITEMS == ("play", "help", "settings", "quit")
    assert i18n.get_lang() == "vi"
    app.menu.settings.open()
    app.handle_event(key(pg.K_RETURN))  # the first row is the language
    assert i18n.get_lang() == "en"
    app.handle_event(key(pg.K_RETURN))
    assert i18n.get_lang() == "vi"


def test_menu_quit_stops_the_app(app):
    app.handle_event(key(pg.K_UP))  # wraps to the last item: Quit
    app.handle_event(key(pg.K_RETURN))
    assert app.running is False


def test_menu_buttons_work_with_the_mouse(app):
    rects = app.menu._rects()
    app.handle_event(click(rects[0].center))
    assert app.menu.play_panel.is_open
    app.handle_event(click(app.menu.play_panel._rects()["solo"].center))
    assert app.scene is app.play


def test_esc_returns_to_menu_and_play_resumes_the_same_game(app):
    app.go_play()
    cue = app.play.world.balls[0]
    cx, cy = (round(v) for v in to_px(cue.x, cue.y))
    app.handle_event(click((cx, cy)))
    app.handle_event(
        pg.event.Event(pg.MOUSEMOTION, pos=(cx - 150, cy), rel=(0, 0), buttons=(1, 0, 0))
    )
    app.handle_event(pg.event.Event(pg.MOUSEBUTTONUP, pos=(cx - 150, cy), button=1))
    assert app.play.rules.shots == 1 and app.game_in_progress()
    app.handle_event(key(pg.K_ESCAPE))
    assert app.scene is app.menu
    app.handle_event(key(pg.K_RETURN))  # Play opens the panel ...
    app.handle_event(key(pg.K_RETURN))  # ... whose first choice is now "Resume"
    assert app.scene is app.play and app.play.rules.shots == 1


def test_esc_while_dragging_cancels_the_drag_instead_of_leaving(app):
    app.go_play()
    cue = app.play.world.balls[0]
    cx, cy = (round(v) for v in to_px(cue.x, cue.y))
    app.handle_event(click((cx, cy)))
    assert app.play.drag.active
    app.handle_event(key(pg.K_ESCAPE))
    assert not app.play.drag.active and app.scene is app.play


def test_cannot_start_aiming_while_balls_move(app):
    app.go_play()
    app.play.world.balls[1].vx = 1.0  # something is rolling
    cue = app.play.world.balls[0]
    cx, cy = (round(v) for v in to_px(cue.x, cue.y))
    app.handle_event(click((cx, cy)))
    assert not app.play.drag.active


def test_keys_restart_and_mute_and_the_table_always_feels_medium(app):
    app.go_play()
    app.play.rules.shots = 5
    app.handle_event(key(pg.K_r))
    assert app.play.rules.shots == 0
    app.handle_event(key(pg.K_m))
    assert app.audio.muted
    for k in (pg.K_1, pg.K_2, pg.K_3):  # the user removed the "table feel" choice (2026-10-29)
        app.handle_event(key(k))
        assert app.play.world.feel.key == "VUA"


def test_every_screen_draws_in_both_languages(app):
    for lang in ("vi", "en"):
        i18n.set_lang(lang)
        app.go_menu()
        app.draw()
        app.go_play()
        app.draw()


def test_right_click_cancels_an_aim(app):
    app.go_play()
    cue = app.play.world.balls[0]
    cx, cy = (round(v) for v in to_px(cue.x, cue.y))
    app.handle_event(click((cx, cy)))
    assert app.play.drag.active
    app.handle_event(pg.event.Event(pg.MOUSEBUTTONDOWN, pos=(cx, cy), button=3))
    assert not app.play.drag.active and app.play.rules.shots == 0


def test_drawing_a_ball_that_is_dropping_into_a_pocket(app):
    app.go_play()
    app.play.fx.add_drop(3, 0.05, 0.05, 0)
    app.play.fx.add_ripple(1.0, 0.6)
    app.update(config.POCKET_ANIM_S / 2)
    app.draw()


def test_the_loading_screen_is_a_dark_screen_with_one_line_in_the_middle():
    from game import app as app_module
    from game.render import palette as C

    pg.init()
    screen = pg.display.set_mode(config.LOGICAL_SIZE)
    app_module._show_loading(screen)
    w, h = screen.get_size()
    lit = [
        (x, y)
        for x in range(0, w, 2)
        for y in range(0, h, 2)
        if tuple(screen.get_at((x, y)))[:3] != tuple(C.BG)
    ]
    assert lit, "the line was not drawn"
    xs, ys = [p[0] for p in lit], [p[1] for p in lit]
    assert w * 0.3 < min(xs) and max(xs) < w * 0.7  # a small line, in the middle
    assert h * 0.4 < min(ys) and max(ys) < h * 0.6
    pg.quit()
