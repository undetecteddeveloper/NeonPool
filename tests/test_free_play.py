from game.physics import BallHitBall, BallPocketed
from game.rules.free_play import FreePlay


def test_counts_shots_and_balls_left():
    fp = FreePlay()
    assert (fp.shots, fp.balls_left) == (0, 15)
    fp.on_shot()
    fp.on_shot()
    fp.on_events([BallPocketed(3, 1), BallPocketed(9, 4), BallHitBall(1, 2, 1.0)])
    assert (fp.shots, fp.balls_left) == (2, 13)
    assert fp.pocketed == {3, 9}


def test_cue_pocketed_is_reported_once_and_not_counted_as_a_ball():
    fp = FreePlay()
    fp.on_events([BallPocketed(0, 2)])
    assert fp.balls_left == 15
    assert fp.take_cue_respawn() is True
    assert fp.take_cue_respawn() is False


def test_same_ball_pocketed_twice_counts_once():
    fp = FreePlay()
    fp.on_events([BallPocketed(5, 0), BallPocketed(5, 0)])
    assert fp.balls_left == 14


def test_reset():
    fp = FreePlay()
    fp.on_shot()
    fp.on_events([BallPocketed(1, 0), BallPocketed(0, 0)])
    fp.reset()
    assert (fp.shots, fp.balls_left, fp.cue_pocketed) == (0, 15, False)
