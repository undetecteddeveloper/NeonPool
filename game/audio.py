"""Sound effects synthesised in code (no asset files). No device => silent, game still runs."""

from __future__ import annotations

import logging
from collections.abc import Iterable

import numpy as np
import pygame as pg

from game.config import SAMPLE_RATE, SFX_MAX_PER_FRAME, SFX_MIN_SPEED, SFX_REF_SPEED
from game.physics import BallHitBall, BallHitCushion, BallPocketed, Event

log = logging.getLogger("mathofpool")
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
        self._play("click", 0.5)

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
