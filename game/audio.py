"""Sound effects and music synthesised in code (no asset files). No device => silent, game still
runs."""

from __future__ import annotations

import logging
import os
import threading
from collections.abc import Iterable

import numpy as np
import pygame as pg

from game import music
from game.config import (
    MENU_INTRO_S,
    MUSIC_CHANNELS,
    MUSIC_DUCK,
    MUSIC_DUCK_S,
    MUSIC_FADE_S,
    MUSIC_GAIN,
    SAMPLE_RATE,
    SFX_MAX_PER_FRAME,
    SFX_MIN_SPEED,
    SFX_REF_SPEED,
)
from game.physics import BallHitBall, BallHitCushion, BallPocketed, Event

log = logging.getLogger("neonpool")
_RNG_SEED = 1234  # fixed so the sounds are the same every run


def _t(seconds: float) -> np.ndarray:
    return np.arange(int(SAMPLE_RATE * seconds)) / SAMPLE_RATE


def _decay(t: np.ndarray, tau: float) -> np.ndarray:
    return np.exp(-t / tau)


def _noise(n: int) -> np.ndarray:
    return np.random.default_rng(_RNG_SEED).uniform(-1.0, 1.0, n)


def _to_int16(x: np.ndarray, gain: float = 0.9) -> np.ndarray:
    peak = float(np.max(np.abs(x))) or 1.0
    return (x / peak * gain * 32767).astype(np.int16)


def synth_ball_hit() -> np.ndarray:
    """Bright, short 'tok': two decaying tones plus a noise click."""
    t = _t(0.09)
    x = (
        0.6 * np.sin(2 * np.pi * 2300 * t) * _decay(t, 0.012)
        + 0.5 * np.sin(2 * np.pi * 1150 * t) * _decay(t, 0.02)
        + 0.5 * _noise(t.size) * _decay(t, 0.003)
    )
    return _to_int16(x)


def synth_cushion() -> np.ndarray:
    """Dull low 'thup'."""
    t = _t(0.14)
    x = (
        0.9 * np.sin(2 * np.pi * 170 * t) * _decay(t, 0.035)
        + 0.4 * np.sin(2 * np.pi * 340 * t) * _decay(t, 0.02)
        + 0.2 * _noise(t.size) * _decay(t, 0.004)
    )
    return _to_int16(x)


def synth_pocket() -> np.ndarray:
    """Drop: a falling tone, then a soft thud."""
    t = _t(0.32)
    freq = 700 * np.exp(-t * 7) + 140
    phase = 2 * np.pi * np.cumsum(freq) / SAMPLE_RATE
    x = 0.7 * np.sin(phase) * _decay(t, 0.12) + 0.5 * np.sin(2 * np.pi * 90 * t) * _decay(t, 0.09)
    return _to_int16(x)


def synth_cue_hit() -> np.ndarray:
    """Cue tip on the ball: sharp click over a thump."""
    t = _t(0.08)
    x = (
        0.7 * np.sin(2 * np.pi * 3200 * t) * _decay(t, 0.004)
        + 0.8 * np.sin(2 * np.pi * 150 * t) * _decay(t, 0.025)
        + 0.4 * _noise(t.size) * _decay(t, 0.002)
    )
    return _to_int16(x)


def synth_ball_pick() -> np.ndarray:
    """The cue ball is lifted: a light, bright tap that slips upwards."""
    t = _t(0.07)
    phase = 2 * np.pi * np.cumsum(1700 + 9000 * t) / SAMPLE_RATE
    x = np.sin(phase) * _decay(t, 0.016) + 0.4 * _noise(t.size) * _decay(t, 0.0015)
    return _to_int16(x * np.minimum(1.0, t / 0.002), gain=0.7)


def synth_ball_put() -> np.ndarray:
    """The cue ball is put down on the cloth: a soft thud, then a small tick."""
    t = _t(0.12)
    thud = np.sin(2 * np.pi * 210 * t) * _decay(t, 0.03)
    tick = np.convolve(_noise(t.size), np.ones(6) / 6, mode="same") * _decay(t, 0.004)
    return _to_int16(thud + 1.2 * tick, gain=0.8)


def synth_click() -> np.ndarray:
    """UI tick."""
    t = _t(0.05)
    return _to_int16(np.sin(2 * np.pi * 1300 * t) * _decay(t, 0.012))


# --- arcade UI sounds: soft square waves, like an 80s cabinet ---------------------------------
def _square(freq: float, seconds: float, tau: float, duty_soft: float = 0.35) -> np.ndarray:
    """A square-ish tone (a few odd harmonics, so it is round, not harsh) that dies away."""
    t = _t(seconds)
    x = sum(np.sin(2 * np.pi * freq * h * t) / h for h in (1, 3, 5)) * (1 - duty_soft)
    x += duty_soft * np.sin(2 * np.pi * freq * t)
    return x * _decay(t, tau) * np.minimum(1.0, t / 0.003)


def _notes(freqs: list[float], step: float, tau: float, tail: float = 0.0) -> np.ndarray:
    parts = [
        _square(f, step + (tail if i == len(freqs) - 1 else 0.0), tau) for i, f in enumerate(freqs)
    ]
    return np.concatenate(parts)


def synth_blip() -> np.ndarray:
    """The pointer moved onto another button: a short high blip."""
    return _to_int16(_square(1568, 0.045, 0.014), gain=0.5)


def synth_confirm() -> np.ndarray:
    """A button was pressed: two quick rising notes."""
    return _to_int16(_notes([988, 1319], 0.045, 0.03), gain=0.7)


def synth_win() -> np.ndarray:
    """The game is won: a bright rising arpeggio, the last note held."""
    return _to_int16(_notes([523, 659, 784, 1047, 1319], 0.085, 0.09, tail=0.25))


def synth_lose() -> np.ndarray:
    """The game is lost: three falling notes, low and slow."""
    return _to_int16(_notes([392, 311, 233], 0.16, 0.14, tail=0.2))


def synth_foul() -> np.ndarray:
    """A foul: a short low buzz."""
    t = _t(0.22)
    x = _square(110, 0.22, 0.09) + 0.5 * _square(116.5, 0.22, 0.09)
    return _to_int16(x * np.minimum(1.0, t / 0.01), gain=0.65)


def synth_notice() -> np.ndarray:
    """Good news (a group chosen, the 8 is next): a light two-note chime."""
    return _to_int16(_notes([1047, 1568], 0.07, 0.07, tail=0.12), gain=0.6)


# --- the clock of a shot, in its last seconds: a beep a second, a quicker double one at the end ---
def synth_warn() -> np.ndarray:
    return _to_int16(_square(880, 0.07, 0.02), gain=0.55)


def synth_warn_last() -> np.ndarray:
    return _to_int16(_notes([1175, 1175], 0.09, 0.02, tail=0.03), gain=0.6)


# --- the coin toss at the start of a two-player game: thrown, turning over (ticks), landing ------
def synth_coin_up() -> np.ndarray:
    """The coin is thrown: a quick rising sweep with a little air in it."""
    t = _t(0.24)
    phase = 2 * np.pi * np.cumsum(420 + 1500 * (t / 0.24) ** 1.6) / SAMPLE_RATE
    x = (0.7 * np.sin(phase) + 0.25 * np.sin(2 * phase)) * np.minimum(1.0, t / 0.01)
    x = x * _decay(t, 0.16) + 0.12 * _noise(t.size) * _decay(t, 0.05)
    return _to_int16(x, gain=0.55)


def synth_coin_land() -> np.ndarray:
    """The coin lands: a metallic clink (a bell with sharp, unmatched overtones), then a small
    one."""
    t = _t(0.75)

    def clink(at: float, amp: float) -> np.ndarray:
        age = np.maximum(t - at, 0.0)
        partials = ((2093, 1.0, 0.16), (3322, 0.35, 0.1), (5774, 0.5, 0.06))
        x = sum(a * np.sin(2 * np.pi * f * age) * _decay(age, tau) for f, a, tau in partials)
        return amp * (t >= at) * np.minimum(1.0, age / 0.001) * x

    return _to_int16(clink(0.0, 1.0) + clink(0.13, 0.45), gain=0.7)


# --- the result card's numbers counting up: ticks that climb a scale, then a bell ----------------
TICK_NOTES = (784, 880, 988, 1175, 1319, 1568, 1760, 1976)  # a pentatonic climb, G5 up to B6


def synth_tick(freq: float) -> np.ndarray:
    """One step of a counting number: a very short soft blip."""
    return _to_int16(_square(freq, 0.04, 0.011), gain=0.5)


def synth_ting(low: float, high: float) -> np.ndarray:
    """A number has stopped: a small glassy bell of two notes."""
    t = _t(0.6)
    x = (
        0.8 * np.sin(2 * np.pi * low * t) * _decay(t, 0.22)
        + 0.5 * np.sin(2 * np.pi * high * t) * _decay(t, 0.16)
        + 0.2 * np.sin(2 * np.pi * low * 2.76 * t) * _decay(t, 0.06)
    )
    return _to_int16(x * np.minimum(1.0, t / 0.002), gain=0.65)


# --- the spin dial: a soft round "tok" for each step, the pitch following the level -------------
# Three sounds, all the same loudness to the ear, differing in pitch only. The user listened and
# picked SANG; NEONPOOL_SPIN_SOUND still selects another, and tools/spin_sound_preview.py writes
# WAVs of them. name: (lowest note in Hz, playback volume). Nine notes a semitone apart, from
# the lowest (strike low) to the highest (strike high). The first try (165-262 Hz) could not be
# heard: a laptop speaker plays next to nothing below ~300 Hz and the ear is dull down there.
# All three stay under 1 kHz, below the button blips (1-2 kHz).
SPIN_SOUNDS = {"TRAM": (330, 0.34), "VUA": (440, 0.28), "SANG": (587, 0.25)}
DEFAULT_SPIN_SOUND = "SANG"  # the user's pick (2026-10-30); the other two stay selectable
SPIN_STEPS = 9


def spin_notes(lowest: float) -> tuple[int, ...]:
    return tuple(round(lowest * 2 ** (k / 12)) for k in range(SPIN_STEPS))


def synth_spin(freq: float) -> np.ndarray:
    """One step of the spin dial: a short, round 'tok' (a sine and a quiet octave)."""
    t = _t(0.07)
    x = np.sin(2 * np.pi * freq * t) * _decay(t, 0.022)
    x += 0.25 * np.sin(2 * np.pi * 2 * freq * t) * _decay(t, 0.012)
    return _to_int16(x * np.minimum(1.0, t / 0.004), gain=0.6)


# --- the opening screen: a chip tune, one sound for each thing that appears ---------------------
# The user listened to two sets (neon sign / 8-bit arcade) and chose the 8-bit one (2026-10-31).
SPLASH_SCALE = (
    0,
    2,
    4,
    7,
    9,
    12,
    14,
    16,
)  # the eight letters of the title climb a pentatonic scale
SPLASH_LINE_NOTES = (392, 440, 494, 587)  # the four tools, a note each
# playback volume of each kind (the clips are all made equally loud)
SPLASH_VOLUMES = {
    "on": 0.95, "letter": 0.88, "sub": 0.64, "line": 0.72, "tick": 0.29, "ok": 0.8,
    "ready": 0.88, "off": 0.95,
}  # fmt: skip


def synth_splash_on() -> np.ndarray:
    """The tube is switched on: a rising sweep and a puff of noise."""
    t = _t(0.35)
    sweep = np.sin(2 * np.pi * np.cumsum(120 + 1800 * (t / 0.35) ** 2) / SAMPLE_RATE)
    return _to_int16(sweep * _decay(t, 0.2) + 0.3 * _noise(t.size) * _decay(t, 0.03), gain=0.8)


def synth_splash_letter(i: int) -> np.ndarray:
    """A letter of the title lights up: one square note, each higher than the one before."""
    return _to_int16(_square(523 * 2 ** (SPLASH_SCALE[i] / 12), 0.11, 0.05), gain=0.8)


def synth_splash_subtitle() -> np.ndarray:
    """The line under the title: two coin notes."""
    return _to_int16(_notes([988, 1319], 0.06, 0.05, tail=0.15), gain=0.7)


def synth_splash_line(i: int) -> np.ndarray:
    """A line of the tools starts to be typed: two chip notes, a different pitch for each."""
    f = SPLASH_LINE_NOTES[i]
    return _to_int16(_notes([f, f * 1.5], 0.05, 0.04), gain=0.7)


def synth_splash_tick() -> np.ndarray:
    """One typed character."""
    return _to_int16(_square(1900, 0.012, 0.004), gain=0.5)


def synth_splash_ok() -> np.ndarray:
    """A line is done: a coin."""
    return _to_int16(_notes([1319, 1760], 0.05, 0.07, tail=0.2), gain=0.8)


def synth_splash_ready() -> np.ndarray:
    """Everything is ready: a short climb of five notes."""
    return _to_int16(_notes([523, 659, 784, 1047, 1319], 0.07, 0.08, tail=0.3), gain=0.85)


def synth_splash_off() -> np.ndarray:
    """The tube is switched off: the notes fall away."""
    return _to_int16(_notes([880, 660, 440, 330, 220, 110], 0.04, 0.04, tail=0.1), gain=0.8)


def synth_menu_sweep() -> np.ndarray:
    """The beam of light that draws the menu, from the top of the screen to the bottom: a chip
    tone that climbs from 150 Hz to 2.4 kHz in steps, in as long as the beam takes."""
    t = _t(MENU_INTRO_S)
    steps = np.floor(np.log2(1 + 15 * t / MENU_INTRO_S) * 6) / 6  # climbs in sixths of an octave
    freq = 150 * 2 ** (steps * 4 / np.log2(16))
    phase = 2 * np.pi * np.cumsum(freq) / SAMPLE_RATE
    wave = np.sin(phase) + np.sin(3 * phase) / 3
    return _to_int16(
        wave * np.minimum(1.0, t / 0.03) * np.minimum(1.0, (MENU_INTRO_S - t) / 0.1), gain=0.5
    )


def volume_for_speed(speed: float) -> float:
    return float(min(1.0, 0.12 + 0.88 * (max(speed, 0.0) / SFX_REF_SPEED) ** 0.7))


class Audio:
    def __init__(self) -> None:
        self.available = False
        self.muted = False
        self.volume = 1.0  # the player's volume (0..1), from the settings
        self.music_volume = 0.5  # and the music's, on its own
        self._sounds: dict[str, pg.mixer.Sound] = {}
        self._built: dict[str, np.ndarray] = {}  # tracks the thread has finished, not yet sounds
        self._tracks: dict[str, pg.mixer.Sound] = {}
        self._level = dict.fromkeys(music.TRACKS, 0.0)  # how far each track has faded in (0..1)
        self._duck = 1.0  # 1 normal, MUSIC_DUCK while the result card is up
        # the spin dial's sound under test (see SPIN_SOUNDS); the one chosen stays, the rest go
        name = os.environ.get("NEONPOOL_SPIN_SOUND", "")
        lowest, self._spin_volume = SPIN_SOUNDS.get(name, SPIN_SOUNDS[DEFAULT_SPIN_SOUND])
        self.spin_notes = spin_notes(lowest)
        self._music_thread: threading.Thread | None = None
        try:
            if not pg.mixer.get_init():
                pg.mixer.init(frequency=SAMPLE_RATE, size=-16, channels=1, buffer=512)
            pg.mixer.set_num_channels(16)
            pg.mixer.set_reserved(MUSIC_CHANNELS)  # the music's channels: effects never take them
            for name, fn in (
                ("ball", synth_ball_hit),
                ("cushion", synth_cushion),
                ("pocket", synth_pocket),
                ("cue", synth_cue_hit),
                ("pick", synth_ball_pick),
                ("put", synth_ball_put),
                ("click", synth_click),
                ("blip", synth_blip),
                ("confirm", synth_confirm),
                ("win", synth_win),
                ("lose", synth_lose),
                ("foul", synth_foul),
                ("notice", synth_notice),
                ("warn", synth_warn),
                ("warn_last", synth_warn_last),
                ("coin_up", synth_coin_up),
                ("coin_land", synth_coin_land),
                ("splash_on", synth_splash_on),
                ("splash_sub", synth_splash_subtitle),
                ("splash_tick", synth_splash_tick),
                ("splash_ok", synth_splash_ok),
                ("splash_ready", synth_splash_ready),
                ("splash_off", synth_splash_off),
                ("menu_sweep", synth_menu_sweep),
                *((f"splash_letter{i}", lambda i=i: synth_splash_letter(i)) for i in range(8)),
                *((f"splash_line{i}", lambda i=i: synth_splash_line(i)) for i in range(4)),
                ("ting_win", lambda: synth_ting(1319, 1976)),  # bright: E6 and B6
                ("ting_lose", lambda: synth_ting(440, 659)),  # lower: A4 and E5
                *((f"tick{i}", lambda f=f: synth_tick(f)) for i, f in enumerate(TICK_NOTES)),
                *((f"spin{i}", lambda f=f: synth_spin(f)) for i, f in enumerate(self.spin_notes)),
            ):
                self._sounds[name] = self._make(fn())
            self.available = True
        except pg.error as exc:
            log.warning("no audio device, running silent: %s", exc)

    @staticmethod
    def _make(samples: np.ndarray) -> pg.mixer.Sound:
        channels = pg.mixer.get_init()[2]
        data = samples if channels == 1 else np.repeat(samples[:, None], channels, axis=1)
        return pg.sndarray.make_sound(np.ascontiguousarray(data))

    # --- music: one loop per place (the menu, the table), faded in and out ----------------------
    def _build_music(self) -> None:
        """Make every track (a thread: numpy only, the mixer is touched on the main thread)."""
        for name, style in music.TRACKS.items():
            self._built[name] = music.render(style)

    def prepare_music(self) -> bool:
        """Make ONE track that is not made yet, here and now (the loading screen does this, so no
        thread is working against the first frames of the game). Returns whether it made one."""
        if not self.available or os.environ.get("NEONPOOL_NO_MUSIC"):
            return False
        for name, style in music.TRACKS.items():
            if name not in self._tracks:
                self._tracks[name] = self._make(music.render(style))
                return True
        return False

    def music_level(self, name: str) -> float:
        return self._level[name]

    def update_music(self, dt: float, track: str | None, duck: bool = False) -> None:
        """Every frame: fade towards `track` ("menu", "play" or None); `duck` drops the music
        under the result jingle. The first call starts making the tracks in the background."""
        if not self.available:
            return
        missing = any(name not in self._tracks for name in music.TRACKS)
        if self._music_thread is None and missing and not os.environ.get("NEONPOOL_NO_MUSIC"):
            self._music_thread = threading.Thread(target=self._build_music, daemon=True)
            self._music_thread.start()
        for name in list(self._built):
            self._tracks[name] = self._make(self._built.pop(name))
        goal = MUSIC_DUCK if duck else 1.0
        self._duck += (goal - self._duck) * min(1.0, dt / MUSIC_DUCK_S)
        for i, name in enumerate(music.TRACKS):
            sound = self._tracks.get(name)
            if sound is None:
                continue
            level, target = self._level[name], 1.0 if name == track else 0.0
            step = dt / MUSIC_FADE_S
            level = min(target, level + step) if target > level else max(target, level - step)
            self._level[name] = level
            channel = pg.mixer.Channel(i)
            if level <= 0.0:
                if channel.get_busy():
                    channel.stop()
                continue
            if not channel.get_busy():
                channel.play(sound, loops=-1)
            gain = level * self._duck * self.music_volume * MUSIC_GAIN
            channel.set_volume(0.0 if self.muted else gain)

    def toggle_mute(self) -> bool:
        self.muted = not self.muted
        return self.muted

    def _play(self, name: str, volume: float) -> bool:
        if not self.available or self.muted or self.volume <= 0.0:
            return False
        channel = self._sounds[name].play()
        if channel is None:  # all channels busy: drop this sound
            return False
        channel.set_volume(max(0.0, min(1.0, volume * self.volume)))
        return True

    def play_click(self) -> None:
        """A button was pressed."""
        self._play("confirm", 0.45)

    def play_hover(self) -> None:
        """The pointer (or the arrow keys) moved to another button."""
        self._play("blip", 0.3)

    def play_win(self) -> None:
        self._play("win", 0.55)

    def play_lose(self) -> None:
        self._play("lose", 0.55)

    def play_foul(self) -> None:
        self._play("foul", 0.5)

    def play_notice(self) -> None:
        self._play("notice", 0.45)

    def play_clock_warn(self, seconds_left: int) -> None:
        """A second of the last ten of your clock; the last three are quicker and higher."""
        self._play("warn_last" if seconds_left <= 3 else "warn", 0.5)

    def play_coin_up(self) -> None:
        """The coin of the toss is thrown."""
        self._play("coin_up", 0.5)

    def play_coin_land(self) -> None:
        """The coin of the toss has landed."""
        self._play("coin_land", 0.55)

    def play_spin(self, level: float) -> None:
        """The spin dial moved a step; `level` -1 (low) .. +1 (high) picks the note."""
        i = round((min(1.0, max(-1.0, level)) + 1) / 2 * (SPIN_STEPS - 1))
        self._play(f"spin{i}", self._spin_volume)

    def play_tally_tick(self, pitch: float) -> None:
        """A counting number stepped; `pitch` 0..1 is how far up the scale it has climbed."""
        i = round(min(1.0, max(0.0, pitch)) * (len(TICK_NOTES) - 1))
        self._play(f"tick{i}", 0.4)

    def play_tally_ting(self, won: bool, big: bool) -> None:
        """A number stopped: bright after a win, lower after a loss; the score's is loudest."""
        self._play("ting_win" if won else "ting_lose", 0.55 if big else 0.32)

    def play_splash(self, kind: str, i: int = 0) -> None:
        """A sound of the opening screen: kind "on", "letter" (i: which), "sub", "line" (i: which
        tool), "tick", "ok", "ready" or "off"."""
        name = f"splash_{kind}{i}" if kind in ("letter", "line") else f"splash_{kind}"
        self._play(name, SPLASH_VOLUMES[kind])

    def play_menu_sweep(self) -> None:
        """The beam draws the menu, after the opening screen."""
        self._play("menu_sweep", 0.5)

    def play_shot(self, power: float) -> None:
        self._play("cue", 0.25 + 0.75 * power)

    def play_cue_pick(self) -> None:
        """The cue ball in hand was picked up."""
        self._play("pick", 0.45)

    def play_cue_put(self) -> None:
        """The cue ball in hand was put down on the table."""
        self._play("put", 0.55)

    def on_events(self, events: Iterable[Event]) -> int:
        """Play the loudest few impacts of one frame; returns how many sounds were started."""
        hits = sorted(
            (
                e
                for e in events
                if isinstance(e, BallHitBall | BallHitCushion) and e.speed >= SFX_MIN_SPEED
            ),
            key=lambda e: e.speed,
            reverse=True,
        )
        budget = SFX_MAX_PER_FRAME
        started = 0
        for e in events:
            if isinstance(e, BallPocketed) and budget > 0:
                started += self._play("pocket", 0.8)
                budget -= 1
        for e in hits[:budget]:
            name = "ball" if isinstance(e, BallHitBall) else "cushion"
            started += self._play(name, volume_for_speed(e.speed))
        return started
