"""Physics invariants (workflow/physics.md). Changing physics must not make these red."""

import math
from dataclasses import replace

import pytest

from game.config import (
    BALL_R,
    FEEL_ORDER,
    FEEL_SETS,
    HEAD_SPOT,
    PHYSICS_DT,
    POCKETS,
    TABLE_L,
    TABLE_W,
)
from game.physics import BallHitBall, BallHitCushion, BallPocketed, Shot, World

D = 2 * BALL_R
EPS = 1e-9
# Worst residual overlap measured in the densest jam (full-power break): ~4 um with 16 relaxation
# passes (300 um with none). 10 um is invisible (< 0.004 px on screen) yet would catch a regression.
OVERLAP_TOL = 1e-5
MAX_REST_SECONDS = 60


def run_until_rest(world: World, max_seconds: float = MAX_REST_SECONDS, on_step=None) -> list:
    events = []
    for _ in range(int(max_seconds / PHYSICS_DT)):
        events += world.step()
        if on_step:
            on_step(world)
        if world.at_rest():
            return events
    raise AssertionError(f"balls still moving after {max_seconds} s")


def lossless() -> World:
    """Empty table, no friction, perfectly elastic: for exact collision checks."""
    feel = replace(FEEL_SETS["TRON"], roll_decel=0.0, cushion_e=1.0, ball_e=1.0)
    return World(rack=False, feel=feel)


# --- AC1: setup -----------------------------------------------------------------------
def test_rack_layout():
    w = World()
    live = w.in_play()
    assert len(live) == 16
    assert sorted(b.number for b in w.balls) == list(range(16))
    for i, a in enumerate(live):
        assert BALL_R <= a.x <= TABLE_L - BALL_R and BALL_R <= a.y <= TABLE_W - BALL_R
        for b in live[i + 1 :]:
            assert math.hypot(a.x - b.x, a.y - b.y) >= D - EPS
    assert (w.balls[0].x, w.balls[0].y) == HEAD_SPOT
    assert w.balls[8].y == pytest.approx(TABLE_W / 2)  # 8 ball in the middle of row 3
    # the two back corners are one solid and one stripe
    back = sorted((b for b in w.balls[1:]), key=lambda b: b.x)[-5:]
    corners = {min(back, key=lambda b: b.y).number, max(back, key=lambda b: b.y).number}
    assert sum(1 for n in corners if n < 8) == 1 and sum(1 for n in corners if n > 8) == 1


def test_all_rack_balls_distinct_and_cover_1_to_15():
    from game.config import RACK_ORDER

    assert sorted(RACK_ORDER) == list(range(1, 16))


# --- AC2: invariants ---------------------------------------------------------------------
@pytest.mark.parametrize("angle", [0.0, 0.03, -0.2, 1.0, 2.5])
@pytest.mark.parametrize("feel_key", FEEL_ORDER)
def test_no_overlap_inside_table_and_rest(angle, feel_key):
    w = World(feel=FEEL_SETS[feel_key])
    w.apply(Shot(angle, 1.0))

    def check(world):
        live = world.in_play()
        for i, a in enumerate(live):
            assert -EPS <= a.x <= TABLE_L + EPS and -EPS <= a.y <= TABLE_W + EPS, "left the table"
            for b in live[i + 1 :]:
                assert math.hypot(a.x - b.x, a.y - b.y) >= D - OVERLAP_TOL, "balls overlap"

    run_until_rest(w, on_step=check)


def test_energy_never_increases():
    w = World()
    w.apply(Shot(0.0, 1.0))
    prev = w.kinetic_energy()
    for _ in range(int(20 / PHYSICS_DT)):
        w.step()
        now = w.kinetic_energy()
        assert now <= prev + 1e-9
        prev = now
        if w.at_rest():
            break


def test_head_on_collision_swaps_velocity():
    w = lossless()
    w.place(0, 0.5, 0.6, vx=2.0)
    w.place(1, 1.0, 0.6)
    events = run_until_stop_after_hit(w)
    hits = [e for e in events if isinstance(e, BallHitBall)]
    assert len(hits) == 1 and hits[0].speed == pytest.approx(2.0, abs=1e-6)
    assert w.balls[0].vx == pytest.approx(0.0, abs=1e-6)
    assert w.balls[1].vx == pytest.approx(2.0, abs=1e-6)


def run_until_stop_after_hit(w: World) -> list:
    events = []
    for _ in range(int(0.5 / PHYSICS_DT)):  # 0.5 s: enough to hit, not enough to reach the wall
        events += w.step()
    return events


def test_cushion_bounce_loses_energy_by_restitution():
    feel = replace(FEEL_SETS["VUA"], roll_decel=0.0)
    w = World(rack=False, feel=feel)
    w.place(0, 0.3, 0.6, vx=-1.0)
    events = []
    for _ in range(int(0.5 / PHYSICS_DT)):
        events += w.step()
    hits = [e for e in events if isinstance(e, BallHitCushion)]
    assert len(hits) == 1 and hits[0].speed == pytest.approx(1.0, abs=1e-6)
    assert w.balls[0].vx == pytest.approx(feel.cushion_e, abs=1e-6)


def test_deterministic_same_seed_same_shot():
    def final_state(seed):
        w = World(seed=seed)
        w.apply(Shot(0.01, 0.9))
        run_until_rest(w)
        return [(b.x, b.y, b.in_play) for b in w.balls]

    assert final_state(3) == final_state(3)


@pytest.mark.parametrize("angle", [0.0, math.pi, math.pi / 2, -math.pi / 2, 0.7, 2.2, -2.2])
def test_no_tunnelling_at_full_power(angle):
    w = World()
    w.apply(Shot(angle, 1.0))

    def inside(world):
        for b in world.in_play():
            assert BALL_R - 1e-6 <= b.x <= TABLE_L - BALL_R + 1e-6
            assert BALL_R - 1e-6 <= b.y <= TABLE_W - BALL_R + 1e-6

    run_until_rest(w, on_step=inside)


def test_a_ball_rolling_into_a_pocket_drops_and_stays_out():
    w = World(rack=False)
    cx, cy, _ = POCKETS[0]
    w.place(3, 0.3, 0.3, vx=-0.6, vy=-0.6)
    events = run_until_rest(w)
    drops = [e for e in events if isinstance(e, BallPocketed)]
    assert [(e.ball, e.pocket) for e in drops] == [(3, 0)]
    assert not w.balls[3].in_play and w.balls[3].pocket == 0
    assert w.at_rest() and (cx, cy) == (0.0, 0.0)


def test_side_pocket_catches_a_ball():
    w = World(rack=False)
    w.place(5, TABLE_L / 2, 0.5, vy=-1.5)
    events = run_until_rest(w)
    assert any(isinstance(e, BallPocketed) and e.ball == 5 and e.pocket == 4 for e in events)


def test_a_stopped_world_stays_stopped():
    w = World()
    for _ in range(100):
        assert w.step() == []
    assert w.at_rest()


# --- AC5: cue respawn -----------------------------------------------------------------------
def test_respawn_cue_goes_to_head_spot_when_free():
    w = World()
    w.balls[0].in_play = False
    assert w.respawn_cue() == HEAD_SPOT


def test_respawn_cue_skips_an_occupied_head_spot():
    w = World(rack=False)
    w.place(1, *HEAD_SPOT)
    x, y = w.respawn_cue()
    assert math.hypot(x - HEAD_SPOT[0], y - HEAD_SPOT[1]) > 0
    assert math.hypot(x - w.balls[1].x, y - w.balls[1].y) >= D


# --- Shot -------------------------------------------------------------------------------------
def test_apply_sets_cue_velocity_from_power_and_angle():
    w = World()
    w.apply(Shot(math.pi / 2, 0.5))
    assert w.balls[0].vx == pytest.approx(0.0, abs=1e-12)
    assert w.balls[0].vy == pytest.approx(w.feel.v_max * 0.5)


def test_apply_refuses_when_cue_ball_is_pocketed():
    w = World()
    w.balls[0].in_play = False
    with pytest.raises(ValueError):
        w.apply(Shot(0.0, 0.5))


@pytest.mark.parametrize("power,spin", [(-0.1, 0), (1.1, 0), (0.5, 1.5), (0.5, -1.5)])
def test_shot_validates_ranges(power, spin):
    with pytest.raises(ValueError):
        Shot(0.0, power, spin)
