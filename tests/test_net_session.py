"""Sessions: handshake, coin toss, turns, referee, checkpoints, bad networks (AC4, AC6)."""

import math
import random

import pytest

from game import config
from game.net import protocol as p
from game.net import session as s
from game.net.session import GUEST, HOST, Session, capture_balls
from game.net.transport import NetSim
from game.physics import Shot
from game.rules.eight_ball import FOUL_NO_HIT


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
