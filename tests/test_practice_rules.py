"""Luyện tập "Thử Ma" (docs/plans/20261102-luyen-tap.md AC1-AC6). Events are scripted."""

from game.physics.world import BallHitBall, BallHitCushion, BallPocketed
from game.rules.eight_ball import (
    FOUL_NO_CUSHION,
    FOUL_NO_HIT,
    FOUL_SCRATCH,
    FOUL_WRONG_BALL,
    LOST,
    PLAYING,
    WON,
)
from game.rules.practice import LOST_TIMEOUT, GhostRun


def hit(ball: int, speed: float = 1.0) -> BallHitBall:
    return BallHitBall(0, ball, speed)


def cushion(ball: int = 0) -> BallHitCushion:
    return BallHitCushion(ball, 1.0)


def down(ball: int) -> BallPocketed:
    return BallPocketed(ball, 0)


def shoot(run: GhostRun, *events):
    run.on_shot()
    run.on_events(events)
    return run.finish_shot()


# --- AC1: the target is always the lowest ball left -------------------------------------------
def test_target_is_the_lowest_ball_left():
    run = GhostRun()
    assert run.target == 1
    shoot(run, hit(1), down(1))
    assert run.target == 2
    shoot(run, hit(2), down(2), down(5))  # a carom took the 5 along too
    assert run.target == 3


# --- AC2: a legal shot keeps the run going ------------------------------------------------------
def test_a_legal_shot_keeps_the_run_going():
    run = GhostRun()
    res = shoot(run, hit(1), down(1))
    assert res.outcome is None and not res.fouls and res.pocketed == (1,)
    assert (run.streak, run.shots, run.phase) == (1, 1, PLAYING)


def test_potting_extra_balls_in_one_shot_all_count():
    run = GhostRun()
    res = shoot(run, hit(1), down(1), down(7))
    assert not res.fouls and set(res.pocketed) == {1, 7}
    assert run.streak == 2 and run.target == 2  # 1 and 7 gone: the lowest left is 2


def test_a_legal_shot_that_only_reaches_a_cushion_is_not_a_foul():
    run = GhostRun()
    res = shoot(run, hit(1), cushion(3))
    assert not res.fouls and res.outcome is None
    assert run.target == 1  # nothing potted: still the same target


# --- AC3: every foul ends the run at once, no ball in hand --------------------------------------
def test_each_foul_ends_the_run_at_once():
    cases = {
        # a cushion too, so only the scratch trips (otherwise FOUL_NO_CUSHION would as well)
        FOUL_SCRATCH: (hit(1), down(0), cushion(3)),
        FOUL_NO_HIT: (),
        FOUL_WRONG_BALL: (hit(3),),
        FOUL_NO_CUSHION: (hit(1),),
    }
    for reason, events in cases.items():
        run = GhostRun()
        res = shoot(run, *events)
        assert res.fouls[0] == reason, reason
        assert res.outcome == LOST and res.reason == reason
        assert run.phase == LOST


def test_a_mid_run_foul_keeps_the_streak_already_made():
    run = GhostRun()
    shoot(run, hit(1), down(1))
    shoot(run, hit(2), down(2))
    res = shoot(run, hit(5))  # ball 3 is the target now: touching 5 first is a foul
    assert res.fouls == (FOUL_WRONG_BALL,) and res.outcome == LOST
    assert run.streak == 2  # the two balls already pocketed are not undone


# --- AC4: the shot's clock reaching zero ends the run the same way -----------------------------
def test_timeout_ends_the_run():
    run = GhostRun()
    res = run.timeout()
    assert res.outcome == LOST and res.reason == LOST_TIMEOUT
    assert run.phase == LOST


def test_timeout_after_a_partial_run_keeps_the_streak():
    run = GhostRun()
    shoot(run, hit(1), down(1))
    run.timeout()
    assert run.phase == LOST and run.streak == 1


# --- AC5: clearing the whole rack wins -----------------------------------------------------------
def test_clearing_all_15_wins():
    run = GhostRun()
    for n in range(1, 15):
        res = shoot(run, hit(n), down(n))
        assert res.outcome is None
    res = shoot(run, hit(15), down(15))
    assert res.outcome == WON and run.phase == WON
    assert run.streak == 15 and run.target is None


# --- AC6: reset gives a clean run ----------------------------------------------------------------
def test_reset_gives_a_fresh_run():
    run = GhostRun()
    shoot(run, hit(1), down(1))
    shoot(run, hit(5))  # a foul: the run is over
    run.reset()
    assert (run.shots, run.streak, run.balls_left, run.phase) == (0, 0, 15, PLAYING)
    assert run.target == 1 and run.last is None


def test_counts_shots_and_balls_left():
    run = GhostRun()
    assert (run.shots, run.balls_left) == (0, 15)
    shoot(run, hit(1), down(1), cushion(3))
    assert (run.shots, run.balls_left) == (1, 14)


def test_finish_shot_without_on_shot_does_nothing():
    run = GhostRun()
    res = run.finish_shot()
    assert res.outcome is None and not res.fouls and not res.pocketed
    assert run.phase == PLAYING
