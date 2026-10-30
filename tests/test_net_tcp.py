"""Real sockets on 127.0.0.1: frames in order, hanging up, a full room, a session over TCP."""

import math
import random
import socket
import struct
import time

from game import config
from game.net import protocol as p
from game.net import session as s
from game.net import tcp
from game.physics import Shot


def wait(cond, seconds=3.0):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if cond():
            return True
        time.sleep(0.002)
    return False


def connect(listener):
    conn = tcp.Connector("127.0.0.1", listener.port)
    assert wait(lambda: conn.state != tcp.CONNECT_CONNECTING)
    assert conn.state == tcp.CONNECT_OK
    client = conn.result()
    accepted = []
    assert wait(lambda: accepted.append(listener.accept()) or accepted[-1] is not None)
    return client, accepted[-1]


def drain(transport, count, seconds=3.0):
    got = []
    wait(lambda: len(got.extend(transport.poll()) or got) >= count, seconds)
    return got


def test_frames_cross_in_both_directions_whole_and_in_order():
    listener = tcp.TcpListener(0, "127.0.0.1")
    client, server = connect(listener)
    sent = [p.encode(p.Ping(i)) for i in range(500)]
    for f in sent:
        client.send(f)
    server.send(p.encode(p.Welcome("Hoa", 7)))
    assert drain(server, 500) == sent
    assert drain(client, 1) == [p.encode(p.Welcome("Hoa", 7))]
    listener.close()


def test_hanging_up_delivers_what_was_queued_then_the_other_side_sees_it_gone():
    listener = tcp.TcpListener(0, "127.0.0.1")
    client, server = connect(listener)
    client.send(p.encode(p.Bye(p.BYE_LEAVE)))
    client.close()
    assert drain(server, 1) == [p.encode(p.Bye(p.BYE_LEAVE))]
    assert wait(lambda: not server.connected) and not client.connected
    listener.close()


def test_a_stream_with_a_wild_length_is_hung_up_on():
    listener = tcp.TcpListener(0, "127.0.0.1")
    client, server = connect(listener)
    client._sock.sendall(struct.pack("<H", 0) + b"junk")
    assert wait(lambda: not server.connected)
    listener.close()


def test_a_third_person_is_told_the_room_is_full():
    listener = tcp.TcpListener(0, "127.0.0.1")
    client, server = connect(listener)
    knock = tcp.Connector("127.0.0.1", listener.port)
    assert wait(lambda: knock.state == tcp.CONNECT_OK)
    third = knock.result()
    got = drain(third, 1)
    assert got and p.decode(got[0]) == p.Reject(p.REJECT_BUSY)
    assert server.connected  # the guest who was there first is not disturbed
    listener.close()


def test_joining_a_room_that_is_not_there_fails_with_a_reason_and_does_not_hang():
    listener = tcp.TcpListener(0, "127.0.0.1")
    port = listener.port
    listener.close()
    conn = tcp.Connector("127.0.0.1", port, timeout=2.0)
    assert wait(lambda: conn.state == tcp.CONNECT_FAILED)
    assert conn.error in (tcp.ERR_REFUSED, tcp.ERR_UNREACHABLE, tcp.ERR_TIMEOUT)
    bad = tcp.Connector("no such host.invalid", 1, timeout=2.0)
    assert wait(lambda: bad.state == tcp.CONNECT_FAILED) and bad.error is not None


def test_a_run_of_unreliable_frames_waiting_to_go_out_is_cut_to_the_newest():
    q = tcp.OutQueue()
    q.put(b"r1", True)
    for i in range(100):
        q.put(b"u%d" % i, False)
    q.put(b"r2", True)
    q.put(b"u-last", False)
    q.finish()
    assert q.take() == [b"r1", b"u99", b"r2", b"u-last"]
    assert q.take() is None


def test_addresses_are_parsed_or_refused():
    assert tcp.parse_address("192.168.1.5") == ("192.168.1.5", config.NET_PORT)
    assert tcp.parse_address(" 192.168.1.5:5000 ") == ("192.168.1.5", 5000)
    assert tcp.parse_address("host-name.local:1") == ("host-name.local", 1)
    for bad in ("", ":80", "a b", "1.2.3.4:", "1.2.3.4:0", "1.2.3.4:70000", "1.2.3.4:x", "ä.com"):
        assert tcp.parse_address(bad) is None, bad
    assert tcp.local_address().count(".") == 3


def test_a_whole_game_start_and_a_shot_work_over_real_sockets():
    listener = tcp.TcpListener(0, "127.0.0.1")
    client, server = connect(listener)
    host = s.Session(server, True, "Hoa", rng=random.Random(2))
    guest = s.Session(client, False, "Nam")

    def tick():
        host.update(0.02)
        guest.update(0.02)
        time.sleep(0.001)

    assert wait(lambda: (tick(), host.playing and guest.playing)[1])
    assert host.names == guest.names == ["Hoa", "Nam"] and host.breaker == guest.breaker
    shooter = host if host.match.turn == s.HOST else guest
    assert shooter.shoot(Shot(math.pi, 0.1, 0.0)) is not None  # a soft miss: a foul
    assert wait(lambda: (tick(), host.checkpoints == 1 and guest.checkpoints == 1)[1], 10.0)
    assert s.capture_balls(host.world) == s.capture_balls(guest.world) and guest.desyncs == 0
    guest.leave()
    assert wait(lambda: (tick(), host.close_reason == s.CLOSE_LEFT)[1])
    listener.close()


def test_ac14_the_guest_comes_back_over_real_sockets_after_its_connection_died():
    listener = tcp.TcpListener(0, "127.0.0.1")
    client, server = connect(listener)
    host = s.Session(server, True, "Hoa", rng=random.Random(2))
    guest = s.Session(client, False, "Nam")

    def tick():
        host.update(0.02)
        guest.update(0.02)
        time.sleep(0.001)

    assert wait(lambda: (tick(), host.playing and guest.playing)[1])
    host.set_relink(tcp.HostRelink(listener))
    guest.set_relink(tcp.GuestRelink("127.0.0.1", listener.port, every_s=0.1))
    shooter = host if host.match.turn == s.HOST else guest
    assert shooter.shoot(Shot(math.pi, 0.1, 0.0)) is not None
    assert wait(lambda: (tick(), host.checkpoints == 1 and guest.checkpoints == 1)[1], 10.0)
    client._sock.shutdown(socket.SHUT_RDWR)  # the guest's connection dies, abruptly
    assert wait(lambda: (tick(), host.link_down_s is not None and guest.link_down_s is not None)[1])
    assert host.playing and guest.playing  # nobody gave up the game
    assert wait(lambda: (tick(), host.linked and guest.linked and host.rejoins == 1)[1], 10.0)
    assert wait(lambda: (tick(), host.settled and guest.settled)[1])
    assert s.capture_balls(host.world) == s.capture_balls(guest.world)
    assert host.match.snapshot() == guest.match.snapshot()
    # the game goes on over the new connection
    mover = host if host.match.turn == s.HOST else guest
    if mover.can_place:
        assert mover.place_cue(1.0, 0.4)
        mover.release_cue()
        assert wait(lambda: (tick(), mover.can_shoot)[1])
    assert mover.shoot(Shot(math.pi, 0.1, 0.0)) is not None
    assert wait(lambda: (tick(), host.checkpoints >= 3 and guest.checkpoints >= 3)[1], 10.0)
    guest.leave()
    assert wait(lambda: (tick(), host.phase == s.CLOSED)[1])
    # leaving closed the room's door: nobody can knock any more
    refused = tcp.Connector("127.0.0.1", listener.port)
    assert wait(lambda: refused.state != tcp.CONNECT_CONNECTING)
    assert refused.state == tcp.CONNECT_FAILED


def test_a_guest_that_cannot_reach_the_host_keeps_trying_and_then_gives_up():
    listener = tcp.TcpListener(0, "127.0.0.1")
    port = listener.port
    listener.close()  # nobody is home
    relink = tcp.GuestRelink("127.0.0.1", port, every_s=0.05)
    seen = []
    assert not wait(lambda: seen.append(relink.poll()) or seen[-1] is not None, 0.6)
    relink.close()
    assert relink.poll() is None
