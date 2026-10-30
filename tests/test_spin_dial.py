"""Setting the spin in the table scene: the dot on the dial, the wheel, back to the middle."""

import math

import pygame as pg
import pytest

from game import config, i18n
from game.app import App
from game.input.drag import DragAim
from game.physics import Shot
from game.render import hud
from game.render.layout import PANEL_H, PANEL_W, PANEL_X, PANEL_Y, to_px


@pytest.fixture
def app():
    pg.init()
    a = App(pg.display.set_mode(config.LOGICAL_SIZE))
    a.go_play()
    yield a
    pg.quit()
    i18n.set_lang("vi")


def wheel(y):
    return pg.event.Event(pg.MOUSEWHEEL, x=0, y=y, flipped=False)


def press(pos):
    return pg.event.Event(pg.MOUSEBUTTONDOWN, pos=pos, button=1)


def move(pos):
    return pg.event.Event(pg.MOUSEMOTION, pos=pos, rel=(0, 0), buttons=(1, 0, 0))


def release(pos):
    return pg.event.Event(pg.MOUSEBUTTONUP, pos=pos, button=1)


def above(app_spin_c, fraction):
    """The dial point `fraction` of the way from the middle to the top (negative: the bottom)."""
    cx, cy = app_spin_c
    return cx, cy - fraction * hud.SPIN_R * config.SPIN_DIAL_TRAVEL


def test_the_dial_sits_inside_the_side_panel_between_the_balls_and_the_keys():
    cx, cy = hud.SPIN_C
    assert PANEL_X < cx - hud.SPIN_R and cx + hud.SPIN_HIT_R < PANEL_X + PANEL_W
    assert cy - hud.SPIN_R > PANEL_Y + 300  # below the grid of balls
    assert cy + hud.SPIN_R < hud.KEYS_Y - 12  # above the line over the keys
    assert hud.SPIN_C[1] < PANEL_Y + PANEL_H


@pytest.mark.parametrize(
    "fraction,expected",
    [(1.0, 1.0), (0.5, 0.5), (0.0, 0.0), (-1.0, -1.0), (3.0, 1.0), (-3.0, -1.0)],
)
def test_dial_height_means_spin(fraction, expected):
    y = above(hud.SPIN_C, fraction)[1]
    assert hud.spin_value(y) == pytest.approx(expected)


def test_a_new_game_has_the_middle_selected(app):
    assert app.play.spin == 0.0


def test_the_wheel_steps_the_spin_up_and_down_and_stops_at_the_ends(app):
    play = app.play
    play.handle_event(wheel(1))
    assert play.spin == config.SPIN_WHEEL_STEP
    for _ in range(10):
        play.handle_event(wheel(1))
    assert play.spin == 1.0
    for _ in range(3):
        play.handle_event(wheel(-1))
    assert play.spin == 1.0 - 3 * config.SPIN_WHEEL_STEP
    for _ in range(20):
        play.handle_event(wheel(-1))
    assert play.spin == -1.0


def test_pressing_and_dragging_the_dot_sets_the_spin(app):
    play = app.play
    play.handle_event(press(hud.SPIN_C))
    assert play._dial_drag and play.spin == 0.0
    play.handle_event(move(above(hud.SPIN_C, 1.0)))
    assert play.spin == 1.0
    play.handle_event(move((hud.SPIN_C[0] + 60, hud.SPIN_C[1] + 30)))  # the pointer may wander off
    assert play.spin == -1.0
    play.handle_event(release(hud.SPIN_C))
    assert not play._dial_drag and play.spin == -1.0  # it stays where it was let go


def test_the_middle_is_easy_to_hit(app):
    play = app.play
    play.handle_event(press(above(hud.SPIN_C, 0.03)))
    assert play.spin == 0.0


def test_a_press_away_from_the_dial_does_not_grab_it(app):
    play = app.play
    play.handle_event(press((hud.SPIN_C[0] - hud.SPIN_HIT_R - 8, hud.SPIN_C[1])))
    assert not play._dial_drag


def test_the_spin_goes_into_the_shot_and_stays_for_the_next_one(app):
    play = app.play
    play.handle_event(wheel(1))
    play.handle_event(wheel(1))
    assert play.spin == 0.5
    cx, cy = to_px(play.world.balls[0].x, play.world.balls[0].y)
    play.handle_event(press((cx, cy)))
    play.handle_event(move((cx - 100, cy)))
    seen = []
    real_apply = play.world.apply
    play.world.apply = lambda shot: (seen.append(shot), real_apply(shot))[1]
    play.handle_event(release((cx - 100, cy)))
    assert len(seen) == 1 and seen[0].spin == 0.5 and seen[0].angle == pytest.approx(0.0)
    assert play.spin == 0.5  # kept: the next shot uses it too
    assert not play._dial_drag


def test_the_spin_cannot_be_changed_while_balls_roll(app):
    play = app.play
    play.fire(Shot(0.0, 0.5))
    assert not play.world.at_rest()
    play.handle_event(wheel(1))
    play.handle_event(press(hud.SPIN_C))
    assert play.spin == 0.0 and not play._dial_drag


def test_new_game_clears_the_spin(app):
    play = app.play
    play.handle_event(wheel(1))
    play.new_game()
    assert play.spin == 0.0


def test_drag_aim_passes_the_spin_to_the_shot():
    d = DragAim()
    d.begin((100.0, 100.0))
    d.move((40.0, 100.0))
    shot = d.end(-0.75)
    assert shot is not None and shot.spin == -0.75 and shot.angle == pytest.approx(0.0)
    d.begin((100.0, 100.0))
    d.move((40.0, 100.0))
    plain = d.end()
    assert plain is not None and plain.spin == 0.0 and math.isclose(plain.power, shot.power)


def test_the_panel_draws_with_the_dial_at_every_spin_in_both_languages(app):
    for lang in ("vi", "en"):
        i18n.set_lang(lang)
        for spin in (-1.0, 0.0, 1.0):
            app.play.spin = spin
            app.draw()


def listen(app):
    """Record every spin 'tok' and every button sound the table scene asks for."""
    heard = {"spin": [], "click": 0}
    app.audio.play_spin = lambda level: heard["spin"].append(level)
    app.audio.play_click = lambda: heard.__setitem__("click", heard["click"] + 1)
    return heard


def test_each_step_of_the_wheel_makes_a_soft_tok_that_follows_the_level(app):
    heard = listen(app)
    for _ in range(3):
        app.play.handle_event(wheel(1))
    assert heard["spin"] == [0.25, 0.5, 0.75]
    for _ in range(3):  # at the top end nothing moves, so nothing sounds
        app.play.handle_event(wheel(1))
    assert heard["spin"] == [0.25, 0.5, 0.75, 1.0]


def test_dragging_sounds_once_for_each_step_crossed_and_never_the_button_blip(app):
    heard = listen(app)
    play = app.play
    play.handle_event(press(hud.SPIN_C))  # a press always gives its tok (here: the middle)
    assert heard["spin"] == [0.0]
    play.handle_event(move(above(hud.SPIN_C, 0.52)))  # from the middle up two steps: one tok
    play.handle_event(move(above(hud.SPIN_C, 0.55)))  # still the same step: quiet
    assert len(heard["spin"]) == 2 and heard["spin"][1] == pytest.approx(0.52, abs=0.04)
    assert heard["click"] == 0


def test_a_press_that_does_not_change_the_step_still_gives_its_tok(app):
    heard = listen(app)
    app.play.handle_event(wheel(1))
    app.play.handle_event(press(above(hud.SPIN_C, 0.25)))
    assert heard["spin"][-1] == 0.25 and heard["click"] == 0


def test_the_spin_is_kept_through_a_whole_shot_and_into_the_next(app):
    play = app.play
    play.handle_event(wheel(-1))
    play.handle_event(wheel(-1))
    assert play.spin == -0.5
    play.fire(Shot(0.0, 0.3, play.spin))
    for _ in range(60 * 90):
        app.update(1 / 60)
        if not play._live:
            break
    assert not play._live and play.spin == -0.5
    play.handle_event(wheel(1))  # settable again once the balls stop
    assert play.spin == -0.25
