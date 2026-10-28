import math

import pytest

from game.config import BALL_R, TABLE_L, TABLE_W
from game.physics import World, first_contact


def empty() -> World:
    return World(rack=False)


def test_ray_hits_cushion_when_nothing_in_the_way():
    w = empty()
    w.place(0, 0.5, 0.6)
    c = first_contact(w.balls, (0.5, 0.6), (1.0, 0.0))
    assert c.kind == "cushion" and c.ball is None and c.object_dir is None
    assert c.distance == pytest.approx(TABLE_L - BALL_R - 0.5)
    assert c.point == pytest.approx((TABLE_L - BALL_R, 0.6))


def test_ray_hits_first_ball_head_on():
    w = empty()
    w.place(0, 0.5, 0.6)
    w.place(1, 1.0, 0.6)
    w.place(2, 1.5, 0.6)
    c = first_contact(w.balls, (0.5, 0.6), (1.0, 0.0))
    assert c.kind == "ball" and c.ball == 1
    assert c.distance == pytest.approx(0.5 - 2 * BALL_R)
    assert c.object_dir == pytest.approx((1.0, 0.0))


def test_thin_cut_pushes_the_object_ball_sideways_and_stays_at_contact_distance():
    w = empty()
    w.place(0, 0.5, 0.6)
    w.place(1, 1.0, 0.6 + BALL_R)  # offset by half a contact distance: a cut shot
    c = first_contact(w.balls, (0.5, 0.6), (1.0, 0.0))
    assert c.kind == "ball" and c.ball == 1
    assert math.hypot(c.point[0] - 1.0, c.point[1] - (0.6 + BALL_R)) == pytest.approx(2 * BALL_R)
    assert c.object_dir[1] > 0.0  # pushed downwards (+y)


def test_ray_misses_a_ball_off_to_the_side():
    w = empty()
    w.place(0, 0.5, 0.6)
    w.place(1, 1.0, 0.6 + 3 * BALL_R)
    assert first_contact(w.balls, (0.5, 0.6), (1.0, 0.0)).kind == "cushion"


def test_ray_ignores_pocketed_balls_and_the_cue_ball():
    w = empty()
    w.place(0, 0.5, 0.6)
    w.place(1, 1.0, 0.6)
    w.balls[1].in_play = False
    assert first_contact(w.balls, (0.5, 0.6), (1.0, 0.0)).kind == "cushion"


def test_ray_direction_need_not_be_unit_and_zero_is_rejected():
    w = empty()
    w.place(0, 0.5, 0.6)
    a = first_contact(w.balls, (0.5, 0.6), (3.0, 0.0))
    b = first_contact(w.balls, (0.5, 0.6), (1.0, 0.0))
    assert a.distance == pytest.approx(b.distance)
    with pytest.raises(ValueError):
        first_contact(w.balls, (0.5, 0.6), (0.0, 0.0))


def test_vertical_ray_hits_the_top_cushion():
    w = empty()
    w.place(0, 0.5, 0.6)
    c = first_contact(w.balls, (0.5, 0.6), (0.0, -1.0))
    assert c.distance == pytest.approx(0.6 - BALL_R) and c.point[1] == pytest.approx(BALL_R)
    assert TABLE_W > 0
