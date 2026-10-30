"""The other player's cue on my screen: newest packet only, about a frame behind, no swing."""

import math

from game import config
from game.net import protocol as p
from game.net.remote_cue import RemoteCue


def aim(n, state=p.AIM_PULLING, angle=1.0, pull=100.0):
    return p.Aim(n, state, p.quantize_angle(angle), p.quantize_pull(pull))


def test_a_cue_comes_back_at_its_angle_without_swinging_from_where_it_was():
    cue = RemoteCue()
    assert not cue.visible
    cue.receive(aim(1, p.AIM_RESTING, 2.0))
    assert cue.visible and abs(cue.angle - 2.0) < 1e-3 and cue.pull == 0.0


def test_a_late_packet_is_dropped_and_the_numbers_wrap_around():
    cue = RemoteCue()
    assert cue.receive(aim(10)) and cue.receive(aim(12))
    assert not cue.receive(aim(11))  # arrived after 12
    assert not cue.receive(aim(12))  # a repeat
    assert cue.dropped == 2 and cue.received == 2
    cue2 = RemoteCue()
    assert cue2.receive(aim(254)) and cue2.receive(aim(255)) and cue2.receive(aim(1))
    assert not cue2.receive(aim(255))


def test_the_picture_closes_on_the_newest_packet_within_about_a_frame():
    cue = RemoteCue()
    cue.receive(aim(1, angle=0.0, pull=0.0))
    cue.receive(aim(2, angle=1.0, pull=200.0))
    cue.update(1 / 60)
    assert cue.angle > 0.5 and cue.pull > 100  # one frame: more than half way
    for _ in range(10):
        cue.update(1 / 60)
    assert abs(cue.angle - 1.0) < 0.01


def test_there_is_no_buffer_an_older_target_is_never_visited():
    cue = RemoteCue()
    cue.receive(aim(1, angle=0.0, pull=0.0))
    cue.receive(aim(2, angle=1.0))
    cue.receive(aim(3, angle=-1.0))  # the newest wins; angle 1.0 is never shown
    seen = []
    for _ in range(30):
        cue.update(1 / 60)
        seen.append(cue.angle)
    assert max(seen) < 0.05  # it never swings toward 1.0


def test_it_turns_the_short_way_round_the_back():
    cue = RemoteCue()
    cue.receive(aim(1, p.AIM_RESTING, math.pi - 0.1))
    cue.receive(aim(2, p.AIM_RESTING, -math.pi + 0.1))
    cue.update(1 / 60)
    assert abs(((cue.angle - math.pi + 0.1 + math.pi) % (2 * math.pi)) - math.pi) < 0.2


def test_hiding_hides_and_the_power_follows_the_local_curve():
    cue = RemoteCue()
    cue.receive(aim(1, pull=config.MAX_DRAG_PX))
    assert abs(cue.power - 1.0) < 0.01
    cue.receive(aim(2, p.AIM_HIDDEN, 0.0, 0.0))
    assert not cue.visible
    cue.update(1.0)  # does nothing, does not raise
