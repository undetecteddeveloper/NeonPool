"""The letters of a glowing text, made once and tinted: the same picture as rendering them in the
colour, and a title that changes colour all the time does not pile up a picture for every colour."""

import pygame as pg
import pytest

from game.render import fonts, hud

WORDS = ("NEONPOOL", "Chơi đơn", "ỔỖỠẬ Điểm", "A")
COLOURS = ((0, 0, 0), (255, 255, 255), (1, 2, 3), (190, 60, 200), (77, 77, 77), (254, 254, 254))


@pytest.fixture(autouse=True)
def _pygame():
    pg.init()
    yield
    pg.quit()


@pytest.mark.parametrize("name", ["display", "bold"])
@pytest.mark.parametrize("dev", [14, 116])
@pytest.mark.parametrize("word", WORDS)
def test_a_lit_face_is_the_font_rendered_in_that_colour(word, dev, name):
    for colour in COLOURS:
        want = fonts.face(dev, name).render(word, True, colour)
        got = hud._face_of(word, dev, name, colour)
        assert got.get_size() == want.get_size()
        assert pg.image.tobytes(got, "RGBA") == pg.image.tobytes(want, "RGBA"), colour


def test_a_title_that_changes_colour_does_not_pile_up_pictures():
    for level in range(300):  # as the breathing title goes through its colours
        hud._face_of("NEONPOOL", 116, "display", (level % 256, 40, 255 - level % 256))
    assert len(hud._faces) <= hud.FACE_MAX
