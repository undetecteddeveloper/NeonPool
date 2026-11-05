"""Two small things the player sees:

- Free play's side panel says "time for the 8" only once every ball has stopped. The rules know it
  the moment the last ball of the group drops, but the other balls are still rolling then.
- The number in a how-to-play marker sits in the middle of its disc: by where its ink is, not
  by the middle of its box (a "1" has its stem on the right, so its box middle looks too far left).
"""

from types import SimpleNamespace

import numpy as np
import pygame as pg
import pytest

from game.render import hud
from game.render import palette as C
from game.render.guide_art import Annot
from game.render.view import View
from game.scenes import help_pictures
from game.scenes.play import PlayScene

DISC_C = 40  # logical px: where the marker is drawn on its test surface
INK_R = 8  # logical px: inside this radius the dark pixels are the digit (the disc is pink)
MAX_OFF = 0.6  # device px the centre of the ink may be off the centre of the disc (a glyph is
# placed on whole pixels, so half a pixel is as close as it gets; a "1" used to be 1.5-2 off)


@pytest.fixture(autouse=True)
def _pygame():
    pg.init()
    pg.display.set_mode((64, 64))
    yield
    pg.quit()


def _scene(monkeypatch) -> tuple[PlayScene, list[bool]]:
    """A Free play scene (as help_pictures builds one) and the `eight_next` of each panel drawn."""
    seen: list[bool] = []
    monkeypatch.setattr(hud, "draw_panel", lambda *a, **kw: seen.append(kw["eight_next"]))
    v = View(1.0)
    scene = PlayScene(SimpleNamespace(view=v, audio=help_pictures._QuietAudio()))
    return scene, seen


def test_eight_is_said_only_when_balls_rest(monkeypatch):
    scene, seen = _scene(monkeypatch)
    v = scene.app.view
    scene.rules.group = "solid"
    scene.rules.pocketed = {1, 2, 3, 4, 5, 6, 7}  # the whole group is down
    assert scene.rules.eight_is_next()

    scene._draw_panel(pg.Surface((1280, 720)), v)
    assert seen[-1] is True  # at rest: say it

    scene.world.balls[0].vx = 1.0  # the cue ball is still rolling
    assert not scene.world.at_rest()
    scene._draw_panel(pg.Surface((1280, 720)), v)
    assert seen[-1] is False  # rolling: keep the group name


@pytest.mark.parametrize("scale", [0.8, 1.0, 1.6, 2.0])
@pytest.mark.parametrize("n", range(1, 10))
def test_marker_digit_is_centred_on_its_ink(n, scale):
    v = View(scale)
    size = round(80 * scale)
    surf = pg.Surface((size, size))
    surf.fill((0, 0, 0))
    Annot(surf, v).step(n, (DISC_C, DISC_C))
    red = pg.surfarray.array3d(surf)[:, :, 0].astype(float)
    ink = np.clip((C.ACCENT[0] - red) / C.ACCENT[0], 0, 1)  # 0 on the pink disc, 1 on the digit
    xs, ys = np.meshgrid(np.arange(size) + 0.5, np.arange(size) + 0.5, indexing="ij")
    ink *= (xs - DISC_C * scale) ** 2 + (ys - DISC_C * scale) ** 2 < (INK_R * scale) ** 2
    mass = (ink * xs).sum() / ink.sum() - DISC_C * scale
    assert abs(mass) <= MAX_OFF, f"{n} @ {scale}: ink centre off by {mass:+.2f} px"
