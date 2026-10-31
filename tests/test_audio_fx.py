import math

import numpy as np
import pygame as pg
import pytest

from game import audio
from game.audio import Audio, volume_for_speed
from game.config import (
    MAX_RIPPLES,
    POCKET_ANIM_S,
    RIPPLE_S,
    SAMPLE_RATE,
    SFX_MAX_PER_FRAME,
    SHAKE_PX,
    SHAKE_S,
)
from game.physics import BallHitBall, BallHitCushion, BallPocketed
from game.render.fx import Fx

SYNTHS = [
    audio.synth_ball_hit,
    audio.synth_cushion,
    audio.synth_pocket,
    audio.synth_cue_hit,
    audio.synth_ball_pick,
    audio.synth_ball_put,
    audio.synth_click,
]


# --- AC6: synthesised sounds ------------------------------------------------------------------
@pytest.mark.parametrize("synth", SYNTHS)
def test_synth_is_audible_short_and_within_int16(synth):
    x = synth()
    assert x.dtype == np.int16
    assert 0.02 * SAMPLE_RATE < x.size < 0.5 * SAMPLE_RATE  # 20 ms .. 500 ms
    assert np.max(np.abs(x)) > 10000  # audible
    assert np.max(np.abs(x.astype(np.int32))) <= 32767


@pytest.mark.parametrize("synth", SYNTHS)
def test_synth_is_reproducible(synth):
    assert np.array_equal(synth(), synth())


def test_volume_grows_with_speed_and_stays_in_range():
    vs = [volume_for_speed(s) for s in (0.0, 0.5, 2.0, 6.0, 20.0)]
    assert vs == sorted(vs) and 0.0 < vs[0] < vs[-1] <= 1.0


@pytest.fixture
def sound():
    pg.mixer.quit()
    a = Audio()
    yield a
    pg.mixer.quit()


def test_audio_plays_and_obeys_mute(sound):
    assert sound.available
    assert sound.on_events([BallHitBall(1, 2, 3.0)]) == 1
    sound.toggle_mute()
    assert sound.muted and sound.on_events([BallHitBall(1, 2, 3.0)]) == 0


def test_audio_caps_sounds_per_frame_and_keeps_the_loudest(sound):
    many = [BallHitBall(1, 2, 0.1 * i) for i in range(1, 40)] + [BallHitCushion(3, 5.0)]
    started = sound.on_events(many)
    assert 0 < started <= SFX_MAX_PER_FRAME


def test_pocket_sound_is_always_included(sound):
    many = [BallHitBall(1, 2, 3.0)] * 20 + [BallPocketed(4, 0)]
    assert sound.on_events(many) >= 1


def test_game_runs_silent_when_there_is_no_audio_device(monkeypatch):
    pg.mixer.quit()

    def boom(*a, **k):
        raise pg.error("no device")

    monkeypatch.setattr(pg.mixer, "init", boom)
    a = Audio()
    assert not a.available
    a.play_click()
    a.play_shot(1.0)
    a.play_cue_pick()
    a.play_cue_put()
    assert a.on_events([BallHitBall(1, 2, 3.0), BallPocketed(1, 0)]) == 0


def test_the_cue_ball_in_hand_has_its_own_pick_up_and_put_down_sounds():
    played = []
    a = Audio.__new__(Audio)
    a._play = lambda name, volume: played.append(name) or True
    a.play_cue_pick()
    a.play_cue_put()
    assert played == ["pick", "put"]  # not the shared button click any more


def test_the_pick_up_rises_and_the_put_down_is_lower_than_the_ball_hit():
    pick, put, hit = audio.synth_ball_pick(), audio.synth_ball_put(), audio.synth_ball_hit()
    assert _loudest_pitch(pick[: pick.size // 3]) < _loudest_pitch(pick[pick.size // 3 :])
    assert _loudest_pitch(put) < _loudest_pitch(hit)  # a thud on the cloth, not a ball's tok


# --- AC7: effects ------------------------------------------------------------------------------
def test_ripples_expire_and_are_capped():
    fx = Fx()
    for _ in range(MAX_RIPPLES + 10):
        fx.add_ripple(1.0, 0.5)
    assert len(fx.ripples) == MAX_RIPPLES
    fx.update(RIPPLE_S + 0.01)
    assert fx.ripples == []


def test_pocket_drop_expires():
    fx = Fx()
    fx.add_drop(3, 0.05, 0.05, 0)
    fx.update(POCKET_ANIM_S / 2)
    assert len(fx.drops) == 1
    fx.update(POCKET_ANIM_S)
    assert fx.drops == []


def test_shake_starts_decays_and_ends_at_zero():
    fx = Fx()
    assert fx.shake_offset() == (0.0, 0.0)
    fx.shake()
    peak = max(abs(v) for v in fx.shake_offset())
    assert 0 < peak <= SHAKE_PX
    fx.update(SHAKE_S + 0.01)
    assert fx.shake_offset() == (0.0, 0.0)


def test_clear_resets_everything():
    fx = Fx()
    fx.add_ripple(0, 0)
    fx.add_drop(1, 0, 0, 0)
    fx.shake()
    fx.clear()
    assert fx.ripples == [] and fx.drops == [] and fx.shake_offset() == (0.0, 0.0)


# --- the spin dial's sound: a soft round tok the ear can hear, not the button blip ----------------
SPIN_FREQS = [f for low, _ in audio.SPIN_SOUNDS.values() for f in audio.spin_notes(low)]


def _loudest_pitch(samples: np.ndarray) -> float:
    spectrum = np.abs(np.fft.rfft(samples.astype(float), n=1 << 16))
    return float(np.argmax(spectrum) * SAMPLE_RATE / (1 << 16))


def _heard(samples: np.ndarray, volume: float) -> float:
    """How loud it sounds to an ear (A-weighted: dull below ~300 Hz) at this playback volume.
    The first sound made for the dial (165-262 Hz) scored 25-42% of the quietest button blip and
    could not be heard on a laptop; these must not fall back there."""

    def a_weight(f: float) -> float:
        f2 = f * f
        top = 12194**2 * f2 * f2
        low = (f2 + 20.6**2) * math.sqrt((f2 + 107.7**2) * (f2 + 737.9**2)) * (f2 + 12194**2)
        return top / low / 0.7943

    x = samples.astype(float) / 32768
    freqs = np.fft.rfftfreq(x.size, 1 / SAMPLE_RATE)
    weights = np.array([a_weight(max(f, 1.0)) for f in freqs])
    power = np.sum((np.abs(np.fft.rfft(x)) * weights) ** 2)
    return math.sqrt(power / x.size) * volume


@pytest.mark.parametrize("freq", SPIN_FREQS)
def test_the_spin_sound_is_a_short_round_tone_in_the_middle_of_the_range(freq):
    s = audio.synth_spin(freq)
    assert s.dtype == np.int16 and 0.03 < s.size / SAMPLE_RATE < 0.12 and np.max(np.abs(s)) > 3000
    assert abs(_loudest_pitch(s) - freq) < 12  # it IS the note it should be
    assert 300 <= freq <= 1000  # a laptop speaker plays this; the button blips are above
    power = np.abs(np.fft.rfft(s.astype(float))) ** 2
    cut = int(2500 * s.size / SAMPLE_RATE)
    assert power[cut:].sum() < 0.01 * power.sum()  # no whistle


def test_the_spin_sounds_are_audible_softer_than_the_button_blip_and_equal_to_each_other():
    blip = _heard(audio.synth_blip(), 0.30)  # the quietest button sound: the yardstick
    means = []
    for name, (lowest, volume) in audio.SPIN_SOUNDS.items():
        levels = [_heard(audio.synth_spin(f), volume) / blip for f in audio.spin_notes(lowest)]
        assert all(0.55 <= x <= 1.0 for x in levels), (name, levels)  # heard, but softer
        means.append(sum(levels) / len(levels))
    assert max(means) / min(means) < 1.2  # the three differ in pitch, not in loudness


@pytest.mark.parametrize("lowest", [low for low, _ in audio.SPIN_SOUNDS.values()])
def test_the_nine_notes_climb_a_semitone_at_a_time(lowest):
    notes = audio.spin_notes(lowest)
    assert len(notes) == audio.SPIN_STEPS == 9 and notes[0] == lowest
    for a, b in zip(notes, notes[1:], strict=False):
        assert b / a == pytest.approx(2 ** (1 / 12), rel=0.01)


def test_play_spin_picks_the_note_by_level_and_plays_it_at_the_sounds_volume():
    played = []
    a = Audio.__new__(Audio)
    a._spin_volume = 0.3
    a._play = lambda name, volume: played.append((name, volume)) or True
    for level in (-1.0, 0.0, 1.0, -5.0, 5.0):
        a.play_spin(level)
    assert played == [(f"spin{i}", 0.3) for i in (0, 4, 8, 0, 8)]


def test_the_environment_picks_which_spin_sound_the_game_makes(monkeypatch):
    monkeypatch.setenv("NEONPOOL_SPIN_SOUND", "SANG")
    chosen = Audio()
    assert chosen.spin_notes == audio.spin_notes(audio.SPIN_SOUNDS["SANG"][0])
    assert chosen._spin_volume == audio.SPIN_SOUNDS["SANG"][1]
    monkeypatch.setenv("NEONPOOL_SPIN_SOUND", "nonsense")
    default = Audio()
    assert default.spin_notes == audio.spin_notes(audio.SPIN_SOUNDS[audio.DEFAULT_SPIN_SOUND][0])
