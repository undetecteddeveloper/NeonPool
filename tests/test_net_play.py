"""The Play panel and the two-player table: two games meet over a real socket on 127.0.0.1."""

import math
import re
import socket
import time

import pygame as pg
import pytest

from game import config, i18n
from game.app import App
from game.net import session as net_session
from game.physics import Shot
from game.render import hud
from game.rules.eight_ball import LOST, PLAYING, WON
from game.scenes import play_panel as pp
from game.scenes.net_play import COIN_S, NetPlayScene


def key(k):
    return pg.event.Event(pg.KEYDOWN, key=k)


def typed(text):
    return pg.event.Event(pg.TEXTINPUT, text=text)


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def apps(monkeypatch, tmp_path):
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
    """The host makes a room, the guest joins it by address; True once both are at the table."""
    host, guest = apps_
    hp, gp = host.menu.play_panel, guest.menu.play_panel
    hp.open()
    hp.name = "Hoa"
    hp._start_hosting()
    gp.open()
    gp.name, gp.addr = "Nam", "127.0.0.1"
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


def test_a_bad_address_is_refused_on_the_spot_and_a_closed_door_says_so(apps):
    host, _ = apps
    panel = host.menu.play_panel
    panel.open()
    panel._goto(pp.JOINING)
    panel.addr = "not an address!"
    panel._start_joining()
    assert panel.error == "net.err.bad_address" and panel.step == pp.JOINING
    panel.addr = "127.0.0.1"  # nobody is listening on the room's port
    panel._start_joining()
    assert panel.step == pp.CONNECTING
    assert run([host], lambda: panel.step == pp.JOINING)
    assert panel.error in ("net.err.refused", "net.err.unreachable", "net.err.timeout")


# --- two games meeting ---
def test_two_games_meet_through_the_panel_and_both_open_the_table(apps):
    host, guest = apps
    assert meet(apps)
    assert isinstance(host.net, NetPlayScene) and host.scene is host.net
    assert host.net.session.names == guest.net.session.names == ["Hoa", "Nam"]
    assert host.net.session.breaker == guest.net.session.breaker
    assert not host.menu.play_panel.is_open and host.menu.play_panel.listener is None


def test_a_guest_with_another_build_gets_the_update_message(apps, monkeypatch):
    host, guest = apps
    real = net_session.Session

    def other_build(transport, is_host, name, **kw):
        return real(transport, is_host, name, **({**kw, "build": "9.9"} if not is_host else kw))

    monkeypatch.setattr(pp.net_session, "Session", other_build)
    assert not meet(apps, seconds=3.0)
    assert run(apps, lambda: guest.menu.play_panel.error == "net.err.version", seconds=8)
    assert guest.net is None and guest.menu.play_panel.step == pp.JOINING
    assert host.net is None and host.menu.play_panel.listener is not None  # the room stays open


def test_the_coin_toss_comes_first_and_nobody_can_shoot_until_it_is_done(apps):
    host, guest = apps
    assert meet(apps)
    for a in (host, guest):
        assert not a.net._can_aim() and not a.net._dial_ok()
    assert after_the_toss(apps)
    first, other = players(apps)
    assert first._can_aim() and not other._can_aim()
    assert first.session.breaker == first.session.match.turn
    assert COIN_S > 1.5


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
    host.handle_event(pg.event.Event(pg.MOUSEBUTTONDOWN, pos=hud.NET_BUTTON.center, button=1))
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


def test_esc_has_to_be_pressed_twice_to_leave_a_two_player_game(apps):
    host, guest = apps
    assert meet(apps) and after_the_toss(apps)
    host.handle_event(key(pg.K_ESCAPE))
    assert host.scene is host.net and host.net._notice_left > 0
    host.handle_event(key(pg.K_ESCAPE))
    assert host.scene is host.menu
    host.handle_event(key(pg.K_m))  # after the panel the shortcuts of the game work again
    assert host.audio.muted


def test_ac9_net_keys_in_both_languages():
    vi, en = i18n.table("vi"), i18n.table("en")
    for k in (k for k in vi if k.startswith(("net.", "play."))):
        assert k in en, k
        assert set(re.findall(r"{(\w+)}", vi[k])) == set(re.findall(r"{(\w+)}", en[k])), k
    assert any(k.startswith("net.err.") for k in vi)
