"""Background music: the loops made in code, and how the game fades them in and out."""

import numpy as np
import pygame as pg
import pytest

from game import config, music
from game.app import App
from game.audio import Audio
from game.rules.eight_ball import LOST, WON


# --- the loops themselves (no mixer needed) -------------------------------------------------
@pytest.fixture(scope="module")
def loops():
    return {name: music.render(style) for name, style in music.STYLES.items()}


def test_there_are_two_candidates_for_the_menu_and_two_for_the_table():
    assert set(music.STYLES) == {"menu_dusk", "menu_city", "play_focus", "play_pulse"}
    assert music.TRACKS["menu"].name.startswith("menu_")
    assert music.TRACKS["play"].name.startswith("play_")
    assert config.MUSIC_CHANNELS == len(music.TRACKS)  # one reserved channel per track


def test_a_loop_is_as_long_as_its_bars_and_tempo_say():
    style = music.MENU_DUSK
    assert style.bars == len(style.chords) * style.bars_per_chord
    assert style.loop_s == pytest.approx(style.bars * 4 * 60 / style.bpm)
    assert 12 < style.loop_s < 60  # long enough not to nag, short enough to be small


@pytest.mark.parametrize("name", list(music.STYLES))
def test_every_loop_is_audible_mono_int16_and_not_clipped(loops, name):
    x = loops[name]
    style = music.STYLES[name]
    assert x.dtype == np.int16 and x.ndim == 1
    assert x.size == round(style.loop_s * config.SAMPLE_RATE)
    f = x.astype(np.float32) / 32767
    rms = float(np.sqrt(np.mean(f * f)))
    assert rms == pytest.approx(music.TARGET_RMS, rel=0.15)  # all the loops are equally loud
    assert np.max(np.abs(f)) < 0.96  # a soft ceiling, no clipping


@pytest.mark.parametrize("name", list(music.STYLES))
def test_every_loop_joins_its_own_start_without_a_click(loops, name):
    x = loops[name].astype(np.float32) / 32767
    join = abs(float(x[0] - x[-1]))
    normal = float(np.max(np.abs(np.diff(x))))
    assert join <= normal  # the step from the last sample to the first is an ordinary one


def test_the_same_style_always_gives_the_same_samples(loops):
    assert np.array_equal(music.render(music.PLAY_FOCUS), loops["play_focus"])


def test_the_styles_really_differ(loops):
    names = list(loops)
    for i, a in enumerate(names):
        for b in names[i + 1 :]:
            n = min(loops[a].size, loops[b].size)
            assert not np.array_equal(loops[a][:n], loops[b][:n]), (a, b)


def test_the_layers_do_what_they_are_called():
    base = music.Style("t", 120, ((57, music.MINOR),), bars_per_chord=1, pad=0.8)
    with_kick = music.Style("t", 120, ((57, music.MINOR),), bars_per_chord=1, pad=0.8, kick=0.8)
    a, b = music.render(base), music.render(with_kick)
    beat = round(60 / 120 * config.SAMPLE_RATE)
    assert np.max(np.abs(b[:200].astype(int))) != np.max(np.abs(a[:200].astype(int)))
    # the kick is a low thump on the beat: more energy right after beat 2 than between beats
    hit = np.abs(b[2 * beat : 2 * beat + 2000].astype(float)).mean()
    quiet = np.abs(b[2 * beat + beat // 2 : 2 * beat + beat // 2 + 2000].astype(float)).mean()
    assert hit > quiet


# --- playing them (the dummy mixer: channels and volumes are real, there is no sound) --------
@pytest.fixture
def audio(monkeypatch):
    monkeypatch.delenv("NEONPOOL_NO_MUSIC", raising=False)  # these tests want the music
    pg.init()
    a = Audio()
    assert a.available
    yield a
    pg.quit()


def ready(a: Audio, track: str = "menu", dt: float = 1 / 60) -> None:
    """Start the music and wait for the tracks to be made (they come from a thread)."""
    a.update_music(dt, track)
    assert a._music_thread is not None
    a._music_thread.join(20)
    a.update_music(dt, track)  # picks the finished tracks up


def run(a: Audio, track: str | None, seconds: float, duck: bool = False) -> None:
    for _ in range(round(seconds * 60)):
        a.update_music(1 / 60, track, duck)


def test_music_fades_in_on_its_own_channel_and_loops(audio):
    ready(audio, "menu")
    run(audio, "menu", 1.5)
    assert audio.music_level("menu") == 1.0 and audio.music_level("play") == 0.0
    assert pg.mixer.Channel(0).get_busy() and not pg.mixer.Channel(1).get_busy()
    want = audio.music_volume * config.MUSIC_GAIN
    assert pg.mixer.Channel(0).get_volume() == pytest.approx(want, abs=0.02)


def test_going_from_the_menu_to_the_table_crosses_the_two_tracks(audio):
    ready(audio, "menu")
    run(audio, "menu", 1.5)
    run(audio, "play", config.MUSIC_FADE_S / 2)
    assert 0.3 < audio.music_level("menu") < 0.7 and 0.3 < audio.music_level("play") < 0.7
    run(audio, "play", config.MUSIC_FADE_S)
    assert audio.music_level("menu") == 0.0 and not pg.mixer.Channel(0).get_busy()
    assert pg.mixer.Channel(1).get_busy()


def test_the_music_has_its_own_volume_and_mute_silences_it(audio):
    ready(audio, "menu")
    run(audio, "menu", 1.5)
    audio.volume = 0.0  # the effects off: the music is not touched
    run(audio, "menu", 0.1)
    assert pg.mixer.Channel(0).get_volume() > 0.05
    audio.music_volume = 0.0
    run(audio, "menu", 0.1)
    assert pg.mixer.Channel(0).get_volume() == 0.0
    audio.music_volume = 1.0
    audio.muted = True
    run(audio, "menu", 0.1)
    assert pg.mixer.Channel(0).get_volume() == 0.0
    audio.muted = False
    run(audio, "menu", 0.1)
    assert pg.mixer.Channel(0).get_volume() == pytest.approx(config.MUSIC_GAIN, abs=0.02)


def test_the_music_ducks_under_the_result_jingle_and_comes_back(audio):
    ready(audio, "play")
    run(audio, "play", 1.5)
    full = pg.mixer.Channel(1).get_volume()
    run(audio, "play", 1.0, duck=True)
    assert pg.mixer.Channel(1).get_volume() == pytest.approx(full * config.MUSIC_DUCK, abs=0.02)
    run(audio, "play", 1.0)
    assert pg.mixer.Channel(1).get_volume() == pytest.approx(full, abs=0.02)


def test_effects_never_take_the_music_channels(audio):
    for _ in range(40):  # far more sounds than there are channels
        audio.play_win()
        audio.play_click()
    assert not pg.mixer.Channel(0).get_busy() and not pg.mixer.Channel(1).get_busy()


def test_without_a_sound_device_or_with_music_off_nothing_breaks(audio, monkeypatch):
    audio.available = False
    audio.update_music(1 / 60, "menu")
    assert audio._music_thread is None  # nothing was started
    audio.available = True
    monkeypatch.setenv("NEONPOOL_NO_MUSIC", "1")
    audio.update_music(1 / 60, "menu")
    assert audio._music_thread is None and audio.music_level("menu") == 0.0


# --- the game asks for the right track ----------------------------------------------------------
@pytest.fixture
def app(monkeypatch):
    monkeypatch.delenv("NEONPOOL_NO_MUSIC", raising=False)
    pg.init()
    a = App(pg.display.set_mode(config.LOGICAL_SIZE))
    a.update(1 / 60)
    a.audio._music_thread.join(20)
    yield a
    pg.quit()


def run_app(app, seconds):
    for _ in range(round(seconds * 60)):
        app.update(1 / 60)


def test_the_menu_plays_its_track_and_the_table_plays_the_other(app):
    run_app(app, 1.5)
    assert app.audio.music_level("menu") == 1.0
    app.go_play()
    app.skip_transition()
    run_app(app, 2.5)
    assert app.audio.music_level("play") == 1.0 and app.audio.music_level("menu") == 0.0
    app.go_menu()
    run_app(app, 2.5)
    assert app.audio.music_level("menu") == 1.0


def test_the_how_to_play_card_and_the_settings_panel_keep_the_same_music(app):
    app.go_play()
    app.skip_transition()
    run_app(app, 2.5)
    app.open_help()
    run_app(app, 1.5)
    assert app.audio.music_level("play") == 1.0  # the card is over the table: same music


@pytest.mark.parametrize("phase", [WON, LOST])
def test_the_result_card_ducks_the_music(app, phase):
    app.go_play()
    app.skip_transition()
    run_app(app, 2.5)
    app.play.rules.phase = phase
    run_app(app, 1.0)
    assert app.audio._duck == pytest.approx(config.MUSIC_DUCK, abs=0.03)


def test_the_music_setting_reaches_the_player_and_is_kept(app):
    app.change_settings(music=0.2)
    assert app.audio.music_volume == pytest.approx(0.2)
    assert app.settings.music == pytest.approx(0.2)
