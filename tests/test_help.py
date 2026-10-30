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
from game.scenes.help import TOPICS, dot_rect


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


# --- the motion -------------------------------------------------------------------
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


def test_a_page_turn_slides_one_page_out_and_the_next_in_while_they_fade():
    from game.scenes.help import FLIP_S, FLIP_SLIDE_PX, flip_state

    (ox, oa), (nx, na) = flip_state(0.0, 1)
    assert (
        (ox, oa) == (0.0, 1.0) and na == 0.0 and nx == FLIP_SLIDE_PX
    )  # the new one waits at the right
    (ox, oa), (nx, na) = flip_state(FLIP_S, 1)
    assert (nx, na) == (0.0, 1.0) and oa == 0.0 and ox == -FLIP_SLIDE_PX  # the old one is gone left
    for age in (0.02, 0.07, 0.13, 0.2):
        (ox, oa), (nx, na) = flip_state(age, 1)
        assert oa + na == 1.0 and -FLIP_SLIDE_PX < ox < 0 < nx < FLIP_SLIDE_PX
    back = flip_state(0.1, -1)  # going back is the mirror image
    fwd = flip_state(0.1, 1)
    assert back[0][0] == -fwd[0][0] and back[1][0] == -fwd[1][0]
    assert flip_state(-1.0, 1) == flip_state(0.0, 1) and flip_state(9.0, 1) == flip_state(FLIP_S, 1)


def test_the_slide_goes_the_way_the_arrow_points(app):
    open_help(app)
    layout = help_scene.LAYOUT
    app.handle_event(key(pg.K_RIGHT))
    assert app.help._flip_dir == 1
    app.handle_event(key(pg.K_LEFT))
    assert app.help._flip_dir == -1
    run(app, 0.4)
    app.handle_event(click(layout.next.center))
    assert app.help._flip_dir == 1
    run(app, 0.4)
    app.handle_event(click(layout.prev.center))
    assert app.help._flip_dir == -1
    run(app, 0.4)
    app.handle_event(click(dot_rect(5).center))  # a dot further on: forward
    assert app.help._flip_dir == 1
    run(app, 0.4)
    app.handle_event(click(dot_rect(1).center))  # a dot back: backward
    assert app.help._flip_dir == -1
    run(app, 0.4)
    app.help.page = len(TOPICS) - 1
    app.handle_event(
        key(pg.K_RIGHT)
    )  # past the last page it comes round to the first, still forward
    assert app.help.page == 0 and app.help._flip_dir == 1


def test_while_a_page_turns_nothing_slides_out_of_its_place_on_the_card(app):
    open_help(app)
    layout = help_scene.LAYOUT
    screen = pg.display.get_surface()
    spots = [
        (layout.card.x + 8, layout.content.centery),  # the card's margin, left of the page
        (layout.card.right - 8, layout.content.centery),  # ... and right of it
        (layout.content.centerx, layout.content.y - 6),  # ... and above it
    ]
    at_rest = [tuple(screen.get_at(p)) for p in spots]
    app.handle_event(key(pg.K_RIGHT))
    for _ in range(round(help_scene.FLIP_S * 60)):
        app.update(1 / 60)
        app.draw()
        assert [
            tuple(screen.get_at(p)) for p in spots
        ] == at_rest  # the page is clipped to its place
    assert app.help._flip_at is None


def test_mid_turn_both_pages_are_on_screen_and_the_page_is_not_a_bright_line(app):
    open_help(app)
    content = help_scene.LAYOUT.content
    screen = pg.display.get_surface()
    rest = _bright(screen, content.inflate(-80, 0))
    app.handle_event(key(pg.K_RIGHT))
    run(app, help_scene.FLIP_S / 2)
    mid = pg.image.tobytes(screen, "RGB")
    assert _bright(screen, content.inflate(-80, 0)) < rest * 3 + 6000  # not the old CRT line
    run(app, help_scene.FLIP_S)
    assert pg.image.tobytes(screen, "RGB") != mid  # and it does settle on something else


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


# --- making the pages ahead of time ---------------------------------------------------------
def test_the_pages_are_made_ahead_one_at_a_time_while_the_card_stands_still(app):
    app.help.prefetch = True
    open_help(app)
    run(app, 0.5)  # the card stands still: it makes the rest, one a frame
    assert len(app.help._pages) == len(TOPICS)
    assert app.help.prefetch_one() is False  # nothing left to make


def test_the_first_page_is_made_while_the_menu_idles_so_opening_does_not_stall(app):
    app.help.prefetch = True
    assert not app.help._pages
    run(app, 1.0)
    assert not app.help._pages  # the menu has only just opened: the title is still lighting up
    run(app, 1.5)
    assert any(page == 0 for page, _ in app.help._pages)


def test_nothing_is_made_ahead_when_the_option_is_off(app):
    run(app, 3.0)
    assert not app.help._pages


# --- everything is made once, at start-up, behind the loading line --------------------------------
def test_prepare_makes_every_page_the_settings_panel_and_the_result_card_at_once(app):
    from game.render import hud

    app.help.prefetch = True
    app.prepare()
    assert len(app.help._pages) == len(TOPICS)
    assert app.menu.settings._warm == app.view.s
    assert hud._result_warm[0] == app.view.s


def test_after_prepare_the_idle_menu_has_nothing_left_to_make_so_it_never_stalls(app):
    app.help.prefetch = True
    app.prepare()
    made = []
    real = app.help._make_page
    app.help._make_page = lambda i: made.append(i) or real(i)
    run(app, 4.0)  # long past the 1.5 s the menu used to wait before making them
    assert made == []
