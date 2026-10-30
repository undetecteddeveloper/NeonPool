"""Sessions: handshake, coin toss, turns, referee, checkpoints, bad networks (AC4, AC6)."""

import math
import random

import pytest

from game import config
from game.net import protocol as p
from game.net import session as s
from game.net.session import GUEST, HOST, Session, capture_balls
from game.net.transport import NetSim, SimRoom
from game.physics import Shot
from game.rules.eight_ball import FOUL_NO_HIT
from game.rules.two_player import LOST_DROPPED, LOST_SURRENDER


def pair(latency=0.0, jitter=0.0, loss=0.0, seed=0, **guest_kw):
    sim = NetSim(latency, jitter, loss, seed)
    host = Session(sim.a, True, "Hoa", rng=random.Random(11))
    guest = Session(sim.b, False, "Nam", **guest_kw)
    return sim, host, guest


def run(sim, sessions, seconds, until=None, dt=1 / 60):
    """Let time pass for everyone; True when `until` became true (or there was none)."""
    for _ in range(round(seconds / dt)):
        sim.advance(dt)
        for sess in sessions:
            sess.update(dt)
        if until is not None and until():
            return True
    return until is None


def started(**kw):
    sim, host, guest = pair(**kw)
    assert run(sim, (host, guest), 5.0, lambda: host.playing and guest.playing)
    return sim, host, guest


def on_turn(host, guest):
    return host if host.match.turn == HOST else guest


def off_turn(host, guest):
    return guest if host.match.turn == HOST else host


def play_shot(sim, host, guest, shot, seconds=90.0):
    """The player on turn shoots; run until the referee's verdict has reached both machines."""
    wanted = host.checkpoints + 1
    assert on_turn(host, guest).shoot(shot) is not None

    def done():
        return (
            host.checkpoints == wanted
            and guest.checkpoints == wanted
            and host.settled
            and guest.settled
        )

    assert run(sim, (host, guest), seconds, done)


def give_guest_the_turn(sim, host, guest):
    """Get to a table where it is the guest's turn and the cue ball is placed and ready."""
    if host.match.turn == HOST:
        play_shot(sim, host, guest, no_hit_shot())  # a foul: the guest has the ball in hand
    if guest.can_place:
        assert guest.place_cue(1.0, 0.4)
        guest.release_cue()
    assert run(sim, (host, guest), 2.0, lambda: guest.can_shoot and host.settled)


def same_table(host, guest):
    return capture_balls(host.world) == capture_balls(guest.world)


def no_hit_shot():
    """From the head spot straight at the near cushion, softly: touches nothing (a foul)."""
    return Shot(math.pi, 0.1, 0.0)


# --- the door and the coin ---
def test_handshake_gives_both_machines_the_same_game_and_the_same_coin():
    sim, host, guest = started(latency=0.02)
    assert host.names == ["Hoa", "Nam"] and guest.names == ["Hoa", "Nam"]
    assert host.breaker == guest.breaker in (0, 1)
    assert host.match.turn == guest.match.turn == host.breaker
    assert same_table(host, guest)
    assert (host.me, guest.me) == (HOST, GUEST)


def test_the_coin_is_the_hosts_and_both_outcomes_happen():
    seen = set()
    for seed in range(40):
        sim = NetSim()
        host = Session(sim.a, True, "A", rng=random.Random(seed))
        guest = Session(sim.b, False, "B")
        run(sim, (host, guest), 1.0, lambda h=host, g=guest: h.playing and g.playing)
        assert host.breaker == guest.breaker
        seen.add(host.breaker)
    assert seen == {0, 1}


def test_a_guest_with_another_build_is_refused_at_the_door_on_both_sides():
    sim, host, guest = pair(build="9.9")
    run(sim, (host, guest), 2.0, lambda: guest.phase == s.CLOSED)
    assert guest.close_reason == s.CLOSE_VERSION and host.close_reason == s.CLOSE_VERSION
    assert host.world is None and guest.world is None


def test_a_guest_with_other_physics_is_refused_too():
    sim, host, guest = pair(fingerprint=p.physics_fingerprint() ^ 1)
    run(sim, (host, guest), 2.0, lambda: guest.phase == s.CLOSED)
    assert guest.close_reason == s.CLOSE_VERSION


def test_a_silent_connection_is_dropped_after_the_handshake_timeout():
    sim = NetSim()
    host = Session(sim.a, True, "A")
    run(sim, (host,), config.NET_HANDSHAKE_TIMEOUT_S + 1.0)
    assert host.close_reason == s.CLOSE_TIMEOUT


# --- AC4: the referee and the turn ---
def test_a_player_without_the_turn_cannot_shoot_and_nothing_changes():
    sim, host, guest = started()
    other = off_turn(host, guest)
    assert not other.can_shoot and other.shoot(Shot(0.0, 0.5, 0.0)) is None
    assert other.world.at_rest() and other.seq == 0


def test_ac4_shot_out_of_turn_rejected():
    """A guest that ignores its own check and asks to shoot out of turn is refused by the host,
    and its predicted shot is taken back by a checkpoint."""
    sim, host, guest = started()
    if host.match.turn == GUEST:  # make it the host's turn so the guest is the one out of turn
        play_shot(sim, host, guest, no_hit_shot())
        guest.place_cue(1.0, 0.4)
        guest.release_cue()
        run(sim, (host, guest), 0.5)
    assert host.match.turn == HOST
    before = capture_balls(host.world)
    msg = p.ShotMsg.from_shot((host.seq + 1) & 0xFFFF, Shot(0.0, 0.8, 0.0))
    guest.transport.send(p.encode(msg))  # the cheat: ask anyway ...
    guest.world.apply(msg.to_shot())  # ... and play it on its own copy
    guest._live = True
    run(sim, (host, guest), 3.0, lambda: guest.rejected_shots == 1 and guest.settled)
    assert host.rejected_shots == 1 and guest.rejected_shots == 1
    assert capture_balls(host.world) == before == capture_balls(guest.world)
    assert host.settled and host.match.turn == HOST


def test_ac4_a_request_with_the_wrong_number_is_refused():
    sim, host, guest = started()
    give_guest_the_turn(sim, host, guest)
    before = capture_balls(host.world)
    bad = p.ShotMsg.from_shot((host.seq + 5) & 0xFFFF, Shot(1.0, 0.5, 0.0))
    guest.transport.send(p.encode(bad))
    run(sim, (host, guest), 0.5)
    assert host.rejected_shots == 1 and guest.rejected_shots == 1
    assert host.settled and capture_balls(host.world) == before


def test_ac4_a_request_while_the_balls_still_roll_is_refused():
    sim, host, guest = started()
    give_guest_the_turn(sim, host, guest)
    assert guest.shoot(Shot(0.0, 0.9, 0.0)) is not None  # a real shot is rolling ...
    run(sim, (host, guest), 0.3)
    again = p.ShotMsg.from_shot((host.seq + 1) & 0xFFFF, Shot(1.0, 0.5, 0.0))
    guest.transport.send(p.encode(again))  # ... and a second one is asked for at once
    run(sim, (host, guest), 0.3)
    assert host.rejected_shots == 1


def test_ac4_timeout_passes_the_turn_on_both_machines():
    sim, host, guest = started()
    turn = host.match.turn
    assert host.timeout_turn()
    run(sim, (host, guest), 1.0, lambda: guest.match.turn != turn)
    assert host.match.turn == guest.match.turn == 1 - turn
    assert host.take_judged()[-1].timed_out and guest.take_judged()[-1].timed_out
    assert not guest.timeout_turn()  # only the referee calls time


def test_a_guest_can_claim_its_clock_ran_out_and_the_host_decides():
    sim, host, guest = started()
    if host.match.turn == HOST:
        host.timeout_turn()
        run(sim, (host, guest), 1.0, lambda: guest.match.turn == GUEST)
    guest._send(p.TurnTimeout(GUEST))
    run(sim, (host, guest), 1.0, lambda: host.match.turn == HOST)
    assert host.match.turn == HOST


# --- AC11: the clock of the shot ---
def test_ac11_the_clock_waits_for_the_coin_and_for_rolling_balls():
    sim, host, guest = started()
    run(sim, (host, guest), config.NET_COIN_S - 0.3)  # the coin is still in the air
    assert host.turn_left_s == guest.turn_left_s == config.NET_TURN_S
    assert not host.clock_running
    run(sim, (host, guest), 1.3)
    assert host.clock_running and host.turn_left_s < config.NET_TURN_S - 0.9
    shooter = on_turn(host, guest)
    assert shooter.shoot(Shot(0.0, 0.9, 0.0)) is not None
    assert shooter.turn_left_s == config.NET_TURN_S  # a new shot: a whole clock again
    run(sim, (host, guest), 0.5)
    assert not shooter.settled and not shooter.clock_running
    frozen = shooter.turn_left_s
    run(sim, (host, guest), 0.5)
    assert shooter.turn_left_s == frozen  # nothing counts while the balls roll


def pass_turn_to(sim, host, guest, player):
    """If the turn is not `player`'s, let it run out once so that it is (no foul, no ball in hand).
    The coin is let land first, so that the clock is running when this returns."""
    run(sim, (host, guest), config.NET_COIN_S + 0.1)
    if host.match.turn != player:
        assert host.timeout_turn()
        assert run(sim, (host, guest), 1.0, lambda: guest.match.turn == player)
        host.take_judged(), guest.take_judged()


def test_ac11_the_host_calls_time_on_its_own_turn_after_60_seconds():
    sim, host, guest = started()
    pass_turn_to(sim, host, guest, HOST)
    run(sim, (host, guest), config.NET_TURN_S - 2.0)
    assert host.match.turn == HOST  # not yet
    assert run(sim, (host, guest), 4.0, lambda: guest.match.turn == GUEST)
    assert host.match.turn == guest.match.turn == GUEST
    assert host.take_judged()[-1].timed_out and guest.take_judged()[-1].timed_out
    assert host.match.fouls == [0, 0] and not host.match.cue_in_hand
    assert guest.turn_left_s > config.NET_TURN_S - 0.2  # the next player starts with a whole clock


def test_ac11_the_guest_s_own_clock_ends_its_turn_and_the_host_agrees():
    sim, host, guest = started(latency=0.03)
    pass_turn_to(sim, host, guest, GUEST)
    assert run(sim, (host, guest), config.NET_TURN_S + 0.5, lambda: guest._timeout_sent)
    assert not guest.can_shoot  # no more shots once it has said time is up
    assert run(sim, (host, guest), 1.0, lambda: host.match.turn == HOST)
    run(sim, (host, guest), 0.5)
    assert host.match.turn == guest.match.turn == HOST
    assert not guest._timeout_sent and guest.turn_left_s > config.NET_TURN_S - 0.5


def test_ac11_the_host_calls_time_itself_when_the_guest_says_nothing():
    sim, host, guest = started()
    pass_turn_to(sim, host, guest, GUEST)
    guest._tick_clock = lambda dt: None  # this guest never speaks up
    run(sim, (host, guest), config.NET_TURN_S + config.NET_TURN_GRACE_S - 2.0)
    assert host.match.turn == GUEST  # the host is still waiting: it gives the guest a moment longer
    assert run(sim, (host, guest), 4.0, lambda: host.match.turn == HOST)


def test_ac11_a_shot_at_the_last_moment_is_not_refused_for_being_late():
    sim, host, guest = started(latency=0.1)
    give_guest_the_turn(sim, host, guest)
    run(sim, (host, guest), config.NET_TURN_S + 5.0, lambda: guest.turn_left_s < 0.05)
    assert guest.turn_left_s < 0.05 and not guest._timeout_sent
    assert guest.shoot(Shot(0.0, 0.6, 0.0)) is not None
    run(sim, (host, guest), 8.0, lambda: host.checkpoints == guest.checkpoints and guest.settled)
    assert host.rejected_shots == 0 and guest.rejected_shots == 0
    assert host.last_shooter == GUEST and same_table(host, guest)


# --- AC12: giving the game up, or walking out of it ---
def finished(sim, host, guest):
    """Both machines show the same ended game."""
    return host.match.over and guest.match.over


def test_ac12_the_guest_gives_up_and_the_host_wins_on_both_machines():
    sim, host, guest = started(latency=0.02)
    assert guest.surrender()
    assert run(sim, (host, guest), 2.0, lambda: finished(sim, host, guest))
    for sess in (host, guest):
        assert sess.match.winner == HOST and sess.match.last.shooter == GUEST
        assert sess.match.last.reason == LOST_SURRENDER
        assert sess.wins == [1, 0]
    assert host.match.score(HOST) == config.SCORE_WIN_BASE and host.match.score(GUEST) == 0
    assert host.match.snapshot() == guest.match.snapshot()
    assert not guest.surrender() and not host.surrender()  # it is over: nothing more to give up


def test_ac12_the_host_gives_up_and_the_guest_wins_on_both_machines():
    sim, host, guest = started(latency=0.02)
    assert host.surrender()
    assert run(sim, (host, guest), 2.0, lambda: finished(sim, host, guest))
    assert host.match.winner == guest.match.winner == GUEST
    assert host.wins == guest.wins == [0, 1]


def test_ac12_giving_up_while_the_balls_roll_stops_the_game_at_once():
    sim, host, guest = started(latency=0.02)
    shooter = on_turn(host, guest)
    assert shooter.shoot(Shot(0.0, 0.9, 0.0)) is not None
    run(sim, (host, guest), 0.4)
    assert not host.settled  # the break is still rolling
    assert guest.surrender() if shooter is host else host.surrender()
    assert run(sim, (host, guest), 2.0, lambda: finished(sim, host, guest))
    loser = host.match.last.shooter
    run(sim, (host, guest), 20.0)  # the balls come to rest; the referee does not judge a shot now
    assert host.match.winner == guest.match.winner == 1 - loser
    assert host.take_judged()[-1].reason == LOST_SURRENDER
    assert host.match.snapshot() == guest.match.snapshot()


def test_ac12_walking_out_in_the_middle_of_a_game_loses_it():
    for leaver_is_host in (False, True):
        sim, host, guest = started(latency=0.02)
        leaver, stayer = (host, guest) if leaver_is_host else (guest, host)
        leaver.leave()
        assert run(sim, (host, guest), 2.0, lambda st=stayer: st.phase == s.CLOSED)
        assert stayer.close_reason == s.CLOSE_LEFT and leaver.close_reason == s.CLOSE_SELF
        assert stayer.match.over and stayer.match.winner == stayer.me  # told before the goodbye
        assert stayer.match.last.reason == LOST_SURRENDER


def test_ac12_leaving_after_the_game_is_over_changes_nothing():
    sim, host, guest = started(latency=0.02)
    assert host.surrender()
    assert run(sim, (host, guest), 2.0, lambda: finished(sim, host, guest))
    guest.leave()
    run(sim, (host, guest), 1.0, lambda: host.phase == s.CLOSED)
    assert host.match.winner == GUEST and host.close_reason == s.CLOSE_LEFT


def test_ac12_a_stray_surrender_after_the_end_is_ignored():
    sim, host, guest = started()
    assert host.surrender()
    run(sim, (host, guest), 1.0, lambda: finished(sim, host, guest))
    before = host.match.snapshot()
    guest._send(p.Surrender())
    run(sim, (host, guest), 0.5)
    assert host.match.snapshot() == before and host.wins == [0, 1]


# --- AC13: another game, and the score of the room ---
def end_game(sim, host, guest, loser):
    """The loser gives up; run until both machines show it."""
    assert (host if loser == HOST else guest).surrender()
    assert run(sim, (host, guest), 3.0, lambda: finished(sim, host, guest))


def next_game(host, guest):
    """Both machines have begun the next game."""
    return host.game_no == guest.game_no and not host.match.over and not guest.match.over


def test_ac13_a_rematch_waits_for_the_other_player_for_as_long_as_it_takes():
    sim, host, guest = started(latency=0.02)
    end_game(sim, host, guest, GUEST)
    first = host.match
    assert host.ask_rematch() and not host.ask_rematch()  # asking twice does nothing new
    run(sim, (host, guest), 300.0)  # five minutes: no time limit
    assert host.game_no == guest.game_no == 1 and host.match is first
    assert guest.rematch == [True, False] and host.rematch == [True, False]  # the guest knows
    assert guest.ask_rematch()
    assert run(sim, (host, guest), 2.0, lambda: host.game_no == 2 and guest.game_no == 2)
    assert not host.match.over and not guest.match.over and host.match is not first
    assert host.breaker == guest.breaker and host.match.turn == guest.match.turn == host.breaker
    assert same_table(host, guest) and host.rematch == guest.rematch == [False, False]
    assert host.seq == guest.seq == 0
    play_shot(sim, host, guest, Shot(0.0, 0.9, 0.0))  # the new game really is playable
    assert same_table(host, guest) and host.desyncs == guest.desyncs == 0


def test_ac13_the_guest_may_be_the_one_to_ask_first():
    sim, host, guest = started(latency=0.02)
    end_game(sim, host, guest, HOST)
    assert guest.ask_rematch()
    run(sim, (host, guest), 1.0)
    assert host.game_no == 1 and host.rematch == [False, True]
    assert host.ask_rematch()
    assert run(sim, (host, guest), 2.0, lambda: host.game_no == 2 and guest.game_no == 2)


def test_ac13_every_rematch_is_a_new_table_and_a_new_coin():
    sim, host, guest = started()
    seeds, coins = {hash(host.world.rng.getstate())}, {host.breaker}
    for _ in range(6):
        end_game(sim, host, guest, GUEST)
        host.ask_rematch(), guest.ask_rematch()
        assert run(sim, (host, guest), 1.0, lambda: next_game(host, guest))
        seeds.add(hash(host.world.rng.getstate()))
        coins.add(host.breaker)
        assert host.breaker == guest.breaker and same_table(host, guest)
    assert len(seeds) == 7 and coins == {0, 1}


def test_ac13_the_score_of_the_room_is_the_same_on_both_machines():
    sim, host, guest = started(latency=0.01)
    for loser in (GUEST, HOST, GUEST):
        end_game(sim, host, guest, loser)
        host.ask_rematch(), guest.ask_rematch()
        assert run(sim, (host, guest), 1.0, lambda: next_game(host, guest))
    end_game(sim, host, guest, GUEST)
    assert host.wins == guest.wins == [3, 1]
    assert host.game_no == guest.game_no == 4


def test_ac13_no_rematch_before_the_end_or_after_the_other_player_left():
    sim, host, guest = started(latency=0.02)
    assert not host.ask_rematch() and not guest.ask_rematch()  # the game is not over
    end_game(sim, host, guest, GUEST)
    assert guest.ask_rematch()
    host.leave()
    assert run(sim, (host, guest), 1.0, lambda: guest.phase == s.CLOSED)
    assert guest.match.over and not guest.ask_rematch()  # the room is gone: the button is dead


def test_ac13_a_rematch_message_in_the_middle_of_a_game_is_ignored():
    sim, host, guest = started()
    guest._send(p.Rematch())
    guest._send(p.Start(5, 0, config.DEFAULT_FEEL, config.DEFAULT_SPIN))  # nor may Start be forced
    run(sim, (host, guest), 0.5)
    assert host.rematch == [False, False] and host.game_no == guest.game_no == 1


# --- AC14: the link breaks in the middle of the game and comes back ---
def room_pair(latency=0.0, jitter=0.0, loss=0.0, seed=0):
    """A started game whose two machines can get a new connection (`SimRoom`) if the link breaks."""
    room = SimRoom(latency, jitter, loss, seed)
    host = Session(room.a, True, "Hoa", rng=random.Random(11), relink=room.host_relink)
    guest = Session(room.b, False, "Nam", relink=room.guest_relink)
    assert run(room, (host, guest), 5.0, lambda: host.playing and guest.playing)
    host.set_relink(room.host_relink), guest.set_relink(room.guest_relink)
    return room, host, guest


def settle_clocks(room, host, guest):
    """Let the coin land, so that the clock is running."""
    run(room, (host, guest), config.NET_COIN_S + 0.1)


def back_together(host, guest):
    return host.linked and guest.linked and host.settled and guest.settled


def test_ac14_a_break_while_the_balls_roll_then_back_in_time_gives_the_same_table():
    room, host, guest = room_pair(latency=0.02)
    shooter = on_turn(host, guest)
    assert shooter.shoot(Shot(0.0, 0.9, 0.0)) is not None
    run(room, (host, guest), 0.3)
    room.cut()
    run(room, (host, guest), 0.2)
    assert host.link_down_s is not None and guest.link_down_s is not None
    assert not host.can_shoot and not guest.can_shoot and host.playing and guest.playing
    run(room, (host, guest), 6.0)  # the balls run to a stop on each machine meanwhile
    room.reconnect()
    assert run(room, (host, guest), 5.0, lambda: back_together(host, guest))
    assert host.link_down_s is None and guest.link_down_s is None
    assert host.rejoins == 1 and guest.rejoins == 1 and host.link_losses == guest.link_losses == 1
    assert same_table(host, guest) and host.match.snapshot() == guest.match.snapshot()
    asked = host.checkpoints
    assert on_turn(host, guest).shoot(Shot(0.5, 0.7, 0.0)) is not None  # the game goes on ...
    assert run(
        room, (host, guest), 60.0, lambda: host.checkpoints > asked and back_together(host, guest)
    )
    assert (
        same_table(host, guest) and host.match.snapshot() == guest.match.snapshot()
    )  # ... verdict and all


def test_ac14_a_break_on_the_guests_turn_and_the_guest_shoots_after_coming_back():
    room, host, guest = room_pair(latency=0.02)
    give_guest_the_turn(room, host, guest)
    room.cut()
    run(room, (host, guest), 3.0)
    assert not guest.can_shoot  # no shooting into the void
    room.reconnect()
    assert run(room, (host, guest), 5.0, lambda: back_together(host, guest))
    assert guest.can_shoot and same_table(host, guest)
    play_shot(room, host, guest, Shot(0.3, 0.6, 0.0))
    assert host.last_shooter == GUEST and same_table(host, guest)


def test_ac14_a_break_while_placing_the_cue_ball_in_hand():
    room, host, guest = room_pair(latency=0.02)
    play_shot(room, host, guest, no_hit_shot())  # a foul: the other player has the ball in hand
    placer = on_turn(host, guest)
    assert run(room, (host, guest), 2.0, lambda: placer.can_place)
    assert placer.place_cue(1.0, 0.4)
    room.cut()
    run(room, (host, guest), 3.0)
    room.reconnect()
    assert run(room, (host, guest), 5.0, lambda: host.linked and guest.linked and host.settled)
    run(room, (host, guest), 1.0)
    assert placer.can_place and host.match.cue_in_hand and guest.match.cue_in_hand
    assert placer.place_cue(1.1, 0.5)
    placer.release_cue()
    assert run(room, (host, guest), 2.0, lambda: placer.can_shoot and same_table(host, guest))


def test_ac14_the_clock_of_the_shot_waits_while_the_link_is_down():
    room, host, guest = room_pair()
    settle_clocks(room, host, guest)
    run(room, (host, guest), 10.0)
    left = host.turn_left_s
    room.cut()
    run(room, (host, guest), 40.0)
    assert host.turn_left_s == pytest.approx(left, abs=0.1) and not host.clock_running
    room.reconnect()
    assert run(room, (host, guest), 5.0, lambda: back_together(host, guest))
    # a new verdict-less table from the host: the clock starts again from there, not from nothing
    assert host.match.turn == guest.match.turn
    assert host.turn_left_s <= config.NET_TURN_S


def test_ac14_after_a_minute_without_the_guest_the_host_wins_and_the_guest_is_told_it_is_lost():
    room, host, guest = room_pair(latency=0.02)
    settle_clocks(room, host, guest)
    room.cut()
    run(room, (host, guest), config.NET_REJOIN_S - 2.0)
    assert host.playing and guest.playing and not host.match.over
    assert run(room, (host, guest), 4.0, lambda: host.phase == s.CLOSED and guest.phase == s.CLOSED)
    assert host.close_reason == guest.close_reason == s.CLOSE_LOST
    assert host.match.over and host.match.winner == HOST
    assert host.match.last.shooter == GUEST and host.match.last.reason == LOST_DROPPED
    assert not guest.match.over  # it cannot know who is to blame: the screen says "connection lost"


def test_ac14_a_stranger_with_the_wrong_key_is_turned_away_and_the_guest_still_gets_in():
    room, host, guest = room_pair(latency=0.01)
    room.cut()
    run(room, (host, guest), 1.0)
    thief = room.stranger()
    thief.send(
        p.encode(
            p.Resume(
                p.PROTOCOL_VERSION, config.GAME_VERSION, p.physics_fingerprint(), guest.token ^ 1
            )
        )
    )
    run(room, (host, guest), 1.0)
    assert [p.decode(f) for f in thief.poll()] == [p.Reject(p.REJECT_BUSY)]
    assert host.link_down_s is not None and host.rejoins == 0  # nobody was let in
    room.reconnect()
    assert run(room, (host, guest), 5.0, lambda: back_together(host, guest))
    assert host.rejoins == 1


def test_ac14_a_guest_with_another_build_cannot_take_the_seat_back():
    room, host, guest = room_pair()
    guest._build = "9.9"
    room.cut()
    run(room, (host, guest), 1.0)
    room.reconnect()
    run(room, (host, guest), 5.0)
    assert host.link_down_s is not None and host.rejoins == 0


def test_ac14_a_link_that_goes_quiet_without_closing_is_noticed_and_mended():
    room, host, guest = room_pair(latency=0.02)
    settle_clocks(room, host, guest)
    room.mute()  # nothing gets through, but nobody hangs up
    assert run(
        room, (host, guest), config.NET_SILENT_S + 3.0, lambda: not host.linked and not guest.linked
    )
    room.reconnect()
    assert run(room, (host, guest), 5.0, lambda: back_together(host, guest))
    assert same_table(host, guest)


def test_ac14_a_shot_that_never_arrived_is_taken_back_by_the_hosts_table():
    room, host, guest = room_pair(latency=0.02)
    give_guest_the_turn(room, host, guest)
    before = capture_balls(host.world)
    room.mute()
    assert guest.shoot(Shot(0.0, 0.8, 0.0)) is not None  # played here, but never sent
    room.cut()
    run(room, (host, guest), 8.0)
    assert capture_balls(guest.world) != before  # the guest's own table moved on
    room.reconnect()
    assert run(room, (host, guest), 5.0, lambda: back_together(host, guest))
    assert same_table(host, guest) and capture_balls(host.world) == before
    assert guest.can_shoot  # and it is still the guest's turn: it shoots again


def test_ac14_walking_out_while_the_link_is_down_still_ends_the_game():
    room, host, guest = room_pair()
    room.cut()
    run(room, (host, guest), 1.0)
    host.leave()
    assert host.phase == s.CLOSED and host.match.over and host.match.winner == GUEST


def test_ac14_a_rematch_asked_for_before_the_break_is_not_forgotten():
    room, host, guest = room_pair(latency=0.02)
    assert host.surrender()
    assert run(room, (host, guest), 2.0, lambda: finished(room, host, guest))
    assert guest.ask_rematch()
    room.cut()
    run(room, (host, guest), 2.0)
    room.reconnect()
    assert run(room, (host, guest), 5.0, lambda: host.linked and guest.linked)
    run(room, (host, guest), 1.0)
    assert host.rematch == [False, True]  # the host heard it again
    assert host.ask_rematch()
    assert run(room, (host, guest), 2.0, lambda: next_game(host, guest))


# --- AC15: the ready-made reactions ---
def test_ac15_a_reaction_reaches_both_screens_as_a_code():
    sim, host, guest = started(latency=0.02)
    assert guest.send_emote(1)
    run(sim, (host, guest), 0.5)
    assert guest.take_emotes() == [(GUEST, 1)] and host.take_emotes() == [(GUEST, 1)]
    assert host.take_emotes() == []  # taken once


def test_ac15_codes_out_of_range_are_never_sent_or_shown():
    sim, host, guest = started()
    assert not host.send_emote(config.NET_EMOTES) and not host.send_emote(-1)
    guest._send(p.Emote(200))  # a hand-made frame
    run(sim, (host, guest), 0.5)
    assert host.take_emotes() == [] and guest.take_emotes() == []


def test_ac15_reactions_are_rationed():
    sim, host, guest = started()
    assert host.send_emote(0)
    assert not host.send_emote(2)  # at once: too soon
    run(sim, (host, guest), config.NET_EMOTE_GAP_S - 0.2)
    assert not host.send_emote(2)
    run(sim, (host, guest), 0.3)
    assert host.send_emote(2)
    run(sim, (host, guest), 0.1)
    assert [c for _, c in guest.take_emotes()] == [0, 2]


def test_ac15_a_flood_from_a_hand_made_client_cannot_pile_up():
    sim, host, guest = started()
    for _ in range(200):
        guest._send(p.Emote(1))
    run(sim, (host, guest), 0.5)
    assert len(host.take_emotes()) <= s.EMOTE_QUEUE


# --- a shot, the verdict, the checkpoint ---
def test_the_break_is_played_on_both_machines_and_the_referee_s_table_is_everywhere():
    sim, host, guest = started(latency=0.02, jitter=0.005)
    play_shot(sim, host, guest, Shot(0.0, 0.9, 0.0))
    assert same_table(host, guest)
    assert host.match.snapshot() == guest.match.snapshot()
    assert host.desyncs == 0 and guest.desyncs == 0  # one machine, one arithmetic
    assert host.seq == guest.seq == 1


def test_a_foul_gives_the_cue_ball_in_hand_to_the_other_player_who_places_it_and_shoots():
    sim, host, guest = started(latency=0.01)
    shooter, other = on_turn(host, guest), off_turn(host, guest)
    play_shot(sim, host, guest, no_hit_shot())
    judged = host.take_judged()[-1]
    assert judged.fouls == (FOUL_NO_HIT,)
    assert host.match.turn == guest.match.turn == other.me and host.match.cue_in_hand
    assert other.can_place and not other.can_shoot and not shooter.can_place
    assert not other.place_cue(0.0, 0.0)  # in a pocket mouth: refused, the ball stays
    assert other.place_cue(1.0, 0.4)
    run(sim, (host, guest), 0.3)  # the other machine sees it move
    assert shooter.world.balls[0].x == pytest.approx(1.0) or shooter.match.cue_in_hand
    other.release_cue()
    run(sim, (host, guest), 0.5, lambda: not host.match.cue_in_hand and not guest.match.cue_in_hand)
    assert other.can_shoot and same_table(host, guest)
    assert (host.world.balls[0].x, host.world.balls[0].y) == (1.0, 0.4)


def test_a_desync_is_counted_and_the_referee_s_table_is_taken():
    sim, host, guest = started()
    guest.world.balls[5].x += 0.01  # this machine's arithmetic "went its own way"
    play_shot(sim, host, guest, Shot(0.0, 0.9, 0.0))
    assert guest.desyncs == 1 and guest.max_desync_m > config.NET_DESYNC_M
    assert same_table(host, guest)  # and from now on they agree again
    assert host.desyncs == 0


def test_the_other_players_cue_is_seen_at_no_more_than_the_agreed_rate():
    sim, host, guest = started()
    shooter, viewer = on_turn(host, guest), off_turn(host, guest)
    angle = 0.0
    for _ in range(240):  # one second at 240 Hz of "the mouse moved"
        angle += 0.01
        shooter.set_aim(p.AIM_PULLING, angle, 100.0)
        sim.advance(1 / 240)
        shooter.update(1 / 240)
        viewer.update(1 / 240)
    assert viewer.remote_cue.received <= config.NET_AIM_HZ + 1
    assert viewer.remote_cue.visible and viewer.remote_cue.state == p.AIM_PULLING
    shooter.set_aim(p.AIM_HIDDEN)
    run(sim, (host, guest), 0.2)
    assert not viewer.remote_cue.visible  # the last word is never held back by the rate limit


# --- bad frames, goodbyes, cuts ---
def test_garbage_on_the_wire_is_counted_and_the_game_goes_on():
    sim, host, guest = started()
    guest.transport.send(b"\x00\x00\x01")
    guest.transport.send(p.encode(p.Ping(1))[:-1])
    guest.transport.send(bytes(range(40)), reliable=False)
    run(sim, (host, guest), 0.3)
    assert host.bad_frames == 3 and host.playing
    play_shot(sim, host, guest, Shot(0.0, 0.5, 0.0))


def test_leaving_tells_the_other_side_and_a_cut_cable_is_a_lost_connection():
    sim, host, guest = started()
    guest.leave()
    run(sim, (host, guest), 0.5)
    assert guest.close_reason == s.CLOSE_SELF and host.close_reason == s.CLOSE_LEFT
    sim2, host2, guest2 = started()
    sim2.cut()
    run(sim2, (host2, guest2), 0.2)
    assert host2.close_reason == guest2.close_reason == s.CLOSE_LOST
    assert host2.update(0.1) == []  # a closed session does nothing


def test_the_round_trip_time_is_measured():
    sim, host, guest = started(latency=0.03)
    run(sim, (host, guest), 3.0)
    assert guest.rtt_s == pytest.approx(0.06, abs=0.02) and host.rtt_s is not None


# --- AC6: a whole game over a bad network ---
def test_ac6_netsim_game_ends_with_same_result_on_both():
    sim, host, guest = started(latency=0.02, jitter=0.01, loss=0.02, seed=3)
    rng = random.Random(5)
    # a few real shots first (each side shoots at a random ball), then a scripted finish
    for _ in range(4):
        player = on_turn(host, guest)
        if player.can_place:
            assert player.place_cue(0.8, 0.5) or player.place_cue(0.9, 0.7)
            player.release_cue()
            run(sim, (host, guest), 1.0, lambda pl=player: pl.can_shoot)
        aim = rng.choice([b for b in player.world.balls[1:] if b.in_play])
        cue = player.world.balls[0]
        angle = math.atan2(aim.y - cue.y, aim.x - cue.x)
        wanted = host.checkpoints + 1
        play_shot(sim, host, guest, Shot(angle, rng.uniform(0.3, 0.8), 0.0))
        assert host.checkpoints >= wanted
    assert not host.match.over
    # set the 8 to be sunk early by whoever is on turn
    aside = {
        b.number: (0.35 + 0.09 * i, 1.15) for i, b in enumerate(host.world.in_play()) if b.number
    }
    aside.update({8: (0.2, 0.2), 0: (0.6, 0.6)})
    host.reset_table(aside)
    run(sim, (host, guest), 5.0, lambda: guest.checkpoints == host.checkpoints and guest.settled)
    player = on_turn(host, guest)
    if player.can_place:
        player.release_cue()
        run(sim, (host, guest), 1.0, lambda pl=player: pl.can_shoot)
    loser = player.me
    play_shot(sim, host, guest, Shot(-3 * math.pi / 4, 0.7, 0.0))
    assert host.match.over and guest.match.over
    assert host.match.winner == guest.match.winner == 1 - loser
    assert host.match.snapshot() == guest.match.snapshot() and same_table(host, guest)
    assert host.desyncs == 0 and guest.desyncs == 0  # reported; one machine, so none
    assert guest.checkpoints >= 5 and guest.bad_frames == 0


# --- the referee puts balls back by the rules: that is not a desync ---
def test_a_pocketed_cue_ball_is_put_back_by_the_referee_without_a_desync():
    sim, host, guest = started(latency=0.01)
    player = on_turn(host, guest)
    others = {
        b.number: (0.5 + 0.1 * (b.number % 8), 1.0 + 0.05 * (b.number // 8))
        for b in host.world.balls[1:]
    }
    host.reset_table({**others, 0: (0.3, 0.3)})
    run(sim, (host, guest), 2.0, lambda: guest.checkpoints == host.checkpoints and guest.settled)
    play_shot(sim, host, guest, Shot(-3 * math.pi / 4, 0.5, 0.0))  # straight into the corner
    assert host.take_judged()[-1].fouls[0] == "foul.scratch"
    assert host.world.balls[0].in_play and guest.world.balls[0].in_play
    assert same_table(host, guest) and host.match.cue_in_hand and host.match.turn == 1 - player.me
    assert guest.desyncs == 0


def test_the_8_on_the_break_racks_again_on_both_machines_without_a_desync():
    sim, host, guest = started(latency=0.01)
    player = on_turn(host, guest)
    host.reset_table({8: (0.2, 0.2), 0: (0.6, 0.6)})
    run(sim, (host, guest), 2.0, lambda: guest.checkpoints == host.checkpoints and guest.settled)
    play_shot(sim, host, guest, Shot(-3 * math.pi / 4, 0.7, 0.0))
    assert host.match.is_break and guest.match.is_break and not host.match.over
    assert host.match.turn == player.me  # the same player breaks again
    assert same_table(host, guest) and guest.desyncs == 0
    assert host.world.balls[0].x == config.HEAD_SPOT[0]
