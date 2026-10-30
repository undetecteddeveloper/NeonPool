"""Two-player 8-ball (AC4 turn state, AC5 rules). Events are scripted, as in test_eight_ball."""

from game.physics.world import BallHitBall, BallHitCushion, BallPocketed
from game.rules.eight_ball import (
    FOUL_SCRATCH,
    FOUL_WRONG_BALL,
    LOST,
    LOST_EARLY,
    RERACK,
    SOLID,
    STRIPE,
    WON,
)
from game.rules.two_player import Match


def hit(ball: int, speed: float = 1.0) -> BallHitBall:
    return BallHitBall(0, ball, speed)


def cushion(ball: int = 0) -> BallHitCushion:
    return BallHitCushion(ball, 1.0)


def down(ball: int) -> BallPocketed:
    return BallPocketed(ball, 0)


def shoot(m: Match, *events):
    m.on_shot()
    m.on_events(events)
    return m.finish_shot()


def after_break(breaker: int = 0) -> Match:
    """A table broken by `breaker` without any ball going down: the other player is on turn."""
    m = Match(breaker)
    shoot(m, hit(1), cushion(3))
    return m


def with_groups(solid_player: int, gone: tuple[int, ...] = ()) -> Match:
    """Groups already chosen; player 0 on turn; `gone` balls are already down."""
    m = after_break(1)  # player 1 breaks, player 0 is on turn
    m.groups = [None, None]
    m.groups[solid_player] = SOLID
    m.groups[1 - solid_player] = STRIPE
    m.pocketed.update(gone)
    m._judge.is_break = False
    return m


# --- AC5: turns ------------------------------------------------------------------------------
def test_ac5_the_breaker_shoots_first_and_a_miss_passes_the_turn():
    m = Match(breaker=1)
    assert m.turn == 1 and m.is_break
    shoot(m, hit(1), cushion(3))
    assert m.turn == 0 and not m.over


def test_ac5_a_ball_down_on_the_open_table_keeps_the_turn_but_picks_no_group():
    m = Match()
    res = shoot(m, hit(1), down(9), cushion(3))  # the break
    assert m.turn == 0 and m.groups == [None, None] and res.group is None


def test_ac5_the_first_legal_pocket_gives_the_opposite_group_to_the_other_player():
    m = after_break()  # player 1 on turn
    res = shoot(m, hit(2), down(11), cushion(3))
    assert m.groups == [SOLID, STRIPE] and res.group == STRIPE and res.shooter == 1
    assert m.turn == 1  # a legal ball down: shoot again


def test_ac5_a_solid_for_the_second_player_gives_solids_to_them_and_stripes_to_the_first():
    m = after_break()
    shoot(m, hit(2), down(4), cushion(3))
    assert m.groups == [STRIPE, SOLID]


def test_ac5_a_miss_after_the_groups_are_chosen_passes_the_turn():
    m = with_groups(solid_player=0)
    shoot(m, hit(2), cushion(3))
    assert m.turn == 1 and not m.cue_in_hand


def test_ac5_only_the_opponents_ball_down_passes_the_turn_and_is_not_a_foul():
    m = with_groups(solid_player=0)
    res = shoot(m, hit(2), down(10), cushion(3))  # hit own ball first, sink a stripe
    assert res.fouls == () and m.turn == 1 and 10 in m.pocketed and not m.cue_in_hand


def test_ac5_own_and_opponents_ball_down_in_one_shot_keeps_the_turn():
    m = with_groups(solid_player=0)
    shoot(m, hit(2), down(10), down(3), cushion(3))
    assert m.turn == 0


# --- AC5: fouls ------------------------------------------------------------------------------
def test_ac5_a_foul_passes_the_turn_and_gives_the_opponent_the_cue_ball_in_hand():
    m = with_groups(solid_player=0)
    res = shoot(m, hit(2), down(0))  # the cue ball went in
    assert res.fouls[0] == FOUL_SCRATCH
    assert m.turn == 1 and m.cue_in_hand and m.fouls == [1, 0]
    m.cue_placed()
    assert not m.cue_in_hand


def test_ac5_a_foul_keeps_the_balls_that_went_down_but_loses_the_turn():
    m = with_groups(solid_player=0)
    shoot(m, hit(10), down(3), cushion(3))  # hit a stripe first: wrong ball
    assert m.turn == 1 and m.cue_in_hand and 3 in m.pocketed


def test_ac5_the_next_shot_ends_the_cue_in_hand_of_the_player_on_turn():
    m = with_groups(solid_player=0)
    shoot(m, hit(2), down(0))
    shoot(m, hit(10), cushion(3))  # player 1 shoots (their group is stripes)
    assert not m.cue_in_hand


def test_ac5_a_foul_on_the_first_shot_after_the_break_picks_no_group():
    m = after_break()
    shoot(m, hit(2), down(5), down(0))
    assert m.groups == [None, None] and m.turn == 0 and m.cue_in_hand


def test_ac5_wrong_first_ball_is_the_foul_it_is_in_solo_play():
    m = with_groups(solid_player=0)
    res = shoot(m, hit(12), cushion(3))
    assert FOUL_WRONG_BALL in res.fouls


# --- AC5: the 8 ------------------------------------------------------------------------------
def test_ac5_the_8_in_after_clearing_the_group_wins_for_that_player():
    m = with_groups(solid_player=0, gone=tuple(range(1, 8)))
    res = shoot(m, hit(8), down(8), cushion(3))
    assert m.over and m.winner == 0 and res.outcome == WON


def test_ac5_the_8_in_too_early_loses_for_that_player_and_wins_for_the_other():
    m = with_groups(solid_player=0, gone=(1, 2))
    res = shoot(m, hit(3), down(8), cushion(3))
    assert m.over and m.winner == 1 and res.outcome == LOST and res.reason == LOST_EARLY


def test_ac5_the_8_in_with_a_foul_loses_even_when_the_group_is_cleared():
    m = with_groups(solid_player=0, gone=tuple(range(1, 8)))
    shoot(m, hit(8), down(8), down(0))
    assert m.over and m.winner == 1


def test_ac5_the_second_player_wins_the_same_way():
    m = with_groups(solid_player=1, gone=tuple(range(1, 8)))  # player 1's solids are all down
    m.turn = 1
    res = shoot(m, hit(8), down(8), cushion(3))
    assert m.winner == 1 and res.outcome == WON


def test_ac5_the_8_on_the_break_racks_again_and_the_same_player_breaks():
    m = Match(breaker=1)
    res = shoot(m, hit(1), down(8), cushion(3))
    assert res.outcome == RERACK and not m.over and m.turn == 1
    m.rerack()
    assert m.is_break and not m.pocketed and m.groups == [None, None] and not m.cue_in_hand


# --- AC4: the clock (the frame is here; the 60 s clock itself is a later stage) ---------------
def test_ac4_timeout_passes_the_turn():
    m = after_break()
    assert m.turn == 1
    res = m.timeout()
    assert m.turn == 0 and res.timed_out and res.shooter == 1
    assert not m.cue_in_hand and m.fouls == [0, 0]


# --- the referee's word travels as a MatchState ---------------------------------------------
def test_a_copy_that_loads_the_snapshot_agrees_with_the_referee():
    ref = with_groups(solid_player=0)
    shoot(ref, hit(2), down(10), down(0))
    copy = Match()
    copy.load(ref.snapshot())
    assert copy.snapshot() == ref.snapshot()
    assert copy.turn == ref.turn and copy.cue_in_hand and copy.groups == ref.groups


def test_group_left_and_eight_next_per_player():
    m = with_groups(solid_player=0, gone=tuple(range(1, 8)))
    assert m.group_left(0) == 0 and m.eight_is_next(0)
    assert m.group_left(1) == 7 and not m.eight_is_next(1)
    assert Match().group_left(0) is None
