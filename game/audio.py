"""Sound effects synthesised in code (no asset files). No device => silent, game still runs."""

from __future__ import annotations

import logging
from collections.abc import Iterable

import numpy as np
import pygame as pg

from game.config import SAMPLE_RATE, SFX_MAX_PER_FRAME, SFX_MIN_SPEED, SFX_REF_SPEED
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


def volume_for_speed(speed: float) -> float:
    return float(min(1.0, 0.12 + 0.88 * (max(speed, 0.0) / SFX_REF_SPEED) ** 0.7))


class Audio:
    def __init__(self) -> None:
        self.available = False
        self.muted = False
        self._sounds: dict[str, pg.mixer.Sound] = {}
        try:
            if not pg.mixer.get_init():
                pg.mixer.init(frequency=SAMPLE_RATE, size=-16, channels=1, buffer=512)
            pg.mixer.set_num_channels(16)
            for name, fn in (
                ("ball", synth_ball_hit),
                ("cushion", synth_cushion),
                ("pocket", synth_pocket),
                ("cue", synth_cue_hit),
                ("click", synth_click),
                ("blip", synth_blip),
                ("confirm", synth_confirm),
                ("win", synth_win),
                ("lose", synth_lose),
                ("foul", synth_foul),
                ("notice", synth_notice),
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

    def toggle_mute(self) -> bool:
        self.muted = not self.muted
        return self.muted

    def _play(self, name: str, volume: float) -> bool:
        if not self.available or self.muted:
            return False
        channel = self._sounds[name].play()
        if channel is None:  # all channels busy: drop this sound
            return False
        channel.set_volume(max(0.0, min(1.0, volume)))
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

    def play_shot(self, power: float) -> None:
        self._play("cue", 0.25 + 0.75 * power)

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
