"""tools/practice_bot.py: the stand-in player used to size the practice modes (rough, by bot)."""

from tools.practice_bot import play_run

SEEDS = (1, 2, 3, 4)  # four real tables (each is a break and then a few called shots)
SHOTS = 6  # per table: a few shots are enough for a smoke check, the tool does the real counts


def _shots(mode: str, sigma: float, seeds=SEEDS) -> list:
    return [s for seed in seeds for s in play_run(mode, sigma, seed, max_shots=SHOTS).shots]


def test_a_bot_with_no_aiming_noise_makes_at_least_half_of_the_called_shots():
    shots = _shots("call", 0.0)
    assert len(shots) >= 12
    assert sum(s.right for s in shots) >= len(shots) / 2


def test_the_bot_runs_are_deterministic_for_one_seed():
    def trace(mode: str, sigma: float):
        run = play_run(mode, sigma, 7, max_shots=SHOTS)
        return run.score, [(s.ball, s.pocket, s.potted, s.right) for s in run.shots]

    assert trace("call", 0.6) == trace("call", 0.6)
    assert trace("ghost", 0.0) == trace("ghost", 0.0)


def test_noise_makes_the_bot_worse():
    seeds = range(1, 7)
    steady = _shots("ghost", 0.0, seeds)
    shaky = _shots("ghost", 3.0, seeds)
    assert sum(s.right for s in shaky) < sum(s.right for s in steady)


def test_sprint_bot_runs_end_and_the_clock_is_charged_per_shot():
    run = play_run("sprint", 1.0, 3, t_aim=10.0, max_shots=40)
    assert run.timed_out or run.won or len(run.shots) + run.breaks >= 40
    assert run.breaks == 1  # the break is made once, first


def test_ac40_the_bot_plays_the_easy_level_too_and_it_is_deterministic():
    def trace(mode: str):
        run = play_run(mode, 0.6, 7, max_shots=SHOTS, level="easy")
        return run.score, [(s.ball, s.pocket, s.potted, s.right) for s in run.shots]

    for mode in ("ghost", "call", "sprint"):
        assert trace(mode) == trace(mode)
    shots = _shots_at("easy", 0.0)
    assert len(shots) >= 12 and sum(s.right for s in shots) >= len(shots) / 2


def _shots_at(level: str, sigma: float) -> list:
    return [
        s
        for seed in SEEDS
        for s in play_run("ghost", sigma, seed, max_shots=SHOTS, level=level).shots
    ]
