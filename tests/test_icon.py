"""The game's icon: the files made by tools/make_icon.py, and the window using it."""

import struct

import pygame as pg
import pytest

from game import app as app_module
from tools import make_icon

pytestmark = pytest.mark.filterwarnings("ignore")


def test_the_icon_files_exist_and_the_png_is_a_256_px_picture_with_round_corners():
    pg.init()
    img = pg.image.load(str(app_module.ICON_FILE))
    assert img.get_size() == (256, 256)
    assert img.get_at((0, 0)).a == 0 and img.get_at((255, 255)).a == 0  # transparent corners
    assert img.get_at((128, 20)).a == 255  # opaque inside


def test_the_ico_holds_every_size_as_a_png_and_the_entries_point_at_real_pictures():
    data = (app_module.ICON_FILE.parent / "icon.ico").read_bytes()
    reserved, kind, count = struct.unpack_from("<HHH", data, 0)
    assert (reserved, kind, count) == (0, 1, len(make_icon.SIZES))
    sizes = []
    for i in range(count):
        w, h, _, _, planes, bits, length, offset = struct.unpack_from("<BBBBHHII", data, 6 + 16 * i)
        sizes.append(w or 256)
        assert (planes, bits) == (1, 32) and w == h
        assert data[offset : offset + 8] == b"\x89PNG\r\n\x1a\n"  # a PNG inside
        assert offset + length <= len(data)
    assert sizes == list(make_icon.SIZES)


def test_the_icon_is_drawn_the_same_every_time_from_the_code():
    pg.init()
    a, b = make_icon.draw_big(), make_icon.draw_big()
    assert pg.image.tobytes(a, "RGBA") == pg.image.tobytes(b, "RGBA")


def test_the_ball_is_in_the_middle_with_a_dark_edge_and_light_rings_round_it():
    pg.init()
    big = make_icon.draw_big()
    c = make_icon.CENTRE
    assert min(big.get_at((c, c))[:3]) > 200  # the white ball
    edge = big.get_at((c + make_icon.BALL_R + 12, c))[:3]
    assert max(edge) < 40  # its edge is dark ink, not cyan
    rings = [
        big.get_at((c + r, c))[:3]
        for r in range(make_icon.RING_R0 - 20, make_icon.RING_R0 + 190, 3)
    ]
    assert any(p[0] > 200 or p[2] > 200 for p in rings)  # lit pink / cyan light round it


def test_the_window_icon_is_set_and_a_missing_file_does_not_stop_the_game(monkeypatch, tmp_path):
    pg.init()
    pg.display.set_mode((50, 50))
    app_module._set_window_icon()  # the real file
    monkeypatch.setattr(app_module, "ICON_FILE", tmp_path / "nope.png")
    app_module._set_window_icon()  # no file: only a warning
