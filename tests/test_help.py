"""The how-to-play card: opening and closing it, its pages, its words, its real pictures."""

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
from game.scenes.help import FLIP_OFF_S, FLIP_ON_S, TOPICS, dot_rect


@pytest.fixture(params=list(help_scene.LAYOUTS))
def app(request, monkeypatch):
    """Every test runs on every layout: the two differ only in where things stand."""
    monkeypatch.setattr(help_scene, "LAYOUT", help_scene.LAYOUTS[request.param])
    pg.init()
    a = App(pg.display.set_mode(config.LOGICAL_SIZE))
    yield a
    pg.quit()
    i18n.set_lang("vi")


def key(k):
    return pg.event.Event(pg.KEYDOWN, key=k)


def click(pos):
    return pg.event.Event(pg.MOUSEBUTTONDOWN, pos=pos, button=1)


def run(app, seconds):
    """Let `seconds` of game time pass, drawing every frame."""
    for _ in range(round(seconds * 60)):
        app.update(1 / 60)
        app.draw()


def open_help(app):
    app.open_help()
    run(app, 0.6)  # the card has opened out
    assert app.help.k == 1.0


# --- getting in and out ---------------------------------------------------------------------
def test_the_menu_has_a_how_to_play_button_that_opens_the_card_over_the_menu(app):
    app.handle_event(key(pg.K_DOWN))  # play -> how to play
    app.handle_event(key(pg.K_RETURN))
    assert app.help.is_open and app.scene is app.menu  # no other screen: the menu stays behind


def test_escape_closes_the_card_and_the_menu_is_still_there(app):
    open_help(app)
    app.handle_event(key(pg.K_ESCAPE))
    assert app.help.is_open  # it folds back into its line first ...
    run(app, help_scene.CLOSE_S + 0.1)
    assert not app.help.is_open and app.scene is app.menu  # ... and then it is gone


def test_h_in_a_game_opens_the_card_over_the_table_and_the_game_waits(app):
    app.go_play()
    app.skip_transition()
    app.play.rules.shots = 3
    app.handle_event(key(pg.K_h))
    assert app.help.is_open and app.scene is app.play
    open_help(app)
    clock = app.play._clock
    run(app, 0.5)
    assert app.play._clock == clock  # the table is paused behind the card
    app.handle_event(key(pg.K_h))  # H again closes it
    run(app, help_scene.CLOSE_S + 0.1)
    assert not app.help.is_open and app.play.rules.shots == 3
    app.update(1 / 60)
    assert app.play._clock > clock  # and the game goes on


def test_opening_the_card_cancels_an_aim_in_progress(app):
    app.go_play()
    app.play.drag.begin((100, 100))
    app.handle_event(key(pg.K_h))
    assert not app.play.drag.active


def test_while_the_card_is_open_the_scene_behind_gets_no_keys_and_no_clicks(app):
    open_help(app)
    sel = app.menu.sel
    app.handle_event(key(pg.K_DOWN))
    app.handle_event(click(app.menu._rects()[3].center))  # the Quit button is under the card
    assert app.menu.sel == sel and app.running


def test_the_side_panel_lists_the_help_key():
    assert "hud.key_help" in [what for _, what in hud.PANEL_KEYS]
    assert all(cap.startswith("keycap.") for cap, _ in hud.PANEL_KEYS)


# --- pages ----------------------------------------------------------------------------------
def test_pages_turn_with_keys_and_go_round_at_both_ends(app):
    open_help(app)
    h = app.help
    app.handle_event(key(pg.K_LEFT))
    assert h.page == len(TOPICS) - 1  # before the first comes the last
    app.handle_event(key(pg.K_RIGHT))
    assert h.page == 0  # and after the last comes the first
    for _ in range(len(TOPICS) + 2):
        app.handle_event(key(pg.K_RIGHT))
    assert h.page == 2


def test_pages_turn_with_the_arrows_and_the_dots(app):
    open_help(app)
    layout = help_scene.LAYOUT
    app.handle_event(click(layout.next.center))
    assert app.help.page == 1
    app.handle_event(click(layout.prev.center))
    assert app.help.page == 0
    app.handle_event(click(dot_rect(4).center))
    assert app.help.page == 4


def test_the_close_button_and_a_click_outside_the_card_close_it_but_a_click_on_it_does_not(app):
    open_help(app)
    layout = help_scene.LAYOUT
    app.handle_event(click(layout.card.center))
    run(app, 0.4)
    assert app.help.is_open and app.help.k == 1.0
    app.handle_event(click(layout.close.center))
    run(app, help_scene.CLOSE_S + 0.1)
    assert not app.help.is_open
    open_help(app)
    app.handle_event(click((layout.card.x - 90, layout.card.y - 20)))  # on the dark
    run(app, help_scene.CLOSE_S + 0.1)
    assert not app.help.is_open


def test_the_card_stays_where_you_left_off(app):
    open_help(app)
    app.handle_event(key(pg.K_RIGHT))
    app.handle_event(key(pg.K_ESCAPE))
    run(app, 0.5)
    open_help(app)
    assert app.help.page == 1


def test_arrows_and_the_close_button_light_up_under_the_pointer(app):
    open_help(app)
    layout = help_scene.LAYOUT
    app.handle_event(
        pg.event.Event(pg.MOUSEMOTION, pos=layout.next.center, rel=(0, 0), buttons=(0,) * 3)
    )
    run(app, 0.3)
    assert app.help.fx.lit["next"] == 1.0 and app.help.fx.lit["prev"] == 0.0


# --- the tube-like motion -------------------------------------------------------------------
def _bright(screen, rect, step=6):
    return sum(sum(screen.get_at((x, rect.centery))[:3]) for x in range(rect.x, rect.right, step))


def test_the_card_opens_out_of_a_bright_line_in_its_middle(app):
    card = help_scene.LAYOUT.card
    app.open_help()
    app.update(0.03)
    app.draw()
    screen = pg.display.get_surface()
    assert 0.0 < app.help.k < 0.3
    line = _bright(screen, card.inflate(-60, 0))  # along the middle of the card
    above = sum(
        sum(screen.get_at((x, card.y + 24))[:3]) for x in range(card.x + 30, card.right - 30, 6)
    )
    assert line > above + 3000  # a lit line, with the dark of the scene above it
    run(app, 0.5)
    assert app.help.k == 1.0


def test_turning_a_page_folds_the_old_one_into_a_line_and_opens_the_new_one(app):
    open_help(app)
    content = help_scene.LAYOUT.content
    screen = pg.display.get_surface()
    app.handle_event(key(pg.K_RIGHT))
    assert app.help._flip_at is not None
    run(app, FLIP_OFF_S - 0.01)  # the old page has all but folded away
    thin = _bright(screen, content.inflate(-80, 0))
    top = sum(
        sum(screen.get_at((x, content.y + 20))[:3])
        for x in range(content.x + 60, content.right - 60, 6)
    )
    assert thin > top + 3000
    run(app, FLIP_ON_S + 0.1)
    assert app.help._flip_at is None  # the new page is whole again


def test_keys_pressed_while_a_page_turns_still_count(app):
    open_help(app)
    for _ in range(3):
        app.handle_event(key(pg.K_RIGHT))
        run(app, 0.05)
    assert app.help.page == 3


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
    """No sentence runs out of its column and the last line stays above the bottom of the page."""
    i18n.set_lang(lang)
    v, layout = app.help.view, help_scene.LAYOUT
    size = layout.text_size
    for i, (prefix, count, _) in enumerate(TOPICS):
        y = layout.text[1]
        for k in range(count):
            lines = hud.wrap(v, i18n.t(f"{prefix}.b{k + 1}"), size, layout.text_w - 30)
            for line in lines:
                assert hud.text_width(v, line, size) <= layout.text_w - 30 + 0.5, (
                    lang,
                    prefix,
                    line,
                )
            y += round(size * 1.5) * (len(lines) + 0.45)
        y -= round(size * 1.5) * 0.45  # no gap after the last sentence
        assert y < layout.content.bottom - 8, (lang, i, y)
        title = i18n.t(f"{prefix}.title")
        right = layout.title[0] + hud.text_width(v, title, layout.title_size, True)
        assert right < layout.card.right - 20, (lang, title)


def test_wrap_breaks_between_words_and_keeps_a_long_word_whole(app):
    v = app.view
    lines = hud.wrap(v, "một hai ba bốn năm sáu bảy tám chín mười", 19, 150)
    assert len(lines) > 1 and " ".join(lines) == "một hai ba bốn năm sáu bảy tám chín mười"
    assert hud.wrap(v, "Siêuiêuiêudài", 19, 20) == ["Siêuiêuiêudài"]
    assert hud.wrap(v, "", 19, 100) == []


def test_the_card_sits_inside_the_screen_with_room_for_its_arrows(app):
    w, h = config.LOGICAL_SIZE
    layout = help_scene.LAYOUT
    for r in (layout.card, layout.prev, layout.next, layout.close):
        assert 0 <= r.x and r.right <= w and 0 <= r.y and r.bottom <= h, r
    assert layout.card.contains(layout.close) and layout.card.contains(layout.content)


# --- pictures: real game frames with marks --------------------------------------------------
@pytest.mark.parametrize("lang", ["vi", "en"])
def test_every_picture_can_be_made_in_both_languages(app, lang):
    i18n.set_lang(lang)
    app.open_help()
    for i in range(len(TOPICS)):
        app.help.page = i
        app.update(1 / 60)
        app.draw()


def test_the_pictures_are_the_size_of_the_art_area():
    v = View(1.0)
    for build in pics.PICTURES:
        w, h = build(v).get_size()
        assert abs(w - pics.ART_W) <= 2 and abs(h - pics.ART_H) <= 2, build.__name__


def test_the_pictures_are_made_small_not_shrunk_from_big_ones(app):
    """The card shows a picture at its own size: made at that scale, so lines stay sharp."""
    k = help_scene.LAYOUT.art_k
    pic = pics.build(0, View(k))
    assert (
        abs(pic.get_width() - pics.ART_W * k) <= 2 and abs(pic.get_height() - pics.ART_H * k) <= 2
    )


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
    run_ = [_px(pic, (cx - crop_x + dx, cy - crop_y)) for dx in range(12, 24)]
    assert any(r > 180 and g < 120 and b > 140 for r, g, b in run_)  # pink-violet, not night blue


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
