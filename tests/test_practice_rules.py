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


# --- AC24 (lần 37, lần 39): the target is only ever a ball that has a pot line ---------------
# Geometry has its own tests (test_pot_lines.py): here the rules get a table whose lines are told.
CUE_XY = (0.3, 0.3)
NEAR_XY = (0.6, 0.3)  # straight ahead of the cue: visible, and hides whatever sits behind it
FAR_XY = (0.9, 0.3)  # directly behind NEAR_XY, same line: not visible
SIDE_XY = (0.3, 0.9)  # a different line, nothing in the way: visible


def told(monkeypatch, lines: dict[int, int], in_hand: dict[int, int] | None = None) -> None:
    """Pot lines per ball from where the cue ball stands, and (if given) with it in hand."""

    def stub(balls, n, *, cue_in_hand=False, **_):
        return (in_hand if cue_in_hand and in_hand is not None else lines).get(n, 0)

    monkeypatch.setattr("game.rules.practice.pot_lines", stub)


def table() -> list[Ball]:
    return [
        Ball(CUE, *CUE_XY, in_play=True),
        Ball(8, *NEAR_XY, in_play=True),
        Ball(6, *FAR_XY, in_play=True),
        Ball(7, *SIDE_XY, in_play=True),
    ]


def three_left(run: GhostRun) -> GhostRun:
    run.pocketed = set(range(1, 16)) - {6, 7, 8}
    return run


def test_ac24_the_next_target_after_a_pot_is_never_a_ball_without_a_pot_line(monkeypatch):
    told(monkeypatch, {7: 2, 8: 1})  # the 6 has none
    seen = set()
    for seed in range(40):
        run = GhostRun(random.Random(seed))
        run.pocketed = set(range(1, 16)) - {5, 6, 7, 8}
        run.target = 5
        run.on_shot()
        run.on_events([down(5)])
        run.finish_shot(table())
        seen.add(run.target)
    assert seen == {7, 8}


def test_ac24_a_miss_that_leaves_the_target_without_a_line_swaps_it_for_one_with(monkeypatch):
    told(monkeypatch, {7: 1, 8: 1})
    run = three_left(GhostRun(random.Random(0)))
    run.target = 6
    run.on_shot()
    res = run.finish_shot(table())  # missed, and the 6 has lost every line
    assert res.lost_life == MISS and run.lives == PRACTICE_LIVES - 1
    assert run.target_swapped and run.target in {7, 8}


def test_ac24_a_miss_that_leaves_the_target_a_line_does_not_swap_it(monkeypatch):
    told(monkeypatch, {7: 1})
    run = three_left(GhostRun(random.Random(0)))
    run.target, run.target_swapped = 7, True  # a swap from an earlier shot must not leak
    run.on_shot()
    run.finish_shot(table())
    assert not run.target_swapped and run.target == 7


def test_ac24_a_timeout_also_swaps_a_target_that_lost_its_lines(monkeypatch):
    told(monkeypatch, {7: 1, 8: 1})
    run = three_left(GhostRun(random.Random(0)))
    run.target = 6
    res = run.timeout(table())
    assert res.lost_life == LOST_TIMEOUT
    assert run.target_swapped and run.target in {7, 8}


def test_ac24_with_no_line_for_any_ball_even_in_hand_a_visible_ball_is_picked(monkeypatch):
    told(monkeypatch, {})  # nothing can be potted from anywhere
    seen = set()
    for seed in range(40):
        run = three_left(GhostRun(random.Random(seed)))
        run.target = 6
        run.on_shot()
        run.finish_shot(table())
        seen.add(run.target)
        assert not run.hand_given  # no point giving the ball when it would not help
    assert seen == {7, 8}  # the 6 is hidden behind the 8: only the visible balls are left


def test_ac24_with_no_line_anywhere_a_target_that_is_still_in_the_pool_is_kept(monkeypatch):
    told(monkeypatch, {})
    run = three_left(GhostRun(random.Random(0)))
    run.target = 7  # visible
    run.on_shot()
    run.finish_shot(table())
    assert run.target == 7 and not run.target_swapped  # no flicker between equally bad balls


def test_ac24_without_positions_nothing_is_swapped_and_the_pick_is_plain_random():
    run = three_left(GhostRun(random.Random(0)))
    run.target = 6
    run.on_shot()
    run.finish_shot()  # no ball list: the old behaviour, a miss keeps its target
    assert run.target == 6 and not run.target_swapped and not run.hand_given


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


def test_ac25_the_break_picks_among_balls_with_a_pot_line_when_given_positions(monkeypatch):
    told(monkeypatch, {7: 1, 8: 3})
    seen = set()
    for seed in range(40):
        run = three_left(GhostRun(random.Random(seed)))
        run.on_shot()
        run.finish_shot(table())
        seen.add(run.target)
    assert seen == {7, 8}


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


# --- AC26 (lần 39): no ball can be potted from here -> the cue ball is given in hand ---------
def test_ac26_when_no_ball_has_a_line_the_cue_ball_is_given_in_hand_at_no_cost(monkeypatch):
    told(monkeypatch, {}, in_hand={7: 1})
    run = three_left(GhostRun(random.Random(0)))
    run.target = 6
    run.on_shot()
    res = run.finish_shot(table())
    assert res.lost_life == MISS and run.lives == PRACTICE_LIVES - 1  # only the miss costs
    assert run.hand_given and run.cue_in_hand
    assert run.target == 7 and run.target_swapped  # the 6 has no line even from a free spot


def test_ac26_the_held_target_is_kept_when_it_has_a_line_from_the_free_spot(monkeypatch):
    told(monkeypatch, {}, in_hand={6: 1, 7: 1})
    run = three_left(GhostRun(random.Random(0)))
    run.target = 6
    run.on_shot()
    run.finish_shot(table())
    assert run.hand_given and run.cue_in_hand and run.target == 6 and not run.target_swapped


def test_ac26_after_a_pot_with_no_line_left_the_next_target_comes_with_the_cue_in_hand(
    monkeypatch,
):
    told(monkeypatch, {}, in_hand={7: 1, 8: 1})
    run = GhostRun(random.Random(0))
    run.pocketed = set(range(1, 16)) - {5, 7, 8}
    run.target = 5
    run.on_shot()
    run.on_events([down(5)])
    res = run.finish_shot(table())
    assert res.hit and res.lost_life is None and run.lives == PRACTICE_LIVES  # nothing lost
    assert run.hand_given and run.cue_in_hand and run.target in {7, 8}


def test_ac26_the_break_can_give_the_cue_in_hand_too_and_costs_nothing(monkeypatch):
    told(monkeypatch, {}, in_hand={7: 1})
    run = three_left(GhostRun(random.Random(0)))
    run.on_shot()
    res = run.finish_shot(table())
    assert res.lost_life is None and run.lives == PRACTICE_LIVES
    assert run.hand_given and run.cue_in_hand and run.target == 7


def test_ac26_a_ball_already_in_hand_is_not_given_again(monkeypatch):
    told(monkeypatch, {7: 1})  # the same answer in hand or not
    run = three_left(GhostRun(random.Random(0)))
    run.target = 6
    run.on_shot()
    run.on_events([down(0)])  # a scratch: in hand already
    run.finish_shot(table())
    assert run.cue_in_hand and not run.hand_given and run.target == 7 and run.target_swapped


def test_ac26_nothing_is_given_while_some_ball_has_a_line(monkeypatch):
    told(monkeypatch, {7: 1}, in_hand={7: 1, 8: 1})
    run = three_left(GhostRun(random.Random(0)))
    run.target = 6
    run.on_shot()
    run.finish_shot(table())
    assert not run.hand_given and not run.cue_in_hand and run.target == 7


def test_ac26_a_timeout_can_give_the_cue_in_hand_and_the_flags_reset_on_the_next_judging(
    monkeypatch,
):
    told(monkeypatch, {}, in_hand={7: 1})
    run = three_left(GhostRun(random.Random(0)))
    run.target = 6
    res = run.timeout(table())
    assert res.lost_life == LOST_TIMEOUT and run.hand_given and run.cue_in_hand
    told(monkeypatch, {7: 1})
    run.cue_placed()
    run.on_shot()
    run.finish_shot(table())
    assert not run.hand_given and not run.target_swapped


def test_ac26_the_run_ending_gives_nothing_and_picks_nothing(monkeypatch):
    told(monkeypatch, {}, in_hand={7: 1})
    run = three_left(GhostRun(random.Random(0)))
    run.target, run.lives = 6, 1
    run.on_shot()
    res = run.finish_shot(table())
    assert res.outcome == LOST and not run.hand_given and not run.cue_in_hand
    assert run.target == 6


def test_ac26_the_ladder_tries_the_roomy_lines_before_the_squeezes_and_here_before_in_hand(
    monkeypatch,
):
    asked = []

    def stub(balls, n, *, cue_in_hand=False, margin=None, **_):
        asked.append((cue_in_hand, margin > 0.0))
        return 1 if n == 7 and not margin and cue_in_hand else 0  # only a squeeze, in hand

    monkeypatch.setattr("game.rules.practice.pot_lines", stub)
    run = three_left(GhostRun(random.Random(0)))
    run.target = 6
    run.on_shot()
    run.finish_shot(table())
    order = list(dict.fromkeys(asked))
    assert order == [(False, True), (True, True), (False, False), (True, False)]
    assert run.hand_given and run.cue_in_hand and run.target == 7


def test_ac26_a_squeeze_from_where_the_cue_ball_stands_needs_no_hand(monkeypatch):
    def stub(balls, n, *, cue_in_hand=False, margin=None, **_):
        return 1 if n == 7 and not margin and not cue_in_hand else 0

    monkeypatch.setattr("game.rules.practice.pot_lines", stub)
    run = three_left(GhostRun(random.Random(0)))
    run.target = 6
    run.on_shot()
    run.finish_shot(table())
    assert run.target == 7 and not run.hand_given and not run.cue_in_hand
