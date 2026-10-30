"""The result card's numbers counting up, one after the other, with ticks and a bell."""

import numpy as np
import pygame as pg
import pytest

from game import audio, config, i18n
from game.app import App
from game.physics import BallHitBall, BallPocketed
from game.render import hud
from game.rules.eight_ball import SOLID, WON
from game.tally import Tally

START = config.TALLY_START_S
GAP = config.TALLY_GAP_S
SPANS = dict(config.TALLY_SPANS)


def at(name: str) -> tuple[float, float]:
    """(when the number starts, when it stops) in seconds after the game ended."""
    start = START
    for n, seconds in config.TALLY_SPANS:
        if n == name:
            return start, start + seconds
        start += seconds + GAP
    raise KeyError(name)


# --- the clock itself ----------------------------------------------------------------------------
def test_the_numbers_count_one_after_the_other_in_the_order_score_shots_fouls():
    t = Tally({"score": 480, "shots": 22, "fouls": 6})
    assert [n for n, _ in config.TALLY_SPANS] == ["score", "shots", "fouls"]
    assert at("score")[1] < at("shots")[0] and at("shots")[1] < at("fouls")[0]  # a pause between
    assert t.total_s == pytest.approx(at("fouls")[1])
    mid_score = (at("score")[0] + at("score")[1]) / 2
    assert 0 < t.value("score", mid_score) < 480
    assert t.value("shots", mid_score) == 0 and t.value("fouls", mid_score) == 0  # not yet


def test_everything_is_zero_before_the_count_starts_and_whole_after_it():
    t = Tally({"score": 480, "shots": 22, "fouls": 6})
    assert [t.value(n, 0.0) for n in t.targets] == [0, 0, 0]
    assert [t.value(n, START - 0.01) for n in t.targets] == [0, 0, 0]
    assert [t.value(n, t.total_s) for n in t.targets] == [480, 22, 6]
    assert [t.value(n, 99.0) for n in t.targets] == [480, 22, 6]
    assert not t.finished("score", at("score")[1] - 0.01) and t.finished("score", at("score")[1])


def test_a_number_only_goes_up_and_slows_down_as_it_settles():
    t = Tally({"score": 900, "shots": 0, "fouls": 0})
    s, e = at("score")
    values = [t.value("score", s + (e - s) * i / 40) for i in range(41)]
    assert values == sorted(values) and values[0] == 0 and values[-1] == 900
    steps = np.diff(values)
    assert steps[:5].sum() > steps[-5:].sum() * 3  # fast at the start, slow at the end


def test_ticks_are_few_when_the_number_is_small_and_capped_when_it_is_big():
    t = Tally({"score": 990, "shots": 5, "fouls": 0})
    assert t.ticks_done("shots", 99.0) == 5  # one tick per step
    assert t.ticks_done("score", 99.0) == config.TALLY_MAX_TICKS  # not 990 of them
    assert t.ticks_done("fouls", 99.0) == 0  # nothing to count: silence
    assert t.ticks_done("score", 0.0) == 0


def test_ticks_come_quickly_at_first_and_slow_down_with_the_number():
    t = Tally({"score": 990, "shots": 0, "fouls": 0})
    s, e = at("score")
    when = []
    for k in range(1, config.TALLY_MAX_TICKS + 1):
        lo, hi = s, e
        for _ in range(30):  # the moment the k-th tick sounds
            mid = (lo + hi) / 2
            lo, hi = (mid, hi) if t.ticks_done("score", mid) < k else (lo, mid)
        when.append(hi)
    gaps = np.diff(when)
    assert all(a <= b + 1e-3 for a, b in zip(gaps, gaps[1:], strict=False))  # never speeding up
    assert gaps[-1] > gaps[0] * 2


def test_the_tick_pitch_climbs_from_low_to_high():
    t = Tally({"score": 990, "shots": 3, "fouls": 0})
    pitches = [t.tick_pitch("score", k) for k in range(1, config.TALLY_MAX_TICKS + 1)]
    assert pitches[0] == 0.0 and pitches[-1] == 1.0 and pitches == sorted(pitches)
    assert [t.tick_pitch("shots", k) for k in (1, 2, 3)] == [0.0, 0.5, 1.0]
    assert t.tick_pitch("score", 1) == 0.0  # and a single tick sits at the bottom


def test_a_number_that_just_stopped_glows_and_then_fades():
    t = Tally({"score": 480, "shots": 22, "fouls": 0})
    _, end = at("score")
    assert t.flash("score", end - 0.05) == 0.0  # still counting
    assert t.flash("score", end) == 1.0
    assert 0.0 < t.flash("score", end + config.TALLY_FLASH_S / 2) < 1.0
    assert t.flash("score", end + config.TALLY_FLASH_S) == 0.0
    assert t.flash("fouls", at("fouls")[1] + 0.01) == 0.0  # a 0 has nothing to celebrate


# --- the sounds ----------------------------------------------------------------------------------
def test_the_ticks_and_bells_are_short_audible_int16_sounds():
    for freq in audio.TICK_NOTES:
        x = audio.synth_tick(freq)
        assert x.dtype == np.int16 and 0.02 * config.SAMPLE_RATE < x.size < 0.1 * config.SAMPLE_RATE
        assert np.max(np.abs(x)) > 8000
    assert list(audio.TICK_NOTES) == sorted(audio.TICK_NOTES)  # a climb
    win, lose = audio.synth_ting(1319, 1976), audio.synth_ting(440, 659)
    assert win.dtype == np.int16 and np.max(np.abs(win)) > 10000 and np.max(np.abs(lose)) > 10000
    assert not np.array_equal(win, lose)


def test_a_bell_after_a_win_is_higher_than_after_a_loss():
    def pitch(x):  # the strongest frequency
        spec = np.abs(np.fft.rfft(x.astype(float)))
        return np.argmax(spec) * config.SAMPLE_RATE / x.size

    assert pitch(audio.synth_ting(1319, 1976)) > pitch(audio.synth_ting(440, 659)) * 1.5


# --- on the result card --------------------------------------------------------------------------
@pytest.fixture
def app():
    pg.init()
    a = App(pg.display.set_mode(config.LOGICAL_SIZE))
    a.go_play()
    a.skip_transition()
    yield a
    pg.quit()
    i18n.set_lang("vi")


def win(app, shots: int = 4, fouls: int = 2):
    """A game that ends in a win after `shots` shots and `fouls` fouls."""
    rules = app.play.rules
    after_break = [BallHitBall(0, 1, 1.0), BallPocketed(1, 0)]
    rules.on_shot()
    rules.on_events(after_break)
    rules.finish_shot()
    rules.group, rules.pocketed = SOLID, set(range(1, 8))
    rules.shots, rules.fouls = shots - 1, fouls
    rules.on_shot()
    rules.on_events([BallHitBall(0, 8, 1.0), BallPocketed(8, 0)])
    app.play._live = True
    app.update(1 / 60)
    assert rules.phase == WON and rules.shots == shots


def run(app, seconds):
    for _ in range(round(seconds * 60)):
        app.update(1 / 60)
        app.draw()


def record(app, monkeypatch):
    heard = []
    monkeypatch.setattr(app.audio, "play_tally_tick", lambda pitch: heard.append(("tick", pitch)))
    monkeypatch.setattr(
        app.audio, "play_tally_ting", lambda won, big: heard.append(("ting", won, big))
    )
    return heard


def test_when_a_game_ends_the_card_starts_at_zero_and_counts_up_to_the_real_numbers(app):
    win(app, shots=22, fouls=6)
    play = app.play
    assert play._tally is not None and play._tally.targets == {
        "score": 480,
        "shots": 22,
        "fouls": 6,
    }
    seen = []
    orig_full, orig_live = hud.draw_result, hud.draw_result_live

    def spy_full(*a, **k):
        seen.append((k["score"], [v for _, v in k["rows"]]))
        return orig_full(*a, **k)

    def spy_live(*a, **k):  # once the card has settled only its moving part is drawn
        seen.append((k["score"], list(k["values"])))
        return orig_live(*a, **k)

    hud.draw_result, hud.draw_result_live = spy_full, spy_live
    try:
        run(app, 0.5)  # the card has opened: nothing has started to count
        assert seen[-1] == (0, [0, 0])
        run(app, at("score")[0] + 0.3)  # inside the score's run
        mid_score, mid_rows = seen[-1]
        assert 0 < mid_score < 480 and mid_rows == [0, 0]
        run(app, play._tally.total_s + 0.2)
        assert seen[-1] == (480, [22, 6])
    finally:
        hud.draw_result, hud.draw_result_live = orig_full, orig_live


def test_the_numbers_tick_while_they_climb_and_ring_a_bell_when_each_stops(app, monkeypatch):
    win(app, shots=22, fouls=0)
    heard = record(app, monkeypatch)
    run(app, app.play._tally.total_s + 0.5)
    ticks = [h for h in heard if h[0] == "tick"]
    bells = [h for h in heard if h[0] == "ting"]
    assert len(ticks) == config.TALLY_MAX_TICKS * 2  # the score and the shots (14 each), no fouls
    assert bells == [("ting", True, True), ("ting", True, False)]  # the score's is the big one
    assert [h[1] for h in ticks[: config.TALLY_MAX_TICKS]] == sorted(
        h[1] for h in ticks[: config.TALLY_MAX_TICKS]
    )  # the score's ticks climb


def test_a_lost_game_rings_the_lower_bell(app, monkeypatch):
    app.play.rules.on_shot()
    app.play.rules.on_events([BallHitBall(0, 3, 1.0), BallPocketed(8, 0)])  # the 8 goes in early
    app.play.rules.group, app.play.rules.is_break = None, False  # not the break: a real loss
    app.play._live = True
    app.update(1 / 60)
    heard = record(app, monkeypatch)
    run(app, app.play._tally.total_s + 0.5)
    assert all(h[1] is False for h in heard if h[0] == "ting")


def test_nothing_is_heard_for_a_zero(app, monkeypatch):
    win(app, shots=3, fouls=0)
    heard = record(app, monkeypatch)
    run(app, app.play._tally.total_s + 0.5)
    assert len([h for h in heard if h[0] == "ting"]) == 2  # score and shots; the 0 fouls stay quiet


def test_the_buttons_work_while_the_numbers_are_still_counting(app):
    win(app, shots=22, fouls=6)
    run(app, 0.8)  # the score is part-way
    assert app.play._tally.counting("score", app.play._clock - app.play._ended_at)
    app.handle_event(pg.event.Event(pg.KEYDOWN, key=pg.K_RETURN))
    assert app.play.rules.phase == "playing" and app.play._tally is None


def test_a_card_that_was_not_counted_shows_the_whole_numbers_at_once(app):
    app.play.rules.phase = WON
    app.play.rules.shots, app.play.rules.fouls = 22, 6
    assert app.play._tally is None
    app.draw()  # drawn whole, not counting (this is how the how-to-play pictures show it)


@pytest.mark.parametrize("lang", ["vi", "en"])
def test_every_moment_of_the_count_draws_in_both_languages(app, lang):
    i18n.set_lang(lang)
    win(app, shots=22, fouls=6)
    run(app, app.play._tally.total_s + 0.6)


def test_the_count_is_paused_with_the_game_while_the_help_card_is_open(app, monkeypatch):
    win(app, shots=22, fouls=0)
    heard = record(app, monkeypatch)
    run(app, 0.3)
    app.open_help()
    n = len(heard)
    run(app, 3.0)  # time passes, but the table (and its counting) waits behind the card
    assert len(heard) == n


def test_once_the_card_has_settled_the_table_behind_it_is_a_picture(app, monkeypatch):
    win(app, shots=22, fouls=6)
    play = app.play
    size = pg.display.get_surface().get_size()
    run(app, 0.5)
    assert not play._frozen.covers(size)  # the table may still be moving: it is drawn each frame
    run(app, 2.0)
    assert play._frozen.covers(size)
    drawn = []
    real = play.fx.draw
    monkeypatch.setattr(play.fx, "draw", lambda *a, **k: (drawn.append(1), real(*a, **k)))
    run(app, 0.5)
    assert drawn == []  # the table is not drawn again
    app.handle_event(pg.event.Event(pg.KEYDOWN, key=pg.K_RETURN))  # a new game: the table is live
    assert not play._frozen.covers(size)
    run(app, 0.2)
    assert drawn
