"""tools/dev.py: every state runs, and the ones that promise a place really get there."""

import pygame as pg
import pytest

from game import config, i18n
from game.app import App
from game.net import toss
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


def test_practice_endings_come_out_as_they_are_named(dev):
    app, _ = dev
    go(dev, "Luyện tập: ván mới")
    assert app.practice.rules.target is None and app.practice.rules.streak == 0
    go(dev, "Giữa chuỗi (đã qua 5 bi)")
    assert (app.practice.rules.streak, app.practice.rules.target) == (5, 6)
    assert app.practice.rules.lives == 2
    go(dev, "Thắng (chạy hết 15 bi")
    assert until(dev, lambda: app.practice.rules.phase != "playing", 20)
    assert app.practice.rules.phase == WON and app.practice.rules.streak == 15
    go(dev, "Thua (hết mạng")
    assert until(dev, lambda: app.practice.rules.phase != "playing", 20)
    assert app.practice.rules.phase == LOST


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


def test_ac24_my_dial_is_told_to_the_other_player_and_theirs_is_shown_to_me(dev):
    app, h = dev
    go(dev, "Sau tung xu, tới lượt tôi", seconds=0.5)
    me, them = app.net.session, h.fake.remote_cue
    assert me.can_shoot and not them.tuning_spin
    app.net._set_spin(0.5, press=True)  # the dot of the dial is set (a wheel turn does as much)
    frames(app, h, round(0.5 / DT))
    assert them.tuning_spin
    frames(app, h, round(3.0 / DT))  # nothing more: the line goes out by itself
    assert not them.tuning_spin
    app.net._dial_drag = True  # the dot is held still for a long time: still told
    frames(app, h, round(4.0 / DT))
    assert them.tuning_spin
    app.net._dial_drag = False
    frames(app, h, round(3.0 / DT))
    assert not them.tuning_spin
    go(dev, "Bot đang chỉnh xoáy (giữ nguyên)", seconds=4.0)
    assert app.net.session.remote_cue.tuning_spin and not app.net.session.my_turn
    frames(app, h, round(0.2 / DT))
    assert i18n.t("net.spin_them", name="Bot") == "Bot đang chỉnh xoáy…"
    go(dev, "Bot thôi chỉnh xoáy", seconds=3.0)
    assert not app.net.session.remote_cue.tuning_spin


def test_ac25_the_ping_line_shows_dashes_then_the_round_trip_in_a_colour_of_its_quality(dev):
    from game.render import hud

    app, h = dev
    go(dev, "Sau tung xu, tới lượt tôi", seconds=0.2)
    s = app.net.session
    assert i18n.t("net.ping", ms="--") == "Ping -- ms" and i18n.t("net.ping", ms=48) == "Ping 48 ms"
    assert hud.ping_colour(None) != hud.ping_colour(10)
    colours = [hud.ping_colour(ms) for ms in (10, config.NET_PING_GOOD_MS - 1, 61, 120, 121, 900)]
    assert colours[0] == colours[1] != colours[2] == colours[3] != colours[4] == colours[5]
    frames(app, h, round(2.5 / DT))
    assert s.rtt_s is not None  # a ping goes every second: the number is there
    h.set_latency(0.2)  # a bad line (a 0.2 s trip each way)
    frames(app, h, round(8.0 / DT))
    assert s.rtt_s > 0.25 and hud.ping_colour(round(s.rtt_s * 1000)) == hud.ping_colour(900)


@pytest.mark.parametrize("state", ["Tôi là chủ phòng, tôi phá", "Tôi là chủ phòng, bot phá"])
def test_ac27_no_plate_is_lit_until_the_coin_has_landed(dev, monkeypatch, state):
    """Found by the user (2026-10-31): the plate of whoever breaks was lit from the first frame of
    the toss, so the coin told nothing. Every frame is looked at, both for the first game and for a
    rematch (whose lead is longer)."""
    from game.render import hud

    app, h = dev
    lit: list[bool] = []
    real = hud.name_plate

    def spy(canvas, v, rect, name, group_s, left, *, turn):
        lit.append(turn)
        return real(canvas, v, rect, name, group_s, left, turn=turn)

    monkeypatch.setattr(hud, "name_plate", spy)
    go(dev, state)
    for again in (False, True):
        scene = app.net
        scene._toss = toss.Toss(again, scene._toss.breaker)  # (the rematch's longer lead)
        h.replay_toss()
        frames(app, h, 1)
        landed = scene._toss.land_at
        before_landing, after_landing = [], []
        while scene._clock - scene._started_at < landed + 0.6:
            age = scene._clock - scene._started_at
            lit.clear()
            frames(app, h, 1)
            (after_landing if age + DT >= landed else before_landing).append(any(lit))
        assert before_landing and not any(before_landing)
        assert after_landing and all(
            after_landing[-5:]
        )  # and from the landing the player on turn is lit
