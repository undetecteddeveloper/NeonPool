"""tools/dev.py: every state runs, and the ones that promise a place really get there."""

import pygame as pg
import pytest

from game import config, i18n
from game.app import App
from game.rules.eight_ball import LOST, WON
from game.scenes import play_panel as pp
from tools.devkit.check import DT, frames, run_check
from tools.devkit.harness import Harness
from tools.devkit.overlay import DevPanel
from tools.devkit.states import STATES, by_name


@pytest.fixture
def dev():
    pg.init()
    screen = pg.display.set_mode(config.LOGICAL_SIZE)
    app = App(screen)
    app.change_settings(lang="vi", show_fps=False)
    harness = Harness(app)
    yield app, harness
    harness.reset()
    pg.quit()
    i18n.set_lang("vi")


def go(dev_, name, seconds=0.0):
    app, h = dev_
    st = by_name(name)
    assert st is not None, name
    st.run(h)
    app.skip_transition()
    frames(app, h, round(seconds / DT))


def until(dev_, cond, seconds=30.0):
    app, h = dev_
    for _ in range(round(seconds / DT)):
        if cond():
            return True
        frames(app, h, 1)
    return cond()


def test_every_state_runs_and_draws_without_an_error():
    pg.init()
    app = App(pg.display.set_mode(config.LOGICAL_SIZE))
    bad = run_check(app, count=20)
    pg.quit()
    i18n.set_lang("vi")
    assert bad == []
    assert len(STATES) >= 60
    assert len({s.name for s in STATES}) == len(STATES)  # names are what people type: unique


def test_the_panels_and_help_pages_are_where_their_names_say(dev):
    app, h = dev
    go(dev, "Bảng Chơi: chờ bạn vào")
    assert app.menu.play_panel.is_open and app.menu.play_panel.step == pp.HOSTING
    assert app.menu.play_panel.room.code == "KXQM"
    go(dev, "Bảng Chơi: mã lỗi")
    assert app.menu.play_panel.step == pp.JOINING and app.menu.play_panel.error == "net.err.no_room"
    go(dev, "Cài đặt")
    assert app.menu.settings.is_open and not app.menu.play_panel.is_open
    go(dev, "Hướng dẫn trang 7")
    assert app.help.is_open and app.help.page == 6
    go(dev, "Menu")
    assert not app.help.is_open and app.scene is app.menu


def test_solo_endings_come_out_as_they_are_named(dev):
    app, _ = dev
    go(dev, "Thẻ THẮNG")
    assert until(dev, lambda: app.play.rules.phase != "playing", 20)
    assert app.play.rules.phase == WON
    go(dev, "Thẻ THUA")
    assert until(dev, lambda: app.play.rules.phase != "playing", 20)
    assert app.play.rules.phase == LOST
    go(dev, "Lỗi: bi trắng trong tay")
    assert until(dev, lambda: app.play.rules.cue_in_hand, 20)


@pytest.mark.parametrize(
    ("name", "phase"),
    [
        ("Tôi THẮNG: bot bỏ bi 8 sớm", WON),
        ("Tôi THUA: tôi bỏ bi 8 sớm", LOST),
        ("Tôi THẮNG: bot đầu hàng", WON),
        ("Tôi THUA: tôi đầu hàng", LOST),
    ],
)
def test_two_player_endings_come_out_as_they_are_named(dev, name, phase):
    app, _ = dev
    go(dev, name)
    assert until(dev, lambda: app.net is not None and app.net._result_shown, 40)
    assert app.net.rules.phase == phase


def test_a_rematch_state_makes_a_new_game_and_keeps_the_score(dev):
    app, h = dev
    go(dev, "Đấu lại: cả hai đã bấm")
    assert until(dev, lambda: app.net is not None and app.net.session.game_no == 2, 15)
    assert not app.net.session.match.over
    assert sum(app.net.session.wins) == 1


def test_the_rematch_buttons_show_each_waiting_state(dev):
    app, h = dev
    go(dev, "Thẻ kết quả: bot đã bấm Đấu lại trước")
    assert until(dev, lambda: app.net._rematch_state() == "they_asked", 10)
    go(dev, "Thẻ kết quả: tôi đã bấm Đấu lại")
    assert until(dev, lambda: app.net._rematch_state() == "wait", 10)
    go(dev, "rồi bot rời phòng")
    assert until(dev, lambda: app.net._rematch_state() == "gone", 10)


def test_cutting_and_mending_the_link_shows_and_hides_its_card(dev):
    app, h = dev
    go(dev, "Tôi là chủ phòng, tôi phá", 3.0)
    go(dev, "Cắt mạng")
    assert until(dev, lambda: app.net._card_showing() == "link", 10)
    go(dev, "Nối mạng lại")
    assert until(dev, lambda: app.net._card_showing() is None and app.net.session.linked, 10)


def test_a_link_with_seconds_left_runs_out_and_the_game_is_lost_or_won(dev):
    app, h = dev
    go(dev, "Tôi là chủ phòng, tôi phá", 3.0)
    go(dev, "Rớt mạng còn 3 giây")
    assert until(dev, lambda: app.net._result_shown, 20)
    assert app.net.rules.phase == WON  # the host wins when the guest is gone too long


def test_the_clock_states_set_the_clock_for_the_right_player(dev):
    app, h = dev
    go(dev, "Đồng hồ của tôi còn 5 giây")
    assert until(dev, lambda: h.mine.my_turn and h.mine.turn_left_s <= 5.5, 15)
    go(dev, "Đồng hồ của bot còn 12 giây")
    assert until(dev, lambda: not h.mine.my_turn and h.mine.turn_left_s <= 12.5, 15)


def test_the_bot_plays_by_itself_when_asked_and_once_when_told(dev):
    app, h = dev
    go(dev, "Tôi là chủ phòng, bot phá", 3.0)
    before = h.fake.shots_started
    go(dev, "Bot đánh một cú ngay")
    assert until(dev, lambda: h.fake.shots_started > before, 15)
    assert not h.bot.auto
    go(dev, "Bot tự chơi")
    assert h.bot.auto


def test_the_bot_places_the_cue_ball_when_it_has_it_in_hand(dev):
    app, h = dev
    go(dev, "Tôi phạm lỗi", 1.0)
    assert until(dev, lambda: h.fake.can_place or h.fake.match.cue_in_hand, 30)
    h.bot.auto = True
    assert until(dev, lambda: not h.fake.match.cue_in_hand and h.fake.shots_started >= 2, 40)


def test_the_cards_and_reactions_states(dev):
    app, h = dev
    go(dev, "Thẻ Esc")
    assert app.net._card_showing() == "esc"
    go(dev, "Thẻ Đầu hàng?")
    assert app.net._card_showing() == "sure"
    go(dev, "Bot biểu cảm: GG", 0.3)
    assert h.mine.take_emotes() or app.net._bubbles
    go(dev, "Tỉ số phòng 2 : 1", 0.2)
    assert app.net._wins() == (2, 1)


def test_display_states_change_the_language_the_speed_and_the_window(dev):
    app, h = dev
    go(dev, "Ngôn ngữ")
    assert app.settings.lang == "en" and i18n.get_lang() == "en"
    go(dev, "Ngôn ngữ")
    assert app.settings.lang == "vi"
    go(dev, "Tốc độ")
    assert h.speed == 4.0
    go(dev, "Cỡ cửa sổ 1050×590")
    assert pg.display.get_surface().get_size() == (1050, 590)
    go(dev, "Cỡ cửa sổ 1280×720")


def test_the_panel_opens_runs_a_state_and_survives_a_broken_one(dev):
    app, h = dev
    panel = DevPanel(h)
    window = app.screen.get_size()
    key = lambda k: pg.event.Event(pg.KEYDOWN, key=k)  # noqa: E731
    assert not panel.handle_event(
        pg.event.Event(pg.KEYDOWN, key=pg.K_a), window
    )  # closed: not taken
    assert panel.handle_event(key(pg.K_F1), window) and panel.is_open
    panel.handle_event(key(pg.K_DOWN), window)
    panel.handle_event(key(pg.K_RETURN), window)
    assert not panel.is_open and panel.ok and panel.last == 1
    assert panel.handle_event(key(pg.K_F2), window)  # F2 repeats it
    broken = DevPanel(h, [STATES[0].__class__("g", "boom", lambda _h: 1 / 0)])
    assert broken.run(0) is False and not broken.ok and "boom" in broken.message
    broken.is_open = True
    broken.draw(app.screen)  # and it can still be drawn
    panel.is_open = True
    panel.draw(app.screen)


def test_the_hotkeys_reach_the_fake_opponent(dev):
    app, h = dev
    panel = DevPanel(h)
    assert panel.hotkey(pg.K_F3) and h.bot.auto  # starts a game if there is none
    assert h.in_net
    frames(app, h, 200)
    assert panel.hotkey(pg.K_F4)  # cut
    assert until(dev, lambda: h.mine.link_down_s is not None, 5)
    assert panel.hotkey(pg.K_F4)  # mend
    assert until(dev, lambda: h.mine.linked, 10)
    assert panel.hotkey(pg.K_F6)
    assert h.mine.turn_left_s <= 10.5
    assert panel.hotkey(pg.K_F7)  # the start of the game once more, from the look at the table
    assert (
        not app.net._toss_done()
        and app.net._toss.phase(app.net._clock - app.net._started_at) == "lead"
    )
    assert h.mine._toss_left == h.fake._toss_left > 4.0
    assert not panel.hotkey(pg.K_F9)
