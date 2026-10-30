"""The 8-ball rules inside the table scene (docs/plans/20261028-8ball.md AC3, AC5, AC6)."""

import math

import pygame as pg
import pytest

from game import config, i18n
from game.app import App
from game.physics import BallHitBall, BallHitCushion, BallPocketed, Shot
from game.render import hud
from game.render.layout import to_px
from game.rules.eight_ball import LOST, PLAYING, SOLID, WON


@pytest.fixture
def app():
    pg.init()
    a = App(pg.display.set_mode(config.LOGICAL_SIZE))
    a.go_play()
    yield a
    pg.quit()
    i18n.set_lang("vi")


def key(k):
    return pg.event.Event(pg.KEYDOWN, key=k)


def mouse(kind, x_m, y_m):
    x, y = (round(v) for v in to_px(x_m, y_m))
    return pg.event.Event(kind, pos=(x, y), button=1, rel=(0, 0), buttons=(1, 0, 0))


def click_at(pos):
    return pg.event.Event(pg.MOUSEBUTTONDOWN, pos=pos, button=1)


def settle(app, seconds=90):
    for _ in range(int(seconds * 60)):
        if not app.play._live:
            return
        app.update(1 / 60)
    raise AssertionError("the balls never stopped")


def scratch(app):
    """A shot straight into the corner pocket: the cue ball is pocketed and touches nothing."""
    app.play.world.place(0, 0.3, 0.3)
    app.play.fire(Shot(math.atan2(-1, -1), 0.3))
    settle(app)


def finish_with(app, *events):
    """Pretend a shot happened with these events; the scene judges it when everything is still."""
    play = app.play
    play.rules.on_shot()
    play.rules.on_events(events)
    play._live = True
    app.update(1 / 60)


def after_break(app):
    """A clean break: the cue ball hit the rack and a ball reached a cushion."""
    app.play.rules.on_shot()
    app.play.rules.on_events([BallHitBall(0, 1, 1.0), BallHitCushion(1, 1.0)])
    app.play.rules.finish_shot()


EIGHT_DOWN = (BallHitBall(0, 8, 1.0), BallPocketed(8, 0))  # the 8 first: only legal when cleared
EARLY_EIGHT = (BallHitBall(0, 3, 1.0), BallPocketed(8, 0))  # a legal touch, then the 8 goes in


# --- AC3: ball in hand -------------------------------------------------------------------------
def test_a_break_down_the_middle_is_not_a_foul_and_leaves_the_table_open(app):
    app.play.fire(Shot(0.0, 1.0))
    settle(app)
    assert app.play.rules.last.fouls == () and app.play.rules.fouls == 0
    assert app.play.rules.group is None and not app.play.rules.cue_in_hand


def test_a_scratch_is_a_foul_and_the_cue_ball_returns_to_be_placed(app):
    scratch(app)
    rules, cue = app.play.rules, app.play.world.balls[0]
    assert rules.fouls == 1 and rules.cue_in_hand
    assert cue.in_play  # back on the table, ready to place
    assert app.play._notice[0] == "foul" and app.play._banner_lines()


def test_the_cue_ball_in_hand_is_dragged_to_a_new_spot_and_dropped(app):
    scratch(app)
    cue = app.play.world.balls[0]
    app.handle_event(mouse(pg.MOUSEBUTTONDOWN, cue.x, cue.y))
    assert app.play.placing and not app.play.drag.active
    app.handle_event(mouse(pg.MOUSEMOTION, 1.0, 0.4))
    app.handle_event(mouse(pg.MOUSEBUTTONUP, 1.0, 0.4))
    assert not app.play.placing and not app.play.rules.cue_in_hand
    assert (cue.x, cue.y) == pytest.approx((1.0, 0.4), abs=0.003)


def test_dragging_onto_a_pocket_or_a_ball_leaves_the_cue_ball_on_its_last_good_spot(app):
    scratch(app)
    cue = app.play.world.balls[0]
    app.handle_event(mouse(pg.MOUSEBUTTONDOWN, cue.x, cue.y))
    app.handle_event(mouse(pg.MOUSEMOTION, 1.0, 0.4))
    good = (cue.x, cue.y)
    app.handle_event(mouse(pg.MOUSEMOTION, 0.0, 0.0))  # the corner pocket
    assert (cue.x, cue.y) == good and not app.play._place_ok
    ball = app.play.world.balls[5]
    app.handle_event(mouse(pg.MOUSEMOTION, ball.x, ball.y))  # on top of a ball
    assert (cue.x, cue.y) == good and not app.play._place_ok


def test_you_cannot_aim_until_the_cue_ball_is_placed(app):
    scratch(app)
    assert not app.play._can_aim()
    app.play.rules.cue_placed()
    assert app.play._can_aim()


# --- AC5: the end of a game ----------------------------------------------------------------------
def _won_position(app):
    after_break(app)
    app.play.rules.group, app.play.rules.pocketed = SOLID, set(range(1, 8))


def test_winning_shows_the_card_and_blocks_shooting_until_a_new_game(app):
    _won_position(app)
    finish_with(app, *EIGHT_DOWN)
    play = app.play
    assert play.rules.phase == WON and not play._can_aim()
    app.draw()
    app.handle_event(key(pg.K_RETURN))
    assert play.rules.phase == PLAYING and play.rules.shots == 0 and play.rules.balls_left == 15


def test_losing_by_pocketing_the_eight_early_names_the_reason(app):
    after_break(app)  # the 8 on the break would just rack again
    finish_with(app, *EARLY_EIGHT)
    assert app.play.rules.phase == LOST
    for lang in ("vi", "en"):
        i18n.set_lang(lang)
        app.draw()
    assert app.play.rules.last.reason == "result.lost_early"


def test_the_result_card_buttons_work_with_the_mouse(app):
    after_break(app)  # the 8 on the break would just rack again
    finish_with(app, *EARLY_EIGHT)
    menu, new = hud.RESULT_BUTTONS["menu"].center, hud.RESULT_BUTTONS["new"].center
    app.handle_event(pg.event.Event(pg.MOUSEMOTION, pos=menu, rel=(0, 0), buttons=(0, 0, 0)))
    assert app.play._hover == "menu"
    app.handle_event(click_at(menu))
    assert app.scene is app.menu
    assert not app.game_in_progress()  # a finished game is not "resumed" from the menu
    app.go_play()
    app.handle_event(click_at(new))
    assert app.play.rules.phase == PLAYING


def test_escape_on_the_card_goes_to_the_menu(app):
    after_break(app)  # the 8 on the break would just rack again
    finish_with(app, *EARLY_EIGHT)
    app.handle_event(key(pg.K_ESCAPE))
    assert app.scene is app.menu


def test_the_eight_on_the_break_racks_the_balls_again_and_keeps_the_count(app):
    finish_with(app, BallHitBall(0, 1, 1.0), BallPocketed(8, 0), BallPocketed(3, 1))
    play = app.play
    assert play.rules.phase == PLAYING and play.rules.shots == 1 and play.rules.fouls == 0
    assert all(b.in_play for b in play.world.balls) and play.rules.balls_left == 15
    assert play.rules.is_break and play._notice == ("info", "notice.rerack")


# --- AC6: what the screen says --------------------------------------------------------------------
def test_the_first_legal_pocket_announces_the_group(app):
    after_break(app)
    finish_with(app, BallHitBall(0, 11, 1.0), BallPocketed(11, 0))
    assert app.play._notice == ("info", "notice.group_stripe")


def test_clearing_the_group_announces_the_eight(app):
    _won_position(app)
    app.play.rules.pocketed = set(range(1, 7))  # only the 7 is left
    finish_with(app, BallHitBall(0, 7, 1.0), BallPocketed(7, 0))
    assert app.play._notice == ("info", "notice.eight") and app.play.rules.eight_is_next()


@pytest.mark.parametrize("lang", ["vi", "en"])
def test_every_rules_state_draws(app, lang):
    i18n.set_lang(lang)
    app.go_play()
    play = app.play
    app.draw()
    play.rules.group, play.rules.fouls = SOLID, 3
    app.draw()
    play.rules.pocketed = set(range(1, 8))
    app.draw()  # "now the 8-ball"
    scratch(app)
    app.draw()  # the ring and the banner
    play._notify("info", "notice.rerack")
    app.draw()


def test_the_result_card_shows_the_score_inside_the_card_in_both_languages(app):
    _won_position(app)
    finish_with(app, *EIGHT_DOWN)
    play = app.play
    assert play.rules.phase == WON and play.rules.score > 0
    c = hud.RESULT_CARD
    assert all(c.contains(r) for r in hud.RESULT_BUTTONS.values())  # nothing sticks out
    last_row = c.y + hud.RESULT_ROWS_Y + hud.RESULT_ROW_STEP + 30
    assert last_row < min(r.top for r in hud.RESULT_BUTTONS.values())  # rows end above the buttons
    for lang in ("vi", "en"):
        i18n.set_lang(lang)
        app.draw()
        assert i18n.t("result.score") != "result.score"
