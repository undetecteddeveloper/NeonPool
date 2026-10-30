"""Background music, made in code (no sound files, so no licences). No pygame here.

A `Style` is a named bundle of "what the music is": tempo, chords and how loud each layer is
(pad, arpeggio, bass, kick, hi-hat, bells). `render(style)` plays it into one seamless loop:
whatever is still ringing at the end of the last bar wraps round to the start, so the loop has no
click and no gap. The same style always gives the same samples.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from game.config import SAMPLE_RATE

MINOR, MAJOR = (0, 3, 7, 12), (0, 4, 7, 12)  # chord tones, in semitones above the root
TARGET_RMS = 0.14  # every loop is brought to this loudness (so styles can be swapped freely)
PAD_ATTACK_S, PAD_RELEASE_S = 0.55, 0.9


@dataclass(frozen=True)
class Style:
    name: str
    bpm: float
    chords: tuple[tuple[int, tuple[int, ...]], ...]  # (root as a MIDI note, chord tones) each
    bars_per_chord: int = 2
    pad: float = 0.0  # how loud each layer is, 0 = absent
    arp: float = 0.0
    arp_per_beat: int = 2  # arpeggio notes per beat
    arp_shape: tuple[int, ...] = (0, 1, 2, 1)  # chord-tone numbers the arpeggio walks through
    bass: float = 0.0
    bass_per_beat: int = 1
    kick: float = 0.0
    kick_beats: tuple[int, ...] = (0, 2)  # beats of each bar that get a kick
    hat: float = 0.0
    bell: float = 0.0
    bell_every: int = 3  # a bell every this many beats
    echo: float = 0.3  # how much of the arpeggio and bells comes back, a dotted eighth later
    seed: int = 7

    @property
    def beat_s(self) -> float:
        return 60.0 / self.bpm

    @property
    def bars(self) -> int:
        return len(self.chords) * self.bars_per_chord

    @property
    def loop_s(self) -> float:
        return self.bars * 4 * self.beat_s


# --- the named styles: the menu's two, and the table's two (docs/GAME_DESIGN.md "round 10") -----
MENU_DUSK = Style(  # slow and dreamy: long pads, a soft arpeggio, a few bells
    "menu_dusk", 84, ((57, MINOR), (53, MAJOR), (60, MAJOR), (55, MAJOR)),
    pad=0.9, arp=0.5, arp_shape=(0, 1, 2, 3, 2, 1), bass=0.55, bell=0.22, bell_every=5, echo=0.38,
)  # fmt: skip
MENU_CITY = Style(  # a little drive: a soft kick, a ticking hat, a pulsing bass
    "menu_city", 100, ((62, MINOR), (58, MAJOR), (65, MAJOR), (60, MAJOR)),
    pad=0.55, arp=0.45, arp_shape=(0, 2, 1, 3), bass=0.5, bass_per_beat=2, kick=0.45, hat=0.2,
    echo=0.3, seed=11,
)  # fmt: skip
PLAY_FOCUS = Style(  # calm and spare, no drums: it must not pull the eye off the aim
    "play_focus", 68, ((52, MINOR), (48, MAJOR), (55, MAJOR), (50, MAJOR)),
    pad=0.8, bass=0.3, bell=0.55, bell_every=3, echo=0.5, seed=5,
)  # fmt: skip
PLAY_PULSE = Style(  # a light, steady pulse under a quiet arpeggio
    "play_pulse", 92, ((57, MINOR), (55, MAJOR), (53, MAJOR), (52, MAJOR)),
    pad=0.5, arp=0.3, arp_shape=(0, 1, 2, 1), bass=0.42, bass_per_beat=2, kick=0.28,
    kick_beats=(0,), hat=0.14, echo=0.3, seed=3,
)  # fmt: skip
STYLES = {s.name: s for s in (MENU_DUSK, MENU_CITY, PLAY_FOCUS, PLAY_PULSE)}
TRACKS = {"menu": MENU_DUSK, "play": PLAY_FOCUS}  # what the game plays now


# --- voices (float32, about one unit loud; the style's level scales them) ---------------------
def _hz(midi: float) -> float:
    return 440.0 * 2.0 ** ((midi - 69.0) / 12.0)


def _time(seconds: float) -> np.ndarray:
    return np.arange(int(SAMPLE_RATE * seconds), dtype=np.float32) / SAMPLE_RATE


def _pad(hz: float, seconds: float) -> np.ndarray:
    """A warm held tone: two slightly detuned copies (a chorus) with three harmonics."""
    t = _time(seconds)
    sig = np.zeros_like(t)
    for cents in (-5.0, 5.0):
        f = hz * 2.0 ** (cents / 1200.0)
        for h, a in ((1, 1.0), (2, 0.45), (3, 0.22)):
            sig += a * np.sin(2 * np.pi * f * h * t)
    env = np.minimum(1.0, t / PAD_ATTACK_S) * np.clip((seconds - t) / PAD_RELEASE_S, 0.0, 1.0)
    return sig * env / 3.34


def _pluck(hz: float, seconds: float) -> np.ndarray:
    """A round, soft square-ish blip that dies away (the arcade tone of audio.py, but slower)."""
    t = _time(seconds)
    sig = sum(np.sin(2 * np.pi * hz * h * t) / h for h in (1, 3, 5)) / 1.5
    return sig * np.exp(-t / 0.16) * np.minimum(1.0, t / 0.004)


def _bass(hz: float, seconds: float) -> np.ndarray:
    t = _time(seconds)
    sig = np.sin(2 * np.pi * hz * t) + 0.45 * np.sin(2 * np.pi * 2 * hz * t)
    env = np.minimum(1.0, t / 0.012) * np.clip((seconds - t) / 0.05, 0.0, 1.0)
    return sig * env / 1.45 * np.exp(-t / (seconds * 1.4))


def _kick() -> np.ndarray:
    t = _time(0.32)
    phase = 2 * np.pi * np.cumsum(46.0 + 96.0 * np.exp(-t / 0.035)) / SAMPLE_RATE
    return (np.sin(phase) * np.exp(-t / 0.11)).astype(np.float32)


def _hat(rng: np.random.Generator) -> np.ndarray:
    t = _time(0.06)
    noise = np.diff(rng.uniform(-1.0, 1.0, t.size + 1)).astype(np.float32)  # brighter than noise
    return noise * np.exp(-t / 0.014) * 0.5


def _bell(hz: float) -> np.ndarray:
    """A glassy bell: partials that are not whole multiples, each dying at its own speed."""
    t = _time(1.8)
    sig = np.zeros_like(t)
    for ratio, a, tau in ((1.0, 1.0, 0.7), (2.76, 0.4, 0.35), (5.4, 0.18, 0.16)):
        sig += a * np.sin(2 * np.pi * hz * ratio * t) * np.exp(-t / tau)
    return sig * np.minimum(1.0, t / 0.003) / 1.4


def _add(buf: np.ndarray, start: int, sig: np.ndarray, level: float) -> None:
    """Mix `sig` into the loop at `start`; what runs past the end wraps round to the beginning."""
    n = buf.size
    start %= n
    first = min(sig.size, n - start)
    buf[start : start + first] += level * sig[:first]
    rest = sig[first:]
    while rest.size:  # a sound longer than the loop keeps wrapping
        part = min(rest.size, n)
        buf[:part] += level * rest[:part]
        rest = rest[part:]


def render(style: Style) -> np.ndarray:
    """The style as one loop of int16 mono samples at SAMPLE_RATE."""
    rng = np.random.default_rng(style.seed)
    beat = style.beat_s
    n = round(style.loop_s * SAMPLE_RATE)
    body = np.zeros(n, np.float32)  # pad, bass and drums
    wet = np.zeros(n, np.float32)  # arpeggio and bells: they get the echo

    def at(beats: float) -> int:  # a beat number -> a sample number
        return round(beats * beat * SAMPLE_RATE)

    chord_beats = style.bars_per_chord * 4

    for c, (root, tones) in enumerate(style.chords):
        start = c * chord_beats
        if style.pad:
            for tone in tones[:3]:
                length = chord_beats * beat + PAD_RELEASE_S
                _add(body, at(start), _pad(_hz(root + tone), length), style.pad)
        if style.bass:
            per = style.bass_per_beat
            for k in range(chord_beats * per):
                accent = 1.0 if k % (4 * per) == 0 else 0.7
                _add(body, at(start + k / per), _bass(_hz(root - 12), beat / per * 0.95),
                     style.bass * accent)  # fmt: skip
        if style.arp:
            per = style.arp_per_beat
            for k in range(chord_beats * per):
                tone = tones[style.arp_shape[k % len(style.arp_shape)] % len(tones)]
                accent = 1.0 if k % per == 0 else 0.7
                _add(wet, at(start + k / per), _pluck(_hz(root + 12 + tone), beat * 1.6),
                     style.arp * accent)  # fmt: skip
        if style.bell:
            for k in range(0, chord_beats, style.bell_every):
                tone = tones[int(rng.integers(0, len(tones)))]
                _add(wet, at(start + k), _bell(_hz(root + 24 + tone)), style.bell)

    for bar in range(style.bars):
        if style.kick:
            for b in style.kick_beats:
                _add(body, at(bar * 4 + b), _kick(), style.kick)
        if style.hat:
            for b in range(4):  # the off-beats
                _add(body, at(bar * 4 + b + 0.5), _hat(rng), style.hat)

    delay = at(0.75)  # a dotted eighth: the echo lands between the beats
    echoed = wet + style.echo * np.roll(wet, delay) + style.echo**2 * np.roll(wet, 2 * delay)
    mix = body + echoed
    mix *= TARGET_RMS / max(float(np.sqrt(np.mean(mix * mix))), 1e-6)
    return (np.tanh(mix) * 0.95 * 32767).astype(np.int16)  # tanh: a soft ceiling, never a click
