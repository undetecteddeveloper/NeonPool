"""Transports: the loopback and the seeded network simulator (virtual time)."""

from game.net.transport import NetSim, loopback_pair


def drain(sim: NetSim, end, seconds: float, step: float = 0.001) -> list[tuple[float, bytes]]:
    """Let time pass and note when each frame shows up at `end`."""
    got = []
    for _ in range(round(seconds / step)):
        sim.advance(step)
        got += [(sim.now, f) for f in end.poll()]
    return got


def test_loopback_delivers_at_once_and_in_order():
    a, b = loopback_pair()
    for i in range(5):
        a.send(bytes([i]))
    b.send(b"back")
    assert b.poll() == [bytes([i]) for i in range(5)]
    assert a.poll() == [b"back"]
    assert b.poll() == []


def test_a_frame_is_not_there_before_its_latency_has_passed():
    sim = NetSim(latency_s=0.02)
    sim.a.send(b"x")
    assert sim.b.poll() == []
    sim.advance(0.019)
    assert sim.b.poll() == []
    sim.advance(0.002)
    assert sim.b.poll() == [b"x"]


def test_jitter_stays_inside_its_window():
    sim = NetSim(latency_s=0.02, jitter_s=0.01, seed=4)
    for i in range(300):
        sim.a.send(bytes([i % 256]), reliable=False)
    times = [t for t, _ in drain(sim, sim.b, 0.1, 0.0005)]
    assert len(times) == 300 and 0.0195 <= min(times) and max(times) <= 0.0305


def test_reliable_frames_arrive_whole_and_in_order_whatever_the_loss_and_jitter():
    sim = NetSim(latency_s=0.02, jitter_s=0.02, loss=0.2, seed=5)
    sent = [i.to_bytes(2, "little") for i in range(400)]
    for f in sent:
        sim.a.send(f)
    got = [f for _, f in drain(sim, sim.b, 12.0, 0.005)]
    assert got == sent


def test_a_lost_reliable_frame_costs_a_timeout_and_holds_back_the_ones_behind_it():
    sim = NetSim(latency_s=0.02, loss=0.5, seed=1, rto_s=0.3)
    for i in range(20):
        sim.a.send(bytes([i]))
    got = drain(sim, sim.b, 10.0, 0.005)
    assert [f[0] for _, f in got] == list(range(20))
    assert max(t for t, _ in got) >= 0.3  # at least one frame needed a resend
    assert all(b[0] >= a[0] for a, b in zip(got, got[1:], strict=False))


def test_unreliable_frames_are_really_lost_at_about_the_loss_rate():
    sim = NetSim(latency_s=0.01, loss=0.1, seed=6)
    for _ in range(4000):
        sim.a.send(b"a", reliable=False)
    got = drain(sim, sim.b, 0.1, 0.005)
    assert 0.07 < 1 - len(got) / 4000 < 0.13


def test_the_same_seed_is_the_same_bad_network_and_another_seed_is_not():
    def run(seed):
        sim = NetSim(latency_s=0.02, jitter_s=0.02, loss=0.1, seed=seed)
        for i in range(200):
            sim.a.send(bytes([i % 256]), reliable=bool(i % 2))
        return drain(sim, sim.b, 2.0, 0.002)

    assert run(1) == run(1)
    assert run(1) != run(2)


def test_a_cut_link_reports_disconnected_on_both_ends_and_sending_is_harmless():
    sim = NetSim(latency_s=0.01)
    assert sim.a.connected and sim.b.connected
    sim.a.send(b"in flight")
    sim.b.close()  # either end can hang up
    assert not sim.a.connected and not sim.b.connected
    sim.a.send(b"into the void")
    sim.advance(1.0)
    assert sim.b.poll() == [b"in flight"]  # what was already on its way still arrives


def test_the_endpoints_count_what_they_send():
    a, b = loopback_pair()
    a.send(b"12345")
    a.send(b"678")
    assert (a.frames_sent, a.bytes_sent, b.frames_sent) == (2, 8, 0)
