"""The start of a two-player game as a timeline (game/net/toss.py): a look at the table, the coin
waits, spins, lies there; the same numbers on both machines."""

import math

import pytest

from game import config
from game.net import toss
from game.net.toss import Toss


def test_a_rematch_starts_slower_than_the_first_game_and_both_are_long_enough_to_read():
    first, again = toss.total_s(False), toss.total_s(True)
    assert again - first == pytest.approx(config.NET_TOSS_LEAD_AGAIN_S - config.NET_TOSS_LEAD_S)
    assert 4.5 < first < again < 7.0
    assert config.NET_TOSS_LEAD_AGAIN_S > config.NET_TOSS_SCORE_AT_S + 0.8  # time to see the point


@pytest.mark.parametrize("again", [False, True])
def test_the_phases_come_in_order_and_cover_the_whole_start(again):
    tt = Toss(again, 0)
    seen = []
    for i in range(int(tt.total_s * 100) + 50):
        ph = tt.phase(i / 100)
        if not seen or seen[-1] != ph:
            seen.append(ph)
    assert seen == [toss.LEAD, toss.HOLD, toss.FLIP, toss.LAND, toss.DONE]
    assert tt.phase(tt.total_s - 0.01) == toss.LAND and tt.phase(tt.total_s) == toss.DONE


def test_the_table_is_dark_for_the_coin_and_light_again_at_both_ends():
    tt = Toss(False, 0)
    assert tt.dim(0.0) == 0.0 and tt.dim(tt.lead_s - config.NET_TOSS_DIM_S - 0.01) == 0.0
    assert 0.0 < tt.dim(tt.lead_s - 0.1) < 1.0  # darkening
    assert tt.dim(tt.lead_s) == tt.dim(tt.flip_at) == tt.dim(tt.land_at) == 1.0
    assert 0.0 < tt.dim(tt.total_s - 0.1) < 1.0  # lighting up
    assert tt.dim(tt.total_s) == 0.0
    ks = [tt.dim(i / 100) for i in range(int(tt.total_s * 100))]
    assert all(0.0 <= k <= 1.0 for k in ks)


@pytest.mark.parametrize("breaker", [0, 1])
def test_the_coin_slows_down_and_lands_face_on_showing_the_breaker(breaker):
    tt = Toss(False, breaker)
    angles = [tt.spin(i / 100) for i in range(int(tt.total_s * 100) + 1)]
    assert angles[0] == 0.0 and all(b >= a for a, b in zip(angles, angles[1:], strict=False))
    end = tt.spin(tt.total_s)
    assert end == pytest.approx(math.pi * (6 + breaker))
    assert round(end / math.pi) % 2 == breaker  # the face that is up is the breaker's
    assert abs(math.cos(end)) == pytest.approx(1.0)  # face-on, not edge-on
    speeds = [
        tt.spin(tt.flip_at + 0.1 * (i + 1)) - tt.spin(tt.flip_at + 0.1 * i) for i in range(14)
    ]
    assert speeds[0] > speeds[7] > speeds[13] > 0  # the end is slow: that is where the doubt is


def test_the_coin_is_thrown_up_and_comes_down_and_turns_over_as_many_times_as_it_should():
    tt = Toss(False, 1)
    assert tt.hop(tt.flip_at - 0.01) == 0.0 and tt.hop(tt.land_at + 0.01) == 0.0
    mid = tt.hop(tt.flip_at + config.NET_TOSS_FLIP_S / 2)
    assert mid == pytest.approx(1.0)
    assert tt.faces_seen(tt.flip_at) == 0 and tt.faces_seen(tt.total_s) == 7  # 6 + the breaker
    counts = [tt.faces_seen(i / 100) for i in range(int(tt.total_s * 100))]
    assert counts == sorted(counts) and set(counts) == set(range(8))


@pytest.mark.parametrize("again", [False, True])
def test_the_breaker_is_known_only_once_the_coin_has_landed(again):
    tt = Toss(again, 1)
    assert not tt.breaker_known(0.0) and not tt.breaker_known(tt.flip_at)
    assert not tt.breaker_known(tt.land_at - 0.01)  # still in the air
    assert tt.breaker_known(tt.land_at) and tt.breaker_known(tt.total_s)
