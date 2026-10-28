"""Shot: the ONLY way anything acts on the cue ball (drag today, formulas later)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Shot:
    angle: float  # radians; direction (cos, sin) in table coordinates (y points down)
    power: float  # 0..1 of the feel set's v_max
    spin: float = 0.0  # -1 (draw) .. +1 (follow); ignored until spin is implemented

    def __post_init__(self) -> None:
        if not 0.0 <= self.power <= 1.0:
            raise ValueError(f"power must be in [0, 1], got {self.power}")
        if not -1.0 <= self.spin <= 1.0:
            raise ValueError(f"spin must be in [-1, 1], got {self.spin}")
