"""Fit the fixed logical canvas into any window, keeping aspect ratio. Pure (no pygame)."""

from __future__ import annotations


def fit(window: tuple[int, int], logical: tuple[int, int]) -> tuple[float, int, int, int, int]:
    """Return (scale, x, y, w, h): where the scaled canvas sits, centred, inside the window."""
    ww, wh = window
    lw, lh = logical
    scale = min(ww / lw, wh / lh)
    w, h = max(1, round(lw * scale)), max(1, round(lh * scale))
    return scale, (ww - w) // 2, (wh - h) // 2, w, h


def window_to_logical(
    pos: tuple[float, float], window: tuple[int, int], logical: tuple[int, int]
) -> tuple[float, float]:
    """Map a window pixel to logical-canvas coordinates (not clamped: may fall in the bars)."""
    scale, x, y, _, _ = fit(window, logical)
    return (pos[0] - x) / scale, (pos[1] - y) / scale
