"""Pot lines (docs/plans/20261102-luyen-tap.md AC26): in how many ways could a ball be shot
straight into a pocket. Hand-built tables, table is 2.54 x 1.27 m, ball radius 0.0286 m."""

from game.config import BALL_R, POCKETS
from game.physics.pot_lines import pot_lines, pot_pockets
from game.physics.world import CUE, Ball


def table(*spots: tuple[int, float, float]) -> list[Ball]:
    return [Ball(n, x, y, in_play=True) for n, x, y in spots]


CUE_AT = (CUE, 1.0, 0.63)
TARGET = (6, 0.3, 0.3)  # near the corner at (0, 0), the cue ball far off to its right


def test_a_ball_in_the_open_has_a_line_to_a_pocket():
    assert pot_lines(table(CUE_AT, TARGET), 6) >= 1


def test_a_ball_blocking_the_way_to_the_pocket_takes_that_line_away():
    clear = pot_lines(table(CUE_AT, TARGET), 6)
    blocker = (9, 0.17, 0.17)  # between the 6 and the corner pocket, on its line
    assert pot_lines(table(CUE_AT, TARGET, blocker), 6) < clear


def test_a_ball_in_the_way_of_the_cue_ball_takes_that_line_away():
    clear = pot_lines(table(CUE_AT, TARGET), 6)
    ghost = (0.3 + 2 * BALL_R * 0.7, 0.3 + 2 * BALL_R * 0.7)  # about where the cue ball must hit
    mid = ((1.0 + ghost[0]) / 2, (0.63 + ghost[1]) / 2)
    assert pot_lines(table(CUE_AT, TARGET, (9, *mid)), 6) < clear


def test_a_ball_standing_right_in_front_of_the_cue_ball_blocks_the_lines_behind_it():
    blocked = pot_lines(table(CUE_AT, TARGET, (8, 0.9, 0.6)), 6)
    assert blocked < pot_lines(table(CUE_AT, TARGET), 6)


def test_thinner_cuts_are_only_allowed_when_the_limit_is_wide():
    balls = table(CUE_AT, TARGET)
    thin, normal, wide = (pot_lines(balls, 6, max_cut_deg=d) for d in (1.0, 75.0, 89.0))
    assert thin <= normal <= wide
    assert thin < wide


def test_with_the_cue_ball_in_hand_only_the_spot_behind_the_target_must_be_free():
    far = (CUE, 2.4, 1.2)  # on the far side of the table from the 6, with the 8 in the way
    balls = table(far, TARGET, (8, 1.4, 0.7))
    assert pot_lines(balls, 6, cue_in_hand=True) >= pot_lines(balls, 6)
    ghost_spot = (0.3 + 2 * BALL_R * 0.7, 0.3 + 2 * BALL_R * 0.7)
    covered = table(far, TARGET, (8, *ghost_spot))  # sitting where the cue ball would have to be
    assert pot_lines(covered, 6, cue_in_hand=True) < pot_lines(balls, 6, cue_in_hand=True)


def test_balls_off_the_table_block_nothing_and_a_ball_off_the_table_has_no_line():
    gone = Ball(9, 0.17, 0.17, in_play=False)
    assert pot_lines([*table(CUE_AT, TARGET), gone], 6) == pot_lines(table(CUE_AT, TARGET), 6)
    assert pot_lines([*table(CUE_AT), Ball(6, 0.3, 0.3, in_play=False)], 6) == 0


def test_there_are_at_most_as_many_lines_as_pockets_and_a_missing_cue_ball_means_none():
    assert 0 <= pot_lines(table(CUE_AT, TARGET), 6) <= len(POCKETS)
    assert pot_lines(table(TARGET), 6) == 0  # no cue ball and not in hand: nothing to shoot with
    assert pot_lines(table(TARGET), 6, cue_in_hand=True) >= 1


def test_a_ball_hugging_a_cushion_can_still_be_shot_along_it_into_the_corner():
    balls = table((CUE, 1.2, 0.5), (6, 0.5, BALL_R))
    assert pot_lines(balls, 6) >= 1


def test_the_count_does_not_depend_on_the_order_of_the_list():
    balls = table(CUE_AT, TARGET, (8, 0.9, 0.6), (9, 1.5, 0.3))
    assert pot_lines(balls, 6) == pot_lines(list(reversed(balls)), 6)


# --- pot_pockets: which pockets, not only how many -------------------------------------------
def test_pot_pockets_lists_the_pockets_with_a_line_and_pot_lines_counts_them():
    for balls in (
        table(CUE_AT, TARGET),
        table(CUE_AT, TARGET, (9, 0.17, 0.17)),
        table(CUE_AT, TARGET, (8, 0.9, 0.6), (9, 1.5, 0.3)),
    ):
        for hand in (False, True):
            pockets = pot_pockets(balls, 6, cue_in_hand=hand)
            assert pockets == sorted(set(pockets)) and all(0 <= i < len(POCKETS) for i in pockets)
            assert pot_lines(balls, 6, cue_in_hand=hand) == len(pockets)


def test_pot_pockets_names_the_corner_the_ball_is_near_and_loses_it_when_blocked():
    corner = min(range(len(POCKETS)), key=lambda i: POCKETS[i][0] ** 2 + POCKETS[i][1] ** 2)
    assert corner in pot_pockets(table(CUE_AT, TARGET), 6)
    blocker = (9, 0.17, 0.17)  # between the 6 and that corner
    assert corner not in pot_pockets(table(CUE_AT, TARGET, blocker), 6)


def test_pot_pockets_with_a_tighter_cut_limit_is_a_subset():
    balls = table(CUE_AT, TARGET)
    loose = pot_pockets(balls, 6, max_cut_deg=75.0)
    tight = pot_pockets(balls, 6, max_cut_deg=30.0)
    assert set(tight) <= set(loose)
    assert (
        pot_pockets(balls, 6, max_cut_deg=89.0) != []
        and pot_pockets(balls, 6, max_cut_deg=0.5) == []
    )


def test_pot_pockets_of_a_ball_off_the_table_or_with_no_cue_ball_is_empty():
    assert pot_pockets([*table(CUE_AT), Ball(6, 0.3, 0.3, in_play=False)], 6) == []
    assert pot_pockets(table(TARGET), 6) == []
    assert pot_pockets(table(TARGET), 6, cue_in_hand=True) != []
