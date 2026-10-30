"""8-ball rules for solo practice (docs/plans/20261028-8ball.md AC1-AC4). Events are scripted."""

from game.physics.world import BallHitBall, BallHitCushion, BallPocketed, World
from game.rules.eight_ball import (
    FOUL_NO_CUSHION,
    FOUL_NO_HIT,
    FOUL_SCRATCH,
    FOUL_WRONG_BALL,
    LOST,
    LOST_EARLY,
    LOST_FOUL,
    PLAYING,
    RERACK,
    SOLID,
    STRIPE,
    WON,
    EightBall,
)


def hit(ball: int, speed: float = 1.0) -> BallHitBall:
    return BallHitBall(0, ball, speed)


def cushion(ball: int = 0) -> BallHitCushion:
    return BallHitCushion(ball, 1.0)


def down(ball: int) -> BallPocketed:
    return BallPocketed(ball, 0)


def shoot(rb: EightBall, *events):
    rb.on_shot()
    rb.on_events(events)
    return rb.finish_shot()


def after_break(rb: EightBall | None = None) -> EightBall:
    """A table that has been broken without any ball going down."""
    rb = rb or EightBall()
    shoot(rb, hit(1), cushion(3))
    return rb


def with_group(group: str, gone: tuple[int, ...] = ()) -> EightBall:
    rb = after_break()
    rb.group = group
    rb.pocketed = set(gone)
    return rb


# --- counting ----------------------------------------------------------------------------
def test_counts_shots_and_balls_left():
    rb = EightBall()
    assert (rb.shots, rb.balls_left, rb.fouls) == (0, 15, 0)
    shoot(rb, hit(1), down(5), cushion(3))
    assert (rb.shots, rb.balls_left) == (1, 14)


def test_reset_gives_a_fresh_game():
    rb = with_group(SOLID, (1, 2))
    shoot(rb, hit(3), down(0))  # a foul
    rb.reset()
    assert (rb.shots, rb.fouls, rb.balls_left, rb.group, rb.phase) == (0, 0, 15, None, PLAYING)
    assert rb.is_break and not rb.cue_in_hand


# --- AC1: the group is decided by the first legal pocketed ball after the break ----------------
def test_the_table_stays_open_after_the_break_even_if_a_ball_goes_down():
    rb = EightBall()
    res = shoot(rb, hit(1), down(9), cushion(3))
    assert rb.group is None and res.group is None and res.fouls == ()


def test_first_legal_pocket_after_the_break_picks_the_group():
    rb = after_break()
    res = shoot(rb, hit(2), down(11), cushion(3))
    assert rb.group == STRIPE and res.group == STRIPE


def test_a_solid_pocket_picks_solids_and_the_first_ball_down_counts():
    rb = after_break()
    shoot(rb, hit(2), down(4), down(12))
    assert rb.group == SOLID


def test_a_foul_shot_does_not_pick_a_group_even_if_a_ball_goes_down():
    rb = after_break()
    shoot(rb, hit(2), down(0), down(5))  # the cue ball went in too
    assert rb.group is None


def test_nothing_changes_the_group_once_it_is_chosen():
    rb = with_group(SOLID)
    shoot(rb, hit(2), down(10), cushion(3))
    assert rb.group == SOLID


def test_group_left_counts_the_players_balls_only():
    rb = with_group(STRIPE, (9, 10, 1))
    assert rb.group_left() == 5
    assert EightBall().group_left() is None


def test_the_eight_is_next_once_the_group_is_cleared():
    rb = with_group(SOLID, tuple(range(1, 8)))
    assert rb.group_left() == 0 and rb.eight_is_next()
    assert not with_group(SOLID, (1,)).eight_is_next()


# --- AC2: fouls --------------------------------------------------------------------------------
def test_a_clean_shot_is_not_a_foul():
    rb = with_group(SOLID)
    res = shoot(rb, hit(3), cushion(3))
    assert res.fouls == () and rb.fouls == 0 and not rb.cue_in_hand


def test_cue_ball_pocketed_is_a_foul():
    rb = with_group(SOLID)
    res = shoot(rb, hit(3), down(0), cushion(3))
    assert res.fouls[0] == FOUL_SCRATCH and rb.fouls == 1


def test_cue_ball_touching_nothing_is_a_foul():
    rb = with_group(SOLID)
    res = shoot(rb, cushion(0))
    assert res.fouls == (FOUL_NO_HIT,)


def test_first_touching_the_other_group_is_a_foul():
    rb = with_group(SOLID)
    res = shoot(rb, hit(9), cushion(3))
    assert res.fouls == (FOUL_WRONG_BALL,)


def test_first_touching_the_eight_too_early_is_a_foul():
    rb = with_group(SOLID, (1, 2))
    assert shoot(rb, hit(8), cushion(8)).fouls == (FOUL_WRONG_BALL,)


def test_on_an_open_table_touching_the_eight_first_is_a_foul():
    rb = after_break()
    assert shoot(rb, hit(8), cushion(8)).fouls == (FOUL_WRONG_BALL,)


def test_touching_the_eight_first_is_fine_once_the_group_is_cleared():
    rb = with_group(SOLID, tuple(range(1, 8)))
    assert shoot(rb, hit(8), cushion(8)).fouls == ()


def test_after_contact_something_must_reach_a_cushion_or_a_pocket():
    rb = with_group(SOLID)
    assert shoot(rb, hit(3)).fouls == (FOUL_NO_CUSHION,)
    assert shoot(rb, hit(3), cushion(3)).fouls == ()  # a ball reached a cushion
    assert shoot(rb, hit(3), down(3)).fouls == ()  # a ball was pocketed


def test_a_cushion_touched_before_the_first_contact_does_not_count():
    rb = with_group(SOLID)
    res = shoot(rb, cushion(0), hit(3))
    assert res.fouls == (FOUL_NO_CUSHION,)


def test_a_gentle_touch_still_counts_as_contact():
    rb = with_group(SOLID)
    res = shoot(rb, hit(3, speed=0.002), cushion(3))
    assert res.fouls == ()


def test_many_reasons_cost_one_foul_point():
    rb = with_group(SOLID)
    res = shoot(rb, down(0))  # scratch AND no contact
    assert len(res.fouls) >= 2 and rb.fouls == 1


def test_a_foul_puts_the_cue_ball_in_hand_until_it_is_placed():
    rb = with_group(SOLID)
    shoot(rb, hit(9), cushion(3))
    assert rb.cue_in_hand
    rb.cue_placed()
    assert not rb.cue_in_hand
    shoot(rb, hit(2), cushion(2))  # a clean shot keeps it that way
    assert not rb.cue_in_hand


def test_taking_the_next_shot_ends_the_in_hand_state():
    rb = with_group(SOLID)
    shoot(rb, hit(9), cushion(3))
    rb.on_shot()
    assert not rb.cue_in_hand


# --- AC4: the 8 ball ---------------------------------------------------------------------------
def test_the_eight_after_the_group_is_cleared_wins():
    rb = with_group(SOLID, tuple(range(1, 8)))
    res = shoot(rb, hit(8), down(8))
    assert res.outcome == WON and rb.phase == WON and res.reason is None


def test_the_eight_while_group_balls_remain_loses():
    rb = with_group(SOLID, (1, 2))
    res = shoot(rb, hit(3), down(8))
    assert res.outcome == LOST and rb.phase == LOST and res.reason == LOST_EARLY


def test_the_eight_with_the_table_still_open_loses():
    rb = after_break()
    res = shoot(rb, hit(2), down(8), cushion(2))
    assert res.outcome == LOST and res.reason == LOST_EARLY


def test_the_eight_in_a_shot_with_a_foul_loses_even_if_the_group_is_cleared():
    rb = with_group(SOLID, tuple(range(1, 8)))
    res = shoot(rb, hit(8), down(8), down(0))
    assert res.outcome == LOST and res.reason == LOST_FOUL


def test_the_last_group_ball_and_the_eight_in_the_same_shot_loses():
    rb = with_group(SOLID, tuple(range(1, 7)))  # only the 7 is left
    res = shoot(rb, hit(7), down(7), down(8))
    assert res.outcome == LOST and res.reason == LOST_EARLY


def test_the_eight_on_the_break_racks_again_without_a_penalty():
    rb = EightBall()
    res = shoot(rb, hit(1), down(8), down(0))  # even with the cue ball: no penalty
    assert res.outcome == RERACK and res.fouls == () and rb.fouls == 0
    assert rb.phase == PLAYING and not rb.cue_in_hand
    rb.rerack()
    assert (rb.pocketed, rb.group, rb.is_break, rb.shots) == (set(), None, True, 1)


def test_a_finished_game_stays_finished():
    rb = with_group(SOLID, (1,))
    shoot(rb, hit(2), down(8))
    assert rb.phase == LOST
    assert rb.finish_shot().outcome is None  # nothing live: judging again does nothing


def test_finish_shot_needs_a_shot_in_progress():
    rb = EightBall()
    assert rb.finish_shot().fouls == () and rb.fouls == 0


# --- the physics side of "in hand" ---------------------------------------------------------------
def test_cue_ball_cannot_be_placed_on_another_ball_or_in_a_pocket_or_off_the_cloth():
    w = World()
    ball = w.balls[3]
    assert not w.can_place_cue(ball.x, ball.y)
    assert not w.can_place_cue(0.0, 0.0)  # the corner pocket
    assert not w.can_place_cue(-0.1, 0.5)  # off the cloth
    assert w.can_place_cue(0.6, 0.3)


def test_place_cue_moves_the_stopped_cue_ball():
    w = World()
    assert w.place_cue(0.6, 0.3)
    assert (w.balls[0].x, w.balls[0].y) == (0.6, 0.3) and w.balls[0].in_play
    x, y = w.balls[0].x, w.balls[0].y
    assert not w.place_cue(0.0, 0.0)  # refused: it stays put
    assert (w.balls[0].x, w.balls[0].y) == (x, y)


def test_a_pocketed_cue_ball_can_be_placed_again():
    w = World()
    w.balls[0].in_play = False
    assert w.place_cue(1.0, 0.4) and w.balls[0].in_play


# --- the score on the result card ---------------------------------------------------------
def won_game(shots: int, fouls: int) -> EightBall:
    rb = EightBall()
    rb.shots, rb.fouls, rb.phase = shots, fouls, WON
    rb.pocketed = set(range(1, 16))
    return rb


def test_a_win_scores_a_budget_minus_shots_and_fouls():
    assert won_game(22, 6).score == 1000 - 22 * 10 - 6 * 50 == 480
    assert won_game(5, 0).score > won_game(22, 6).score  # fewer shots and fouls: more points


def test_a_win_is_never_worth_less_than_the_floor():
    assert won_game(300, 40).score == 100


def test_a_loss_counts_only_the_balls_that_went_down_without_the_eight():
    rb = EightBall()
    rb.phase, rb.pocketed = LOST, {2, 5, 8, 11}  # the 8 went in early: it does not count
    assert rb.score == 3 * 50
    rb.pocketed = {8}
    assert rb.score == 0


def test_a_running_game_has_no_score_yet():
    rb = EightBall()
    rb.shots, rb.fouls = 22, 6
    assert rb.phase == PLAYING and rb.score == 0  # a running game has not won anything yet
