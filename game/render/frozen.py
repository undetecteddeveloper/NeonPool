"""The scene behind a panel, kept as a picture.

A panel that opens over the menu or the table leaves the scene under a nearly black veil. Drawing
that scene and the veil again every frame costs more than the panel itself (6 ms of blending
alone at 2560x1440), and under the veil nobody sees it stand still. So: the first frame of the
opening is kept, later frames paste it, and once the panel is fully open the dark picture (with the
panel's unmoving parts painted on it) is baked once and pasted whole.
"""

from __future__ import annotations

from collections.abc import Callable

import pygame as pg

from game.render.draw import veil


class FrozenScene:
    def __init__(self) -> None:
        self.snap: pg.Surface | None = None  # the scene, as it was when the panel opened
        self.base: pg.Surface | None = None  # ... darkened, with the panel's unmoving parts

    def clear(self) -> None:
        self.snap = self.base = None

    def covers(self, size: tuple[int, int]) -> bool:
        """The scene need not be drawn: its picture is held for this canvas size."""
        return self.snap is not None and self.snap.get_size() == size

    def under(self, canvas: pg.Surface) -> None:
        """While the panel is opening: the first call keeps what is on the canvas (the scene, just
        drawn); later calls paste it back."""
        if not self.covers(canvas.get_size()):
            self.snap, self.base = canvas.copy(), None
        else:
            canvas.blit(self.snap, (0, 0))

    def paste_baked(
        self, canvas: pg.Surface, alpha: int, paint_static: Callable[[pg.Surface], None]
    ) -> None:
        """The panel is fully open: paste the dark picture with `paint_static` already painted on
        it (made once)."""
        size = canvas.get_size()
        if not self.covers(size):
            self.snap, self.base = canvas.copy(), None
        if self.base is None:
            base = self.snap.copy()
            base.blit(veil(size, alpha), (0, 0))
            paint_static(base)
            self.base = base
        canvas.blit(self.base, (0, 0))
