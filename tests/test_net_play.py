"""The Play panel and the two-player table: two games meet by room code through a relay on
127.0.0.1 (`server/local_relay.py`), then straight over a socket (the same machine is the same
network)."""

import math
import re
import socket
import time

import pygame as pg
import pytest

from game import config, i18n
from game.app import App
from game.net import relay, toss
from game.net import session as net_session
from game.physics import Shot
from game.render import hud
from game.render.layout import OUTER_X, to_px
from game.rules.eight_ball import LOST, PLAYING, WON
from game.scenes import play_panel as pp
from game.scenes.net_play import TABLE_RECT, NetPlayScene
from server.local_relay import Relay


def key(k):
    return pg.event.Event(pg.KEYDOWN, key=k)


def typed(text):
    return pg.event.Event(pg.TEXTINPUT, text=text)


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def relay_server(monkeypatch):
    server = Relay()
    monkeypatch.setenv("NEONPOOL_RELAY_URL", server.url)
    yield server
    server.close()


@pytest.fixture
def apps(monkeypatch, tmp_path, relay_server):
    monkeypatch.setenv("NEONPOOL_NET_PORT", str(free_port()))
    monkeypatch.setenv("NEONPOOL_SETTINGS", str(tmp_path / "settings.json"))
    pg.init()
    screen = pg.display.set_mode(config.LOGICAL_SIZE)
    host, guest = App(screen), App(screen)
    for a in (host, guest):
        a.skip_transition()
    yield host, guest
    for a in (host, guest):
        if a.net is not None:
            a.net.leave()
    pg.quit()
    i18n.set_lang("vi")


def run(apps_, until, seconds=15.0, dt=1 / 60):
    """Let both games run (their sockets work in threads) until `until()` or the time is up."""
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        for a in apps_:
            a.update(dt)
            a.draw()
        if until():
            return True
        time.sleep(0.001)
    return False


def meet(apps_, seconds=15.0):
    """The host makes a room, the guest types its code; True once both are at the table."""
    host, guest = apps_
    hp, gp = host.menu.play_panel, guest.menu.play_panel
    hp.open()
    hp.name = "Hoa"
    hp._start_hosting()
    assert run([host], lambda: hp.room.code != "", seconds)
    gp.open()
    gp.name, gp.code = "Nam", hp.room.code
    gp._start_joining()
    return run(apps_, lambda: host.net is not None and guest.net is not None, seconds)


def settled(host, guest):
    return all(a.net.session.settled for a in (host, guest))


def after_the_toss(apps_):
    host, guest = apps_

    def done():
        return host.net._toss_done() and guest.net._toss_done() and settled(host, guest)

    return run(apps_, done)


def players(apps_):
    """The scene of the player on turn, and the other one."""
    host, guest = apps_
    first = host.net if host.net.session.my_turn else guest.net
    return first, guest.net if first is host.net else host.net


# --- the panel ---
def test_play_opens_a_panel_with_solo_first_and_two_players_next(apps):
    host, _ = apps
    host.handle_event(key(pg.K_RETURN))
    panel = host.menu.play_panel
    assert panel.is_open and panel.step == pp.CHOOSE and panel._item() == "solo"
    host.handle_event(key(pg.K_DOWN))
    host.handle_event(key(pg.K_RETURN))
    assert panel.step == pp.SETUP and panel._item() == "name"  # no name yet: the field first
    host.handle_event(key(pg.K_ESCAPE))
    assert panel.step == pp.CHOOSE
    host.handle_event(key(pg.K_ESCAPE))
    for _ in range(30):
        host.update(1 / 60)
    assert not panel.is_open and host.scene is host.menu


def test_typing_a_name_goes_into_the_field_and_m_does_not_mute(apps):
    host, _ = apps
    host.handle_event(key(pg.K_RETURN))
    host.handle_event(key(pg.K_DOWN))
    host.handle_event(key(pg.K_RETURN))
    host.handle_event(typed("Lan"))
    host.handle_event(key(pg.K_m))  # the key reaches the app first: it must stay out of a field
    host.handle_event(typed("m" + "x" * 40))
    panel = host.menu.play_panel
    assert panel.name.startswith("Lanm") and len(panel.name) == config.NET_NAME_MAX
    assert not host.audio.muted and panel.typing
    host.handle_event(key(pg.K_BACKSPACE))
    assert len(panel.name) == config.NET_NAME_MAX - 1


def test_the_name_is_saved_when_a_room_is_made_and_comes_back_next_time(apps):
    host, _ = apps
    panel = host.menu.play_panel
    panel.open()
    panel.name = "  Lan Anh "
    panel._start_hosting()
    assert host.settings.player_name == "Lan Anh"
    panel.dismiss()
    panel.open()
    assert panel.name == "Lan Anh"


def test_a_room_shows_its_code_once_the_relay_gives_it(apps):
    host, _ = apps
    panel = host.menu.play_panel
    panel.open()
    panel._start_hosting()
    assert panel.step == pp.HOSTING
    assert run([host], lambda: panel.room.code != "")
    assert relay.is_code(panel.room.code) and panel.room.door is not None


def test_ac23_a_short_code_is_refused_on_the_spot_and_a_wrong_one_says_so(apps):
    host, _ = apps
    panel = host.menu.play_panel
    panel.open()
    panel._goto(pp.JOINING)
    panel.code = "KX"
    panel._start_joining()
    assert panel.error == "net.err.bad_code" and panel.step == pp.JOINING
    host.handle_event(typed("q-m"))  # the fourth letter goes in: off it goes at once
    assert panel.code == "KXQM" and panel.step == pp.CONNECTING
    assert run([host], lambda: panel.step == pp.JOINING)
    assert panel.error == "net.err.no_room"
    host.handle_event(typed("z"))  # (the code is full: a fifth letter does not try again)
    assert panel.step == pp.JOINING and panel.code == "KXQM"
    host.handle_event(key(pg.K_BACKSPACE))
    assert panel.code == "KXQ" and panel.error is None


def test_ac23_no_internet_is_said_on_both_sides(apps, monkeypatch):
    host, guest = apps
    monkeypatch.setenv("NEONPOOL_RELAY_URL", "ws://127.0.0.1:9")
    hp, gp = host.menu.play_panel, guest.menu.play_panel
    hp.open()
    hp._start_hosting()
    assert run([host], lambda: hp.step == pp.SETUP)
    assert hp.error == "net.err.offline" and hp.room is None
    gp.open()
    gp._goto(pp.JOINING)
    gp.code = "KXQM"
    gp._start_joining()
    assert run([guest], lambda: gp.step == pp.JOINING) and gp.error == "net.err.offline"


# --- two games meeting ---
def test_two_games_meet_through_the_panel_and_both_open_the_table(apps):
    host, guest = apps
    assert meet(apps)
    assert isinstance(host.net, NetPlayScene) and host.scene is host.net
    assert host.net.session.names == guest.net.session.names == ["Hoa", "Nam"]
    assert host.net.session.breaker == guest.net.session.breaker
    assert not host.menu.play_panel.is_open and host.menu.play_panel.room is None


def test_a_guest_with_another_build_gets_the_update_message(apps, monkeypatch):
    host, guest = apps
    real = net_session.Session

    def other_build(transport, is_host, name, **kw):
        return real(transport, is_host, name, **({**kw, "build": "9.9"} if not is_host else kw))

    monkeypatch.setattr(pp.net_session, "Session", other_build)
    assert not meet(apps, seconds=3.0)
    assert run(apps, lambda: guest.menu.play_panel.error == "net.err.version", seconds=8)
    assert guest.net is None and guest.menu.play_panel.step == pp.JOINING
    assert host.net is None and host.menu.play_panel.room is not None  # the room stays open


def test_the_coin_toss_comes_first_and_nobody_can_shoot_until_it_is_done(apps):
    host, guest = apps
    assert meet(apps)
    for a in (host, guest):
        assert not a.net._can_aim() and not a.net._dial_ok()
    assert after_the_toss(apps)
    first, other = players(apps)
    assert first._can_aim() and not other._can_aim()
    assert first.session.breaker == first.session.match.turn
    assert first._toss.total_s == toss.total_s(False) > 4.0  # long enough to see the names first


def test_a_shot_is_seen_on_the_other_table_and_the_turn_goes_by_the_rules(apps):
    host, guest = apps
    assert meet(apps) and after_the_toss(apps)
    first, other = players(apps)
    first.fire(Shot(math.pi, 0.1, 0.0))  # a soft miss from the head spot: a foul
    assert run(apps, lambda: other.session.checkpoints >= 1 and settled(host, guest))
    assert other.session.match.turn == other.session.me and other.session.match.cue_in_hand
    assert other.rules.cue_in_hand and other._holding() and not first._holding()
    assert other.rules.phase == PLAYING and first.rules.fouls == 1 and other.rules.fouls == 0
    lines = [s for s, _ in other._banner_lines()]
    assert any(i18n.t("notice.hand_drag") in s for s in lines)


def test_the_cue_ball_in_hand_makes_the_pick_up_and_put_down_sounds_in_a_two_player_game(apps):
    host, guest = apps
    assert meet(apps) and after_the_toss(apps)
    first, other = players(apps)
    first.fire(Shot(math.pi, 0.1, 0.0))  # a soft miss: a foul, the other has the ball in hand
    assert run(apps, lambda: other.session.checkpoints >= 1 and settled(host, guest))
    heard = []
    other.app.audio.play_cue_pick = lambda: heard.append("pick")
    other.app.audio.play_cue_put = lambda: heard.append("put")
    cue = other.world.balls[0]
    for kind, (x, y) in ((pg.MOUSEBUTTONDOWN, (cue.x, cue.y)), (pg.MOUSEBUTTONUP, (1.0, 0.4))):
        px = tuple(round(v) for v in to_px(x, y))
        other.handle_event(pg.event.Event(kind, pos=px, button=1))
    assert heard == ["pick", "put"]


def test_the_other_players_cue_shows_while_they_aim(apps):
    host, guest = apps
    assert meet(apps) and after_the_toss(apps)
    first, other = players(apps)
    first.drag.begin((300, 300))
    first.drag.move((250, 330))  # pulled back: the cue is out
    assert run(apps, lambda: other._remote_alpha > 0.5 and other.session.remote_cue.pull > 0)
    first.drag.cancel()
    assert run(apps, lambda: other._remote_alpha < 0.05 and not other.session.remote_cue.visible)


def finish_with_the_8_early(apps_):
    """Play a soft miss (so the break is over), then set the table so that whoever is on turn
    sinks the 8 at once and so loses."""
    host, guest = apps_
    first, other = players(apps_)
    first.fire(Shot(math.pi, 0.1, 0.0))
    run(apps_, lambda: settled(host, guest) and other.session.checkpoints >= 1)
    other.session.place_cue(1.0, 0.4)  # the foul gave them the cue ball in hand
    other.session.release_cue()
    run(apps_, lambda: other.session.can_shoot and not host.net.session.match.cue_in_hand)
    balls = host.net.world.in_play()
    aside = {b.number: (0.35 + 0.09 * i, 1.15) for i, b in enumerate(balls) if b.number}
    aside.update({8: (0.2, 0.2), 0: (0.6, 0.6)})
    host.net.session.reset_table(aside)
    run(apps_, lambda: settled(host, guest)
        and guest.net.session.checkpoints == host.net.session.checkpoints)  # fmt: skip
    other.fire(Shot(-3 * math.pi / 4, 0.7, 0.0))
    return other, first


def test_the_game_ends_with_a_card_for_each_player_and_both_cards_count_up(apps):
    host, guest = apps
    assert meet(apps) and after_the_toss(apps)
    loser, winner = finish_with_the_8_early(apps)
    assert run(apps, lambda: host.net._result_shown and guest.net._result_shown)
    assert loser.rules.phase == LOST and winner.rules.phase == WON
    age = lambda: host.net._clock - host.net._ended_at  # noqa: E731
    assert run(
        apps, lambda: all(tl.finished("fouls", age()) for tl in host.net._tallies), seconds=8
    )
    values, _ = winner._result_numbers()
    m = winner.session.match
    mine, theirs = winner._me, winner._them
    assert [row[0] for row in values] == [m.score(mine), m.shots[mine], m.fouls[mine]]
    assert [row[1] for row in values] == [m.score(theirs), m.shots[theirs], m.fouls[theirs]]
    assert values[0][0] > values[0][1]  # the winner has the better score
    reason, won = winner._result_words()
    assert won and winner._name(winner._them) in reason  # "<name> sank the 8 ..."
    for app in (host, guest):
        for _ in range(5):
            app.draw()


def test_the_result_card_button_goes_back_to_the_menu_and_the_other_side_is_told(apps):
    host, guest = apps
    assert meet(apps) and after_the_toss(apps)
    finish_with_the_8_early(apps)
    assert run(apps, lambda: host.net._result_shown and guest.net._result_shown)
    run(apps, lambda: False, seconds=1.0)
    host.handle_event(
        pg.event.Event(pg.MOUSEBUTTONDOWN, pos=hud.NET_BUTTONS["menu"].center, button=1)
    )
    assert host.scene is host.menu and host.net is None
    assert run(apps, lambda: guest.net.session.phase == net_session.CLOSED)


def test_walking_out_in_the_middle_of_a_game_gives_the_other_player_the_win(apps):
    host, guest = apps
    assert meet(apps) and after_the_toss(apps)
    guest.net.leave()
    assert run(apps, lambda: host.net._result_shown)
    assert host.net._ended_note is None and host.net.rules.phase == WON
    words, won = host.net._result_words()
    assert won and words == i18n.t("net.won_surrender", name=host.net._name(1))
    for _ in range(40):
        host.update(1 / 60)
        host.draw()
    host.handle_event(key(pg.K_RETURN))
    assert host.scene is host.menu


def test_esc_opens_a_card_while_the_game_goes_on_and_resume_closes_it(apps):
    host, guest = apps
    assert meet(apps) and after_the_toss(apps)
    host.handle_event(key(pg.K_ESCAPE))
    assert host.scene is host.net and host.net._card == "esc" and host.net._card_sel == 0
    run(apps, lambda: False, seconds=0.5)
    assert host.net.session.playing and host.net.session.linked  # nothing stopped for the card
    for _ in range(20):
        host.draw()
    host.handle_event(key(pg.K_ESCAPE))
    assert host.net._card is None
    host.handle_event(key(pg.K_m))  # the shortcuts of the game work again
    assert host.audio.muted


def test_the_card_blocks_the_table_and_the_mouse_picks_its_buttons(apps):
    assert meet(apps) and after_the_toss(apps)
    scene = players(apps)[0]
    app = apps[0] if scene is apps[0].net else apps[1]
    app.handle_event(key(pg.K_ESCAPE))
    assert scene._card_showing() == "esc"
    cue = scene.world.balls[0]
    app.handle_event(pg.event.Event(pg.MOUSEBUTTONDOWN, pos=to_px(cue.x, cue.y), button=1))
    assert not scene.drag.active  # a press on the cue ball under the card does nothing
    rects = scene._card_rects("esc")
    pos = rects["surrender"].center
    app.handle_event(pg.event.Event(pg.MOUSEMOTION, pos=pos, rel=(0, 0), buttons=(0, 0, 0)))
    assert scene._card_sel == 1
    app.handle_event(pg.event.Event(pg.MOUSEBUTTONDOWN, pos=pos, button=1))
    assert scene._card == "sure" and scene._card_sel == 1  # "Back" is the chosen one: the safe one
    app.handle_event(key(pg.K_ESCAPE))
    assert scene._card is None


def give_up_from_the_host(host):
    host.handle_event(key(pg.K_ESCAPE))
    host.handle_event(key(pg.K_RIGHT))
    host.handle_event(key(pg.K_RETURN))  # "Give up" ...
    assert host.net._card == "sure" and host.net.rules.phase == PLAYING
    host.handle_event(key(pg.K_LEFT))
    host.handle_event(key(pg.K_RETURN))  # ... and "yes, give up"


def test_giving_up_needs_two_steps_then_both_cards_show_who_won_and_why(apps):
    host, guest = apps
    assert meet(apps) and after_the_toss(apps)
    give_up_from_the_host(host)
    assert run(apps, lambda: host.net._result_shown and guest.net._result_shown)
    assert host.net.rules.phase == LOST and guest.net.rules.phase == WON
    assert host.net._result_words() == (i18n.t("net.lost_surrender"), False)
    words, won = guest.net._result_words()
    assert won and words == i18n.t("net.won_surrender", name=guest.net._name(0))
    assert host.net._wins() == (0, 1) and guest.net._wins() == (1, 0)
    for app in (host, guest):
        for _ in range(5):
            app.draw()


def test_a_rematch_waits_for_the_other_side_then_makes_a_new_game_with_the_score_kept(apps):
    host, guest = apps
    assert meet(apps) and after_the_toss(apps)
    old = host.net
    give_up_from_the_host(host)
    assert run(apps, lambda: host.net._result_shown and guest.net._result_shown)
    assert host.net.RESULT_DEFAULT == "again" and host.net._rematch_state() == "ready"
    host.handle_event(key(pg.K_RETURN))  # the host asks first ...
    assert host.net._rematch_state() == "wait" and host.net.RESULT_DEFAULT == "menu"
    assert run(apps, lambda: guest.net._rematch_state() == "they_asked")
    assert guest.net._again_view()[1][0] == i18n.t("net.rematch.they_asked", name="Hoa")
    run(apps, lambda: False, seconds=1.0)  # ... and waits as long as it takes
    assert host.net is old and host.net._rematch_state() == "wait"
    guest.handle_event(key(pg.K_RETURN))
    assert run(apps, lambda: host.net is not old and guest.net.session.game_no == 2)
    assert host.net.session.game_no == 2 and not host.net.session.match.over
    assert host.net._wins() == (0, 1) and guest.net._wins() == (1, 0)
    assert after_the_toss(apps)
    for app in (host, guest):
        for _ in range(5):
            app.draw()


def test_the_other_side_leaving_turns_the_rematch_button_off_with_a_note(apps):
    host, guest = apps
    assert meet(apps) and after_the_toss(apps)
    host.net.session.surrender()
    assert run(apps, lambda: host.net._result_shown and guest.net._result_shown)
    guest.net.leave()
    assert run(apps, lambda: host.net._rematch_state() == "gone")
    (label, can), note = host.net._again_view()
    assert not can and note[0] == i18n.t("net.rematch.gone", name="Nam")
    assert host.net.RESULT_DEFAULT == "menu"
    host.handle_event(key(pg.K_RETURN))
    assert host.scene is host.menu


def test_a_reaction_shows_on_both_screens_and_is_rationed(apps):
    host, guest = apps
    assert meet(apps) and after_the_toss(apps)
    host.handle_event(key(pg.K_1))
    host.handle_event(key(pg.K_2))  # too soon: dropped
    assert run(apps, lambda: 0 in guest.net._bubbles and 0 in host.net._bubbles)
    assert guest.net._bubbles[0][0] == 0 and host.net._bubbles[0][0] == 0
    chips = hud.emote_rects()
    assert len(chips) == config.NET_EMOTES
    run(apps, lambda: False, seconds=config.NET_EMOTE_GAP_S + 0.2)
    guest.handle_event(pg.event.Event(pg.MOUSEBUTTONDOWN, pos=chips[2].center, button=1))
    assert run(apps, lambda: 1 in host.net._bubbles and host.net._bubbles[1][0] == 2)
    for app in (host, guest):
        for _ in range(5):
            app.draw()


def test_the_last_ten_seconds_of_your_clock_beep_once_a_second(apps):
    host, guest = apps
    assert meet(apps) and after_the_toss(apps)
    scene = players(apps)[0]
    beeps = []
    scene.app.audio.play_clock_warn = beeps.append
    scene.session._turn_used = config.NET_TURN_S - 11.5
    other = apps[1] if scene is host.net else apps[0]
    for _ in range(5 * 60):
        scene.update(1 / 60)
        other.update(1 / 60)
    assert beeps[:4] == [10, 9, 8, 7]
    assert all(b > 0 for b in beeps) and len(beeps) == len(set(beeps))


def test_the_other_players_clock_makes_no_sound_for_you(apps):
    host, guest = apps
    assert meet(apps) and after_the_toss(apps)
    waiting = players(apps)[1]
    beeps = []
    waiting.app.audio.play_clock_warn = beeps.append
    waiting.session._turn_used = config.NET_TURN_S - 3.0
    for _ in range(120):
        waiting.update(1 / 60)
    assert beeps == []


def test_the_clock_bar_costs_no_new_picture_as_it_shrinks(apps):
    from game.render import draw as d

    host, _ = apps
    assert meet(apps) and after_the_toss(apps)
    scene = host.net
    for _ in range(3):
        host.draw()
    before = len(d._rr_cache)
    for i in range(120):
        scene.session._turn_used = i * 0.4
        host.draw()
    assert len(d._rr_cache) - before <= 6


def test_a_broken_link_shows_its_card_after_a_moment_and_it_goes_when_the_link_is_back(apps):
    host, guest = apps
    assert meet(apps) and after_the_toss(apps)
    session = host.net.session
    session.link_down_s = 0.2  # (the real break is in test_net_tcp: this is the scene's part)
    host.update(1 / 60)
    assert host.net._card_showing() is None  # a blink of the wifi is not news
    session.link_down_s = config.NET_LINK_CARD_DELAY_S + 0.1
    host.update(1 / 60)
    assert host.net._card_showing() == "link"
    title, line, buttons, _, _ = host.net._card_spec("link")
    assert str(int(config.NET_REJOIN_S) - 1) in line
    assert [b[0] for b in buttons] == ["leave"]
    for _ in range(20):
        host.draw()
    session.link_down_s = None
    host.update(1 / 60)
    assert host.net._card_showing() is None


def test_the_leave_button_of_the_lost_link_card_goes_to_the_menu(apps):
    host, guest = apps
    assert meet(apps) and after_the_toss(apps)
    host.net.session.link_down_s = config.NET_LINK_CARD_DELAY_S + 0.5
    host.update(1 / 60)
    host.handle_event(key(pg.K_ESCAPE))  # Esc does not dismiss it: only getting the link back does
    assert host.net._card_showing() == "link"
    host.handle_event(key(pg.K_RETURN))
    assert host.scene is host.menu


def test_a_timed_out_turn_says_so_on_both_screens(apps):
    host, guest = apps
    assert meet(apps) and after_the_toss(apps)
    on_turn_session = players(apps)[0].session
    assert host.net.session.timeout_turn()  # the referee calls time
    assert run(apps, lambda: all(a.net._net_notice for a in (host, guest)))
    shown = {a.net._net_notice[1] for a in (host, guest)}
    shooter_name = host.net._name(on_turn_session.me)
    mine = i18n.t("net.notice.timeout_me")
    theirs = i18n.t("net.notice.timeout_them", name=shooter_name)
    assert shown == {mine, theirs} or shown == {mine}


def test_ac9_net_keys_in_both_languages():
    vi, en = i18n.table("vi"), i18n.table("en")
    for k in (k for k in vi if k.startswith(("net.", "play."))):
        assert k in en, k
        assert set(re.findall(r"{(\w+)}", vi[k])) == set(re.findall(r"{(\w+)}", en[k])), k
    assert any(k.startswith("net.err.") for k in vi)


def test_nothing_opens_over_the_lost_link_card_and_the_chosen_button_stays_in_range(apps):
    host, guest = apps
    assert meet(apps) and after_the_toss(apps)
    host.net.session.link_down_s = config.NET_LINK_CARD_DELAY_S + 0.5
    host.update(1 / 60)
    assert host.net._card_showing() == "link"
    host.net._open_card("sure")  # (the developer's tool does this; a player cannot)
    assert host.net._card is None and host.net._card_showing() == "link"
    host.net._card_sel = 5
    for _ in range(3):
        host.update(1 / 60)
        host.draw()
    assert host.net._card_sel == 0


# --- the start of a game: a look, the coin in the dark, the point of the last game coming in ---
def frame_at(app, age):
    """The screen with the start of the game `age` seconds in (as the player would see it)."""
    scene = app.net
    scene._started_at = scene._clock - age
    app.skip_transition()  # (the scene change folds the picture for a third of a second)
    app.draw()
    return pg.display.get_surface().copy()


def mean_light(surface, rect):
    sub = surface.subsurface(rect)
    r, g, b, _ = pg.transform.average_color(sub)
    return r + g + b


def test_the_table_goes_dark_for_the_coin_but_the_plates_and_the_side_panel_stay_lit(apps):
    host, _ = apps
    assert meet(apps)
    scene = host.net
    tt = scene._toss
    lit = frame_at(host, 0.5)  # the look at the table first
    dark = frame_at(host, tt.lead_s + 0.5)  # the coin waits
    table = TABLE_RECT
    assert mean_light(dark, table) < 0.6 * mean_light(lit, table)
    plate = pg.Rect(OUTER_X, hud.PLATE_Y, hud.PLATE_W, hud.PLATE_H)
    assert pg.image.tobytes(lit.subsurface(plate), "RGB") == pg.image.tobytes(
        dark.subsurface(plate), "RGB"
    )  # the names and the score are read all through the coin toss
    after = frame_at(host, tt.total_s + 0.1)
    assert abs(mean_light(after, table) - mean_light(lit, table)) < 0.05 * mean_light(lit, table)


def test_the_coin_toss_has_its_sounds_in_order_and_none_before_the_throw(apps):
    host, guest = apps
    heard = []
    audio = host.audio
    audio.play_coin_up = lambda: heard.append("up")
    audio.play_coin_land = lambda: heard.append("land")
    audio.play_tally_tick = lambda pitch: heard.append("tick")
    audio.play_tally_ting = lambda won, big: heard.append("ting")
    assert meet(apps)
    scene = host.net
    assert run(apps, lambda: scene._toss_done())
    breaker = scene.session.breaker
    assert heard == ["up", *["tick"] * (6 + breaker), "land"]  # (a first game adds no point)


def test_the_plates_keep_the_old_score_while_the_result_card_is_up(apps):
    """Found in the dev tool: the point of a game that had just ended showed between the plates
    at once, with the card still up and nobody having asked for another game."""
    host, guest = apps
    assert meet(apps) and after_the_toss(apps)
    give_up_from_the_host(host)  # the host loses: the guest has the point
    assert run(apps, lambda: host.net._result_shown and guest.net._result_shown)
    assert host.net.session.wins == [0, 1]  # (it is counted: the next game starts from it)
    for _ in range(round(2.0 / (1 / 60))):  # well past the moment a point would roll in
        for app in (host, guest):
            app.update(1 / 60)
            app.draw()
    for app in (host, guest):
        assert app.net._shown_wins() == app.net._card_wins() == (0, 0)


def test_a_game_that_ends_under_the_coin_shows_no_coin_no_dark_table_and_no_coin_sound(
    apps, monkeypatch
):
    """The other player gave up in the first seconds: the card stands on a lit table."""
    host, guest = apps
    seen = {"coin": 0, "dark": 0}
    real_coin, real_dim = hud.toss_coin, hud.dim_rect

    def coin(*args, **kw):
        seen["coin"] += 1
        return real_coin(*args, **kw)

    def dim(canvas, v, rect, k):
        seen["dark"] += k > 0
        return real_dim(canvas, v, rect, k)

    monkeypatch.setattr(hud, "toss_coin", coin)
    monkeypatch.setattr(hud, "dim_rect", dim)
    assert meet(apps)
    scene = host.net
    tt = scene._toss
    frame_at(host, tt.lead_s + 0.5)  # the spies do see the coin and the dark while the game is on
    assert seen["coin"] > 0 and seen["dark"] > 0
    guest.net.session.surrender()
    assert run(apps, lambda: host.net._result_shown and guest.net._result_shown)
    seen.update(coin=0, dark=0)
    for age in (tt.lead_s + 0.5, tt.flip_at + 0.5, tt.land_at + 0.2):
        frame_at(host, age)
    assert seen == {"coin": 0, "dark": 0}
    heard = []
    host.audio.play_coin_up = lambda: heard.append("up")
    host.audio.play_coin_land = lambda: heard.append("land")
    host.audio.play_tally_tick = lambda pitch: heard.append("tick")
    scene._started_at = scene._clock - tt.flip_at  # the throw falls between this frame and the next
    scene._toss_age = tt.flip_at - 0.05
    host.update(1 / 60)
    assert heard == []


def test_a_rematch_shows_the_old_score_then_rolls_the_point_in_before_the_coin(apps):
    host, guest = apps
    assert meet(apps) and after_the_toss(apps)
    old = host.net
    give_up_from_the_host(host)  # the host loses: the guest will get the point
    assert run(apps, lambda: host.net._result_shown and guest.net._result_shown)
    assert host.net._wins() == (0, 1) and host.net._card_wins() == (0, 0)  # the card: BEFORE
    assert guest.net._wins() == (1, 0) and guest.net._card_wins() == (0, 0)
    host.handle_event(key(pg.K_RETURN))
    guest.handle_event(key(pg.K_RETURN))
    assert run(apps, lambda: host.net is not old and guest.net.session.game_no == 2)
    for app in (host, guest):
        scene = app.net
        assert scene.session.prev_winner == 1 and scene._toss.again
        assert scene._wins_before == scene._shown_wins() != scene._wins()
        app.draw()  # the board takes the old numbers in
    heard = {"host": [], "guest": []}
    host.audio.play_tally_ting = lambda won, big: heard["host"].append((won, big))
    guest.audio.play_tally_ting = lambda won, big: heard["guest"].append((won, big))
    for _ in range(round(1.2 / (1 / 60))):
        for app in (host, guest):
            app.update(1 / 60)
            app.draw()
    assert host.net._shown_wins() == (0, 1) and guest.net._shown_wins() == (1, 0)
    assert heard == {"host": [(False, True)], "guest": [(True, True)]}  # lower for the one behind
    assert guest.net._vs_board.previous["vs0"] == 0 and guest.net._vs_board.values["vs0"] == 1
    assert host.net._vs_board.previous["vs1"] == 0
    assert after_the_toss(apps)
    assert host.net._card_wins() == (0, 1)  # a game still being played: nothing to take off
