"""Practice "the Ghost" (docs/plans/20261102-luyen-tap.md AC1-AC6, reworked in round 4 /
GAME_DESIGN lần 33). Events are scripted."""

import random

from game.config import PRACTICE_LIVES
from game.physics.world import CUE, Ball, BallHitBall, BallPocketed
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


def break_shot(run: GhostRun) -> GhostRun:
    """Resolve the opening break (no target yet, round 38) so a real one gets picked."""
    run.on_shot()
    run.finish_shot()
    return run


# --- AC1: the target is random and always a ball still on the table ----------------------------
def test_ac1_the_target_is_a_random_ball_still_on_the_table():
    firsts = {break_shot(GhostRun(random.Random(seed))).target for seed in range(60)}
    assert len(firsts) > 8 and firsts <= set(range(1, 16))  # not always the 1


def test_ac1_the_same_seed_gives_the_same_targets():
    def targets(seed):
        run, seen = break_shot(GhostRun(random.Random(seed))), []
        for _ in range(6):
            seen.append(run.target)
            shoot(run, down(run.target))
        return seen

    assert targets(7) == targets(7) and targets(7) != targets(8)


def test_ac1_after_a_pot_the_next_target_is_never_a_ball_already_down():
    run = break_shot(GhostRun(random.Random(3)))
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
    run = break_shot(GhostRun(random.Random(2)))
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
    assert run.target is None  # no target until the break settles (AC25)


def test_ac6_finish_shot_without_on_shot_does_nothing():
    run = GhostRun(random.Random(0))
    res = run.finish_shot()
    assert not res.hit and res.lost_life is None and res.outcome is None
    assert run.lives == PRACTICE_LIVES


# --- AC24 (lần 37): the target is only ever a ball the cue ball can draw a straight line to ----
# Table is 2.54 x 1.27 m (config.TABLE_L / TABLE_W); every position below stays well inside it.
CUE_XY = (0.3, 0.3)
NEAR_XY = (0.6, 0.3)  # straight ahead of the cue: open, and blocks whatever sits behind it
FAR_XY = (0.9, 0.3)  # directly behind NEAR_XY, same line: blocked
SIDE_XY = (0.3, 0.9)  # a different line, nothing in the way: open


def test_ac24_the_next_target_after_a_pot_skips_a_ball_the_cue_cannot_see():
    cue = Ball(CUE, *CUE_XY, in_play=True)
    b5 = Ball(5, 1.5, 1.0, in_play=False)  # just potted, off the blocking line
    b8 = Ball(8, *NEAR_XY, in_play=True)  # sits between the cue and the 6
    b6 = Ball(6, *FAR_XY, in_play=True)  # directly behind the 8: not reachable
    b7 = Ball(7, *SIDE_XY, in_play=True)  # a clear line: reachable
    balls = [cue, b5, b6, b7, b8]
    seen = set()
    for seed in range(40):
        run = GhostRun(random.Random(seed))
        run.pocketed = set(range(1, 16)) - {5, 6, 7, 8}
        run.target = 5
        run.on_shot()
        run.on_events([down(5)])
        run.finish_shot(balls)
        seen.add(run.target)
    assert 6 not in seen and seen == {7, 8}  # the 6 is never picked: the 8 blocks it


def test_ac24_a_miss_that_leaves_the_target_blocked_swaps_it_for_an_open_one():
    cue = Ball(CUE, *CUE_XY, in_play=True)
    b8 = Ball(8, *NEAR_XY, in_play=True)  # ended up between the cue and the 6 after the miss
    b6 = Ball(6, *FAR_XY, in_play=True)  # the target: now blocked by the 8
    b7 = Ball(7, *SIDE_XY, in_play=True)  # open
    balls = [cue, b6, b7, b8]
    run = GhostRun(random.Random(0))
    run.pocketed = set(range(1, 16)) - {6, 7, 8}
    run.target = 6
    run.on_shot()
    res = run.finish_shot(balls)  # missed: the 6 stayed on the table, now blocked
    assert res.lost_life == MISS and run.lives == PRACTICE_LIVES - 1
    assert run.target_swapped and run.target in {7, 8}  # swapped away from the blocked 6


def test_ac24_a_miss_that_leaves_the_target_open_does_not_swap_it():
    cue = Ball(CUE, *CUE_XY, in_play=True)
    b7 = Ball(7, *SIDE_XY, in_play=True)
    balls = [cue, b7]
    run = GhostRun(random.Random(0))
    run.pocketed = set(range(1, 16)) - {7}
    run.target = 7
    run.target_swapped = True  # a swap from an earlier shot must not leak into this one
    run.on_shot()
    run.finish_shot(balls)  # a miss, but the 7 is still open: no swap needed
    assert not run.target_swapped and run.target == 7


def test_ac24_with_no_cue_ball_in_the_list_the_pick_still_falls_back_to_any_ball():
    b6 = Ball(6, *FAR_XY, in_play=True)
    b9 = Ball(9, *SIDE_XY, in_play=True)
    balls = [b6, b9]  # no cue ball: every "open" check fails, nothing to fall back from
    run = GhostRun(random.Random(0))
    run.pocketed = set(range(1, 16)) - {6, 9}
    run.target = 6
    run.on_shot()
    res = run.finish_shot(balls)
    assert res.lost_life == MISS
    assert run.target in {6, 9}  # still a valid target, not None and not crashed


def test_ac24_a_timeout_also_swaps_a_target_the_balls_now_block():
    cue = Ball(CUE, *CUE_XY, in_play=True)
    b8 = Ball(8, *NEAR_XY, in_play=True)
    b6 = Ball(6, *FAR_XY, in_play=True)
    b7 = Ball(7, *SIDE_XY, in_play=True)
    balls = [cue, b6, b7, b8]
    run = GhostRun(random.Random(0))
    run.pocketed = set(range(1, 16)) - {6, 7, 8}
    run.target = 6
    res = run.timeout(balls)
    assert res.lost_life == LOST_TIMEOUT
    assert run.target_swapped and run.target in {7, 8}


# --- AC25 (lần 38): the opening break calls no target, so there is nothing to miss on it -------
def test_ac25_a_fresh_run_has_no_target_until_the_break_settles():
    run = GhostRun(random.Random(0))
    assert run.target is None and run.phase == PLAYING


def test_ac25_the_break_costs_no_life_and_picks_the_first_real_target():
    run = GhostRun(random.Random(0))
    run.on_shot()
    res = run.finish_shot()  # the break: nothing was called, so nothing was missed
    assert res.lost_life is None and res.outcome is None and run.lives == PRACTICE_LIVES
    assert run.target in range(1, 16)


def test_ac25_the_break_picks_among_balls_the_cue_can_see_when_given_positions():
    cue = Ball(CUE, *CUE_XY, in_play=True)
    b8 = Ball(8, *NEAR_XY, in_play=True)
    b6 = Ball(6, *FAR_XY, in_play=True)  # directly behind the 8: not reachable
    b7 = Ball(7, *SIDE_XY, in_play=True)
    balls = [cue, b6, b7, b8]
    seen = set()
    for seed in range(40):
        run = GhostRun(random.Random(seed))
        run.pocketed = set(range(1, 16)) - {6, 7, 8}
        run.on_shot()
        run.finish_shot(balls)
        seen.add(run.target)
    assert 6 not in seen and seen == {7, 8}


def test_ac25_a_scratch_on_the_break_still_costs_a_life_and_still_picks_a_target():
    run = GhostRun(random.Random(0))
    res = shoot(run, down(0))  # the cue ball scratches on the break itself
    assert res.lost_life == FOUL_SCRATCH and run.lives == PRACTICE_LIVES - 1
    assert run.cue_in_hand and run.target in range(1, 16)


def test_ac25_a_timeout_before_the_break_costs_a_life_but_assigns_no_target():
    run = GhostRun(random.Random(0))
    res = run.timeout()  # the clock ran out before the break was even fired
    assert res.lost_life == LOST_TIMEOUT and run.lives == PRACTICE_LIVES - 1
    assert run.target is None and run.phase == PLAYING


def test_ac25_stalling_out_every_life_before_the_break_still_loses_the_run():
    run = GhostRun(random.Random(0))
    for _ in range(PRACTICE_LIVES - 1):
        assert run.timeout().outcome is None
    res = run.timeout()
    assert res.outcome == LOST and run.phase == LOST and run.target is None
