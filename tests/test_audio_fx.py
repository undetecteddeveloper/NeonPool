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
    assert a.on_events([BallHitBall(1, 2, 3.0), BallPocketed(1, 0)]) == 0


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


# --- the spin dial's sound: low and soft, not the button blip -------------------------------------
def _loudest_pitch(samples: np.ndarray) -> float:
    spectrum = np.abs(np.fft.rfft(samples.astype(float), n=1 << 16))
    return float(np.argmax(spectrum) * SAMPLE_RATE / (1 << 16))


@pytest.mark.parametrize("freq", audio.SPIN_NOTES)
def test_the_spin_sound_is_low_and_short_and_has_no_high_whistle(freq):
    s = audio.synth_spin(freq)
    assert s.dtype == np.int16 and 0.03 < s.size / SAMPLE_RATE < 0.12 and np.max(np.abs(s)) > 3000
    assert abs(_loudest_pitch(s) - freq) < 12  # it IS the note it should be
    power = np.abs(np.fft.rfft(s.astype(float))) ** 2
    cut = int(1000 * s.size / SAMPLE_RATE)
    assert power[cut:].sum() < 0.01 * power.sum()  # next to nothing above 1 kHz


def test_the_spin_notes_climb_from_low_to_high_and_stay_far_below_the_button_blips():
    assert list(audio.SPIN_NOTES) == sorted(audio.SPIN_NOTES)
    assert len(set(audio.SPIN_NOTES)) == len(audio.SPIN_NOTES) == 9
    assert max(audio.SPIN_NOTES) < 400 < min(audio.TICK_NOTES)


def test_play_spin_picks_the_note_by_level_and_is_silent_when_muted():
    played = []
    a = Audio.__new__(Audio)
    a._play = lambda name, volume: played.append(name) or True
    for level in (-1.0, 0.0, 1.0, -5.0, 5.0):
        a.play_spin(level)
    assert played == ["spin0", "spin4", "spin8", "spin0", "spin8"]
