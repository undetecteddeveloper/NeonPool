"""Follow / draw on the cue ball (docs/GAME_DESIGN.md, the spin section; workflow/physics.md)."""

import math

import pytest

from game.config import BALL_R, PHYSICS_DT, SPIN_SETS, TABLE_L, TABLE_W
from game.physics import BallHitBall, Shot, World

D = 2 * BALL_R
SETS = list(SPIN_SETS.values())
IDS = [s.key for s in SETS]


def hit_head_on(spin_set, spin: float, power: float = 0.6, gap: float = 0.3) -> float:
    """Metres the cue ball travels after a straight hit on a still ball (+ = on, - = back).

    The hit ball is taken off the table at once, so only the cue ball is measured.
    """
    w = World(rack=False, spin=spin_set)
    w.place(0, 0.4, TABLE_W / 2)
    w.place(1, 0.4 + D + gap, TABLE_W / 2)
    w.apply(Shot(0.0, power, spin))
    hit_x = None
    for _ in range(int(30 / PHYSICS_DT)):
        events = w.step()
        if hit_x is None and any(isinstance(e, BallHitBall) for e in events):
            hit_x = w.balls[0].x
            w.balls[1].in_play = False
        if hit_x is not None and w.at_rest():
            return w.balls[0].x - hit_x
    raise AssertionError("never hit, or never came to rest")


def rest_after(world: World, seconds: float = 60) -> None:
    for _ in range(int(seconds / PHYSICS_DT)):
        world.step()
        if world.at_rest():
            return
    raise AssertionError(f"balls still moving after {seconds} s")


@pytest.mark.parametrize("ss", SETS, ids=IDS)
def test_high_hit_follows_low_hit_draws_centre_stops(ss):
    follow, centre, draw = (hit_head_on(ss, s) for s in (1.0, 0.0, -1.0))
    assert follow > 0.10, "a high hit must run the cue ball on past the hit"
    assert draw < -0.05, "a low hit must bring the cue ball back"
    assert abs(centre) < 0.05, "a centre hit leaves the cue ball where it hit"
    assert draw < centre < follow


@pytest.mark.parametrize("ss", SETS, ids=IDS)
def test_more_spin_more_effect(ss):
    runs = [hit_head_on(ss, s) for s in (0.0, 0.5, 1.0)]
    assert runs[0] < runs[1] < runs[2]


def test_named_sets_get_stronger_in_order():
    runs = [hit_head_on(SPIN_SETS[k], 1.0) for k in ("NHE", "VUA", "MANH")]
    assert runs == sorted(runs)
    draws = [hit_head_on(SPIN_SETS[k], -1.0) for k in ("NHE", "VUA", "MANH")]
    assert draws == sorted(draws, reverse=True)


@pytest.mark.parametrize("ss", SETS, ids=IDS)
def test_spin_zero_keeps_no_slip(ss):
    w = World(spin=ss)
    w.apply(Shot(0.3, 0.8, 0.0))
    assert all(b.qx == 0.0 and b.qy == 0.0 for b in w.balls)


@pytest.mark.parametrize("ss", SETS, ids=IDS)
def test_only_the_cue_ball_gets_slip(ss):
    w = World(spin=ss)
    w.apply(Shot(0.0, 0.8, 1.0))
    assert w.balls[0].qx > 0.0 and w.balls[0].qy == 0.0
    assert all(b.qx == 0.0 and b.qy == 0.0 for b in w.balls[1:])


def test_slip_follows_the_aim_line():
    w = World(rack=False)
    w.place(0, 1.0, 0.6)
    angle = math.radians(40)
    w.apply(Shot(angle, 0.5, -1.0))  # draw: slip runs against the aim
    cue = w.balls[0]
    turn = math.atan2(cue.qy, cue.qx) - angle  # half a turn round, however the angle wraps
    assert math.cos(turn) == pytest.approx(-1.0)


@pytest.mark.parametrize("ss", SETS, ids=IDS)
def test_feather_light_shot_gets_no_push_out_of_nothing(ss):
    w = World(rack=False, spin=ss)
    w.place(0, 1.0, 0.6)
    w.apply(Shot(0.0, 0.004, -1.0))  # a pull of a few pixels with full draw
    rest_after(w)
    assert abs(w.balls[0].x - 1.0) < 0.02


@pytest.mark.parametrize("spin", [1.0, -1.0, 0.5])
@pytest.mark.parametrize("ss", SETS, ids=IDS)
def test_spin_shots_stay_on_the_table_and_come_to_rest(ss, spin):
    for angle, power in ((0.0, 1.0), (0.7, 0.6), (math.pi, 0.9)):
        w = World(spin=ss)
        w.apply(Shot(angle, power, spin))
        for _ in range(int(60 / PHYSICS_DT)):
            w.step()
            for b in w.in_play():
                assert -1e-9 <= b.x <= TABLE_L + 1e-9 and -1e-9 <= b.y <= TABLE_W + 1e-9
            if w.at_rest():
                break
        else:
            raise AssertionError("still moving after 60 s")
        assert all(b.qx == 0.0 and b.qy == 0.0 for b in w.balls)  # slip is always used up


def test_same_seed_same_spin_shot_same_result():
    def final(seed):
        w = World(seed=seed)
        w.apply(Shot(0.02, 0.9, 0.7))
        rest_after(w)
        return [(b.x, b.y, b.in_play) for b in w.balls]

    assert final(5) == final(5)


def test_placing_or_racking_the_cue_ball_clears_slip():
    w = World(rack=False)
    w.place(0, 1.0, 0.6)
    w.apply(Shot(0.0, 0.5, 1.0))
    assert w.balls[0].qx != 0.0
    w.place(0, 0.5, 0.5)
    assert (w.balls[0].qx, w.balls[0].qy) == (0.0, 0.0)
    w.apply(Shot(0.0, 0.5, 1.0))
    w.rack()
    assert (w.balls[0].qx, w.balls[0].qy) == (0.0, 0.0)


def test_follow_pulls_a_cut_shot_along_the_aim_line():
    """After a cut the cue ball leaves at an angle; follow drags it on along the original aim."""

    def cue_end(spin):
        w = World(rack=False)
        w.place(0, 0.5, 0.6)
        w.place(1, 0.5 + 0.5, 0.6 + 0.4 * D)  # off-centre: a cut
        w.apply(Shot(0.0, 0.5, spin))
        for _ in range(int(2 / PHYSICS_DT)):  # long enough to hit, short of the wall
            events = w.step()
            if any(isinstance(e, BallHitBall) for e in events):
                w.balls[1].in_play = False
        rest_after(w)
        return w.balls[0].x

    assert cue_end(1.0) > cue_end(0.0) + 0.05 > cue_end(-1.0) + 0.05
