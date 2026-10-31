"""Meeting by room code through the relay (Chặng 2): codes, frames both ways, wrong / full /
closed rooms, one side breaking, the straight way on the same network, a game through it.

By default the relay is `server/local_relay.py` on 127.0.0.1. NEONPOOL_RELAY_TEST_URL points the
protocol tests at another relay (the Cloudflare one under `wrangler dev`); tests that need the
local relay's short timers are skipped there.
"""

import json
import math
import os
import random
import time

import pytest
from websockets.sync.client import connect as ws_connect

from game import config
from game.net import protocol as p
from game.net import relay, tcp
from game.net import session as s
from game.physics import Shot
from server.local_relay import Relay

OTHER = os.environ.get("NEONPOOL_RELAY_TEST_URL", "").rstrip("/")
local_only = pytest.mark.skipif(bool(OTHER), reason="needs the local relay's short timers")


def wait(cond, seconds=5.0):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if cond():
            return True
        time.sleep(0.003)
    return False


@pytest.fixture
def local():
    """A local relay with short timers (host grace 1.5 s, stale guest 0.5 s, idle room 1 s)."""
    if OTHER:
        pytest.skip("needs the local relay")
    server = Relay(host_grace_s=1.5, guest_stale_s=0.5, room_idle_s=1.0)
    yield server
    server.close()


@pytest.fixture
def url():
    """The relay under test: the local one (a silent guest is stale after 0.5 s), or
    NEONPOOL_RELAY_TEST_URL."""
    if OTHER:
        yield OTHER
        return
    server = Relay(guest_stale_s=0.5)
    yield server.url
    server.close()


def ready_room(url, door=False):
    room = relay.HostRoom(url, port=0, door=door)
    assert wait(lambda: room.state != relay.CONNECTING), "no answer from the relay"
    assert room.state == relay.READY, room.error
    return room


def join(url, code, lan_wait_s=config.NET_LAN_TRY_S):
    j = relay.Join(code, url, lan_wait_s=lan_wait_s)
    assert wait(lambda: j.state != tcp.CONNECT_CONNECTING, 10.0)
    return j


def joined(url, room):
    """A guest in `room`, with the host's end: (guest transport, host transport, the Join)."""
    j = join(url, room.code)
    assert j.state == tcp.CONNECT_OK, j.error
    guest = j.result()
    got = []
    assert wait(lambda: got.append(room.accept()) or got[-1] is not None)
    return guest, got[-1], j


def drain(transport, count, seconds=5.0):
    got = []
    wait(lambda: len(got.extend(transport.poll()) or got) >= count, seconds)
    return got


def pings(n, base=0):
    return [p.encode(p.Ping(base + i)) for i in range(n)]


# --- AC18: codes, frames both ways, what goes wrong ---
def test_ac18_codes_are_four_letters_without_look_alikes():
    rng = random.Random(1)
    codes = {relay.new_code(rng) for _ in range(500)}
    assert all(relay.is_code(c) for c in codes)
    assert not any(ch in "ILO01" for c in codes for ch in c)
    assert relay.clean_code(" kx-qm9 ") == "KXQM"
    assert relay.clean_code("hello") == "HE"  # (L and O are not code letters)
    assert not relay.is_code("KXQ") and not relay.is_code("KXQO")


def test_ac18_a_room_has_a_code_and_frames_go_both_ways_in_order(url):
    room = ready_room(url)
    assert relay.is_code(room.code)
    guest, host, j = joined(url, room)
    assert not j.straight  # (no door on this network: through the relay)
    for frame in pings(40):
        guest.send(frame)
    assert drain(host, 40) == pings(40)
    for frame in pings(40, 100):
        host.send(frame)
    assert drain(guest, 40) == pings(40, 100)
    guest.close()
    room.close()


def test_ac18_a_wrong_code_a_full_room_and_a_closed_room_say_so(url):
    assert join(url, "ZZZZ").error == relay.ERR_NO_ROOM
    assert relay.look(url, "KX")["why"] == relay.ERR_BAD_CODE
    room = ready_room(url)
    guest, host, _ = joined(url, room)
    guest.send(p.encode(p.Ping(1)))  # (a live guest: it has just spoken)
    second = join(url, room.code)
    assert second.state == tcp.CONNECT_FAILED and second.error == relay.ERR_FULL
    room.close()
    assert wait(lambda: not guest.connected)  # closing the room sends the guest away
    assert wait(lambda: relay.look(url, room.code)["why"] == relay.ERR_NO_ROOM)


def test_ac18_no_relay_and_no_internet_are_told_apart():
    assert join("", "KXQM").error == relay.ERR_NO_SERVER
    nobody = join("ws://127.0.0.1:9", "KXQM")
    assert nobody.error == relay.ERR_OFFLINE
    room = relay.HostRoom("", door=False)
    assert room.state == relay.FAILED and room.error == relay.ERR_NO_SERVER
    lost = relay.HostRoom("ws://127.0.0.1:9", door=False)
    assert wait(lambda: lost.state == relay.FAILED) and lost.error == relay.ERR_OFFLINE


@local_only
def test_ac22_requests_carry_the_games_own_name_because_cloudflare_turns_the_default_away(local):
    """Found on the real relay (2026-10-31): `Python-urllib` gets error 1010 and was read as
    "the server is busy". The local relay turns that name away too."""
    import urllib.error
    import urllib.request

    plain = urllib.request.Request(f"http://127.0.0.1:{local.port}/v1/look?code=ZZZZ")
    with pytest.raises(urllib.error.HTTPError) as caught:
        urllib.request.urlopen(plain, timeout=5)
    assert caught.value.code == 403
    assert relay.look(local.url, "ZZZZ") == {"ok": False, "why": relay.ERR_NO_ROOM}
    assert relay.USER_AGENT.startswith("NeonPool/")


def test_ac18_an_old_relay_reads_as_another_version(url):
    with pytest.raises(Exception) as caught:
        ws_connect(f"{url}/v0/host", open_timeout=5).close()
    assert "404" in str(caught.value)
    assert relay._status_error(404) == relay.ERR_VERSION


# --- AC19: one side breaks, the channel breaks; coming back ---
def test_ac19_a_guest_that_leaves_ends_its_channel_and_the_next_one_gets_a_new_one(url):
    room = ready_room(url)
    guest, host, _ = joined(url, room)
    guest.close()
    assert wait(lambda: not host.connected)
    guest2, host2, _ = joined(url, room)
    assert host2 is not host
    host.send(p.encode(p.Ping(7)))  # the old channel is dead: nothing reaches the new guest
    host2.send(p.encode(p.Ping(8)))
    assert drain(guest2, 1) == [p.encode(p.Ping(8))]
    guest2.close()
    room.close()


def test_ac19_the_hosts_link_breaking_ends_the_guests_and_the_host_takes_the_room_back(url):
    room = ready_room(url)
    guest, host, _ = joined(url, room)
    code = room.code
    room._ws.close()  # the host's link to the relay dies (the room's own thread notices)
    assert wait(lambda: not guest.connected and not host.connected)
    assert wait(lambda: room.state == relay.READY and room._ws is not None and room.code == code)
    guest2, host2, _ = joined(url, room)  # the guest comes back to the same code
    guest2.send(p.encode(p.Ping(3)))
    assert drain(host2, 1) == [p.encode(p.Ping(3))]
    host2.send(p.encode(p.Ping(4)))
    assert drain(guest2, 1) == [p.encode(p.Ping(4))]
    guest2.close()
    room.close()


def test_ac19_a_stranger_cannot_take_a_room_without_its_key(url):
    room = ready_room(url)
    with ws_connect(f"{url}/v1/host?code={room.code}&key=00", open_timeout=5) as ws:
        assert json.loads(ws.recv(timeout=5)) == {"t": "error", "why": relay.ERR_GONE}
    guest, host, _ = joined(url, room)  # the room is still the host's
    guest.send(p.encode(p.Ping(1)))
    assert drain(host, 1) == [p.encode(p.Ping(1))]
    room.close()


def test_ac19_a_guest_gone_silent_gives_its_place_to_whoever_comes(url):
    room = ready_room(url)
    old_guest, _, _ = joined(url, room)
    stale = 0.5 if not OTHER else 4.0
    time.sleep(stale + 0.6)  # the old link says nothing (as one that died without a word)
    guest, host, _ = joined(url, room)
    guest.send(p.encode(p.Ping(9)))
    assert drain(host, 1) == [p.encode(p.Ping(9))]
    assert wait(lambda: not old_guest.connected)
    room.close()


@local_only
def test_ac19_a_host_gone_too_long_loses_the_room_and_an_idle_room_closes(local):
    room = ready_room(local.url)
    room._closed = True  # (the host does not come back)
    room._ws.close()
    assert wait(lambda: relay.look(local.url, room.code)["why"] == relay.ERR_AWAY)
    assert wait(lambda: relay.look(local.url, room.code)["why"] == relay.ERR_NO_ROOM, 3.0)
    idle = ready_room(local.url)
    assert wait(lambda: idle.state == relay.FAILED, 4.0) and idle.error == relay.ERR_IDLE


# --- AC20: the straight way on the same network ---
def test_ac20_on_the_same_network_the_guest_goes_straight_to_the_host(url):
    room = ready_room(url, door=True)
    assert room.door is not None
    guest, host, j = joined(url, room)
    assert j.straight and isinstance(guest, tcp.TcpTransport) and isinstance(host, tcp.TcpTransport)
    guest.send(p.encode(p.Ping(5)))
    assert drain(host, 1) == [p.encode(p.Ping(5))]
    guest.close()
    room.close()


def test_ac20_a_door_that_does_not_answer_sends_the_guest_through_the_relay(url):
    room = ready_room(url, door=True)
    room.door.close()  # (a firewall that said no)
    guest, host, j = joined(url, room)
    assert not j.straight and isinstance(guest, relay.WsTransport)
    guest.send(p.encode(p.Ping(6)))
    assert drain(host, 1) == [p.encode(p.Ping(6))]
    room.close()


def test_ac20_the_door_shuts_on_anyone_without_the_rooms_secret():
    door = tcp.TcpListener(0, "127.0.0.1", secret=b"s" * tcp.SECRET_LEN)
    plain = tcp.Connector("127.0.0.1", door.port)
    wrong = tcp.Connector("127.0.0.1", door.port, secret=b"x" * tcp.SECRET_LEN)
    right = tcp.Connector("127.0.0.1", door.port, secret=b"s" * tcp.SECRET_LEN)
    assert wait(lambda: right.state == tcp.CONNECT_OK)
    taken = []
    assert wait(lambda: taken.append(door.accept()) or taken[-1] is not None)
    assert not wait(lambda: door.accept() is not None, tcp.ADMIT_TIMEOUT_S + 0.5)
    for knock in (plain, wrong):
        t = knock.result()
        assert t is None or wait(lambda t=t: not t.connected)
    door.close()


def test_ac20_lan_info_goes_there_and_back():
    secret = bytes(range(16))
    text = relay.lan_info([("192.168.1.5", 47474), ("10.0.0.2", 5000)], secret)
    assert relay.parse_lan(text) == ([("192.168.1.5", 47474), ("10.0.0.2", 5000)], secret)
    for bad in ("", "1.2.3.4:5", "1.2.3.4:5;zz", "x;" + secret.hex(), "1.2.3.4:0;" + secret.hex()):
        assert relay.parse_lan(bad) is None, bad


# --- AC21: a game through the relay, with a broken link in the middle ---
def test_ac21_a_game_through_the_relay_survives_a_broken_link(url):
    room = ready_room(url)
    guest_t, host_t, j = joined(url, room)
    host = s.Session(host_t, True, "Hoa", rng=random.Random(2))
    guest = s.Session(guest_t, False, "Nam")

    def tick():
        host.update(0.02)
        guest.update(0.02)
        time.sleep(0.001)

    assert wait(lambda: (tick(), host.playing and guest.playing)[1], 10.0)
    host.set_relink(relay.HostRelink(room))
    guest.set_relink(relay.GuestRelink(j, every_s=0.1))
    assert wait(lambda: (tick(), host._toss_left <= 0 and guest._toss_left <= 0)[1], 10.0)
    shooter = host if host.match.turn == s.HOST else guest
    assert shooter.shoot(Shot(math.pi, 0.1, 0.0)) is not None
    assert wait(lambda: (tick(), host.checkpoints == 1 and guest.checkpoints == 1)[1], 10.0)
    guest_t._ws.close()  # the guest's link dies
    assert wait(lambda: (tick(), host.link_down_s is not None and guest.link_down_s is not None)[1])
    assert wait(lambda: (tick(), host.linked and guest.linked and host.rejoins == 1)[1], 15.0)
    assert wait(lambda: (tick(), host.settled and guest.settled)[1])
    assert s.capture_balls(host.world) == s.capture_balls(guest.world)
    assert host.match.snapshot() == guest.match.snapshot()
    mover = host if host.match.turn == s.HOST else guest
    if mover.can_place:
        assert mover.place_cue(1.0, 0.4)
        mover.release_cue()
        assert wait(lambda: (tick(), mover.can_shoot)[1])
    assert mover.shoot(Shot(math.pi, 0.1, 0.0)) is not None
    assert wait(lambda: (tick(), host.checkpoints >= 3 and guest.checkpoints >= 3)[1], 10.0)
    assert guest.desyncs == 0
    guest.leave()
    assert wait(lambda: (tick(), host.phase == s.CLOSED)[1])
