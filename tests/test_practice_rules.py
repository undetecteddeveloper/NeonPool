"""Practice "the Ghost" (docs/plans/20261102-luyen-tap.md AC1-AC6, reworked in round 4 /
GAME_DESIGN lần 33). Events are scripted."""

import random

from game.config import PRACTICE_LIVES
from game.physics.world import BallHitBall, BallPocketed
from game.rules.eight_ball import FOUL_SCRATCH, LOST, PLAYING, WON
from game.rules.practice import LOST_TIMEOUT, MISS, GhostRun


def hit(ball: int, speed: float = 1.0) -> BallHitBall:
    return BallHitBall(0, ball, speed)


def down(ball: int) -> BallPocketed:
    return BallPocketed(ball, 0)


def shoot(run: GhostRun, *events):
    run.on_shot()
    run.on_events(events)
    return run.finish_shot()


def run_with_target(target: int, seed: int = 1) -> GhostRun:
    run = GhostRun(random.Random(seed))
    run.target = target
    return run


# --- AC1: the target is random and always a ball still on the table ----------------------------
def test_ac1_the_target_is_a_random_ball_still_on_the_table():
    firsts = {GhostRun(random.Random(seed)).target for seed in range(60)}
    assert len(firsts) > 8 and firsts <= set(range(1, 16))  # not always the 1


def test_ac1_the_same_seed_gives_the_same_targets():
    def targets(seed):
        run, seen = GhostRun(random.Random(seed)), []
        for _ in range(6):
            seen.append(run.target)
            shoot(run, down(run.target))
        return seen

    assert targets(7) == targets(7) and targets(7) != targets(8)


def test_ac1_after_a_pot_the_next_target_is_never_a_ball_already_down():
    run = GhostRun(random.Random(3))
    while run.phase == PLAYING:
        shoot(run, down(run.target))
        assert run.target is None or run.target not in run.pocketed


# --- AC2: the target in a pocket is a success, whatever the cue ball touched ------------------
def test_ac2_potting_the_target_counts_and_picks_the_next_one():
    run = run_with_target(9)
    res = shoot(run, down(9))
    assert res.hit and res.lost_life is None and res.pocketed == (9,)
    assert (run.streak, run.lives, run.shots) == (1, PRACTICE_LIVES, 1)
    assert run.target != 9 and run.target in range(1, 16)


def test_ac2_what_the_cue_ball_touches_first_does_not_matter():
    run = run_with_target(12)
    res = shoot(run, hit(3), hit(12), down(12))  # blocked by the 3, banked in anyhow
    assert res.hit and run.lives == PRACTICE_LIVES


def test_ac2_other_balls_going_down_do_not_count_as_the_target_and_do_not_cost_a_life():
    run = run_with_target(9)
    res = shoot(run, down(9), down(4))
    assert res.hit and run.streak == 1 and run.pocketed == {9, 4}
    assert run.target not in (9, 4)


# --- AC3: a shot that does not pot the target costs a life, the target stays ------------------
def test_ac3_a_miss_costs_a_life_and_keeps_the_target():
    run = run_with_target(9)
    res = shoot(run, hit(9))  # touched it, it did not go down
    assert not res.hit and res.lost_life == MISS and run.lives == PRACTICE_LIVES - 1
    assert run.target == 9 and run.streak == 0 and run.phase == PLAYING


def test_ac3_another_ball_going_down_instead_of_the_target_is_a_miss():
    run = run_with_target(9)
    res = shoot(run, down(4))
    assert res.lost_life == MISS and run.target == 9 and run.pocketed == {4}


def test_ac3_a_shot_that_touches_nothing_is_just_a_miss_not_a_foul():
    run = run_with_target(9)
    assert shoot(run).lost_life == MISS


# --- AC4: the cue ball in a pocket costs a life and goes in hand ------------------------------
def test_ac4_the_cue_ball_in_a_pocket_costs_a_life_and_is_in_hand():
    run = run_with_target(9)
    res = shoot(run, down(0))
    assert res.lost_life == FOUL_SCRATCH and run.lives == PRACTICE_LIVES - 1
    assert run.cue_in_hand and run.target == 9
    run.cue_placed()
    assert not run.cue_in_hand


def test_ac4_the_target_going_down_with_the_cue_ball_is_not_a_success():
    run = run_with_target(9)
    res = shoot(run, down(9), down(0))
    assert not res.hit and res.lost_life == FOUL_SCRATCH and run.streak == 0
    assert 9 in run.pocketed and run.target != 9  # the ball is gone: a new target


def test_ac4_the_next_shot_ends_the_hand():
    run = run_with_target(9)
    shoot(run, down(0))
    run.on_shot()
    assert not run.cue_in_hand


# --- AC5: no lives left loses the run; no ball left wins it -----------------------------------
def test_ac5_the_last_life_lost_loses_the_run():
    run = run_with_target(9)
    for left in range(PRACTICE_LIVES - 1, 0, -1):
        assert shoot(run).outcome is None and run.lives == left
    res = shoot(run)
    assert res.outcome == LOST and run.phase == LOST and run.lives == 0
    assert res.lost_life == MISS and not run.cue_in_hand


def test_ac5_the_streak_made_stays_when_the_run_is_lost():
    run = run_with_target(5)
    shoot(run, down(5))
    shoot(run)
    shoot(run)
    shoot(run)
    assert run.phase == LOST and run.streak == 1


def test_ac5_a_timeout_costs_a_life_too():
    run = run_with_target(9)
    res = run.timeout()
    assert res.lost_life == LOST_TIMEOUT and run.lives == PRACTICE_LIVES - 1
    assert run.phase == PLAYING and run.target == 9
    for _ in range(PRACTICE_LIVES - 1):
        res = run.timeout()
    assert res.outcome == LOST and run.phase == LOST


def test_ac5_clearing_the_table_wins_whatever_the_order():
    run = GhostRun(random.Random(2))
    shots = 0
    while run.phase == PLAYING:
        shoot(run, down(run.target))
        shots += 1
    assert run.phase == WON and run.pocketed == set(range(1, 16)) and run.streak == 15
    assert run.target is None and shots == 15


def test_ac5_a_win_needs_no_target_pot_when_other_balls_clear_the_table():
    run = run_with_target(1)
    run.pocketed = set(range(2, 15))  # 1 and 15 are left; 1 is the target
    res = shoot(run, down(1), down(15))
    assert res.outcome == WON and run.streak == 1


# --- AC6: reset gives a clean run -------------------------------------------------------------
def test_ac6_reset_gives_a_fresh_run():
    run = run_with_target(9)
    shoot(run, down(9))
    shoot(run, down(0))
    run.reset()
    assert (run.shots, run.streak, run.balls_left, run.phase) == (0, 0, 15, PLAYING)
    assert run.lives == PRACTICE_LIVES and not run.cue_in_hand and run.last is None
    assert run.target in range(1, 16)


def test_ac6_finish_shot_without_on_shot_does_nothing():
    run = GhostRun(random.Random(0))
    res = run.finish_shot()
    assert not res.hit and res.lost_life is None and res.outcome is None
    assert run.lives == PRACTICE_LIVES
