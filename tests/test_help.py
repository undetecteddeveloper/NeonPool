"""The how-to-play screen: opening and leaving it, its pages, its words, its real pictures."""

import pygame as pg
import pytest

from game import config, i18n
from game.app import App
from game.render import draw, hud
from game.render import palette as C
from game.render.layout import to_px
from game.render.view import View
from game.scenes import help as help_scene
from game.scenes import help_pictures as pics
from game.scenes.help import CARD, NEXT, PREV, TEXT_W, TEXT_X, TOPICS


@pytest.fixture
def app():
    pg.init()
    a = App(pg.display.set_mode(config.LOGICAL_SIZE))
    yield a
    pg.quit()
    i18n.set_lang("vi")


def key(k):
    return pg.event.Event(pg.KEYDOWN, key=k)


def click(pos):
    return pg.event.Event(pg.MOUSEBUTTONDOWN, pos=pos, button=1)


# --- getting in and out ---------------------------------------------------------------------
def test_the_menu_has_a_how_to_play_button_that_opens_the_help(app):
    app.handle_event(key(pg.K_DOWN))  # play -> how to play
    app.handle_event(key(pg.K_RETURN))
    assert app.scene is app.help


def test_escape_goes_back_to_the_menu_it_came_from(app):
    app.go_help()
    app.handle_event(key(pg.K_ESCAPE))
    assert app.scene is app.menu


def test_h_in_a_game_opens_the_help_and_escape_returns_to_the_same_game(app):
    app.go_play()
    app.play.rules.shots = 3
    app.handle_event(key(pg.K_h))
    assert app.scene is app.help
    app.handle_event(key(pg.K_ESCAPE))
    assert app.scene is app.play and app.play.rules.shots == 3


def test_opening_the_help_cancels_an_aim_in_progress(app):
    app.go_play()
    app.play.drag.begin((100, 100))
    app.handle_event(key(pg.K_h))
    assert not app.play.drag.active


def test_the_side_panel_lists_the_help_key():
    assert "hud.key_help" in [what for _, what in hud.PANEL_KEYS]
    assert all(cap.startswith("keycap.") for cap, _ in hud.PANEL_KEYS)


# --- pages ----------------------------------------------------------------------------------
def test_pages_turn_with_keys_and_stop_at_both_ends(app):
    app.go_help()
    h = app.help
    app.handle_event(key(pg.K_LEFT))
    assert h.page == 0
    for _ in range(len(TOPICS) + 3):
        app.handle_event(key(pg.K_RIGHT))
    assert h.page == len(TOPICS) - 1
    app.handle_event(key(pg.K_LEFT))
    assert h.page == len(TOPICS) - 2


def test_pages_turn_with_the_buttons_and_the_dots(app):
    app.go_help()
    app.handle_event(click(NEXT.center))
    assert app.help.page == 1
    app.handle_event(click(PREV.center))
    assert app.help.page == 0
    app.handle_event(click(help_scene.DOTS[4].center))
    assert app.help.page == 4


# --- words ------------------------------------------------------------------------------------
@pytest.mark.parametrize("lang", ["vi", "en"])
def test_every_topic_has_its_words_in_both_languages(lang):
    table = i18n.table(lang)
    for prefix, count, markers in TOPICS:
        assert len(markers) == count
        assert f"{prefix}.title" in table, prefix
        for i in range(1, count + 1):
            assert f"{prefix}.b{i}" in table, (prefix, i)


@pytest.mark.parametrize("lang", ["vi", "en"])
def test_the_words_fit_inside_the_card(app, lang):
    """No sentence runs out of its column and the last line stays above the bottom of the card."""
    i18n.set_lang(lang)
    v = app.help.view
    for i, (prefix, count, _) in enumerate(TOPICS):
        y = 190.0
        for k in range(count):
            lines = hud.wrap(v, i18n.t(f"{prefix}.b{k + 1}"), 19, TEXT_W - 36)
            for line in lines:
                assert hud.text_width(v, line, 19) <= TEXT_W - 36 + 0.5, (lang, prefix, line)
            y += round(19 * 1.4) * (len(lines) + 0.45)
        assert y < CARD.bottom - 24, (lang, i, y)
        title = i18n.t(f"{prefix}.title")
        assert TEXT_X + hud.text_width(v, title, 30, True) < CARD.right - 20, (lang, title)


def test_wrap_breaks_between_words_and_keeps_a_long_word_whole(app):
    v = app.view
    lines = hud.wrap(v, "một hai ba bốn năm sáu bảy tám chín mười", 19, 150)
    assert len(lines) > 1 and " ".join(lines) == "một hai ba bốn năm sáu bảy tám chín mười"
    assert hud.wrap(v, "Siêuiêuiêudài", 19, 20) == ["Siêuiêuiêudài"]
    assert hud.wrap(v, "", 19, 100) == []


# --- pictures: real game frames with marks --------------------------------------------------
@pytest.mark.parametrize("lang", ["vi", "en"])
def test_every_picture_can_be_made_in_both_languages(app, lang):
    i18n.set_lang(lang)
    app.go_help()
    for i in range(len(TOPICS)):
        app.help.page = i
        app.draw()


def test_the_pictures_are_the_size_of_the_art_area():
    v = View(1.0)
    for build in pics.PICTURES:
        w, h = build(v).get_size()
        assert abs(w - pics.ART_W) <= 2 and abs(h - pics.ART_H) <= 2, build.__name__


def _px(pic: pg.Surface, p) -> tuple[int, int, int]:
    return tuple(pic.get_at((round(p[0]), round(p[1]))))[:3]


def test_the_shot_picture_is_a_real_frame_the_ball_the_bar_and_the_step_marks_are_there():
    v = View(1.0)
    pic = pics.picture_cue(v)
    crop_x, crop_y = 60, 190  # the crop used by picture_cue
    cx, cy = to_px(0.62, 0.64)
    cue = _px(pic, (cx - crop_x, cy - crop_y))
    assert min(cue) > 225  # the white ball, drawn by the game
    tip_x = cx - draw.RIM - draw.STICK_GAP - 150 * config.CUE_SHOW_PULL - 3  # the white tip
    tip = max((_px(pic, (tip_x - crop_x + dx, cy - crop_y)) for dx in range(-8, 9)), key=sum)
    assert min(tip) > 200  # the neon cue's white tip, drawn by the game
    step_one = _px(pic, (cx - crop_x - 4, cy - 46 - crop_y - 6))
    assert step_one[0] > 200 and step_one[1] < 140 and step_one[2] > 160  # the pink-violet badge


def test_the_cue_ball_in_hand_picture_shows_the_real_pulsing_ring():
    v = View(1.0)
    pic = pics.picture_hand(v)
    cx, cy = to_px(0.62, 0.64)
    crop_x, crop_y = 60, 250  # the crop used by picture_hand
    # walk right from the ball's centre: the pink-violet ring is a few px outside the ball
    run = [_px(pic, (cx - crop_x + dx, cy - crop_y)) for dx in range(12, 24)]
    assert any(r > 180 and g < 120 and b > 140 for r, g, b in run)  # pink-violet, not night blue


def test_the_result_pictures_are_the_game_s_own_cards(app):
    v = View(1.0)
    scene = pics._pose(v, {0: (0.6, 0.6)})
    assert scene.rules.phase == "playing"  # posing starts a clean game each time
    pic = pics.picture_end(v)
    assert pic.get_width() >= pics.ART_W - 2
    win = _px(pic, (150, 100))  # inside the win card
    assert win != C.PANEL  # not the plain backdrop


def test_the_studio_scene_never_leaves_sound_or_state_behind():
    v = View(1.0)
    scene = pics._pose(v, {0: (0.5, 0.5), 3: (1.0, 0.5)}, pull=(-80, 0))
    assert scene.drag.active and [b.number for b in scene.world.in_play()] == [0, 3]
    again = pics._pose(v, {0: (0.5, 0.5)})
    assert not again.drag.active and [b.number for b in again.world.in_play()] == [0]
