"""The look of an old tube: the bulge of the glass and the colour fringe (render/tube.py)."""

import pygame as pg
import pytest

from game.render import tube


@pytest.fixture(autouse=True)
def pygame_up():
    pg.init()
    pg.display.set_mode((10, 10))
    yield
    pg.quit()


def grid(size=(400, 240)):
    """A picture with a lit vertical line every 40 px and a lit horizontal one every 40 px."""
    s = pg.Surface(size)
    s.fill((20, 10, 40))
    for x in range(0, size[0], 40):
        pg.draw.line(s, (255, 255, 255), (x, 0), (x, size[1]))
    for y in range(0, size[1], 40):
        pg.draw.line(s, (255, 255, 255), (0, y), (size[0], y))
    return s


def lit_span(surface, y):
    """(leftmost, rightmost) x of anything not black on row y."""
    xs = [x for x in range(surface.get_width()) if sum(surface.get_at((x, y))[:3]) > 6]
    return (xs[0], xs[-1]) if xs else None


def test_the_middle_rows_fill_the_screen_and_the_top_and_bottom_rows_are_narrower():
    src, dst = grid(), pg.Surface((400, 240))
    tube.Bulge((400, 240)).apply(src, dst)
    mid, high, top = lit_span(dst, 120), lit_span(dst, 60), lit_span(dst, 8)
    assert mid[0] <= 2 and mid[1] >= 397  # fills the width in the middle
    assert high[0] > mid[0] and top[0] > high[0]  # and the sides bulge outwards
    assert 400 - 1 - top[1] == pytest.approx(top[0], abs=6)  # evenly on both sides


def test_the_corners_are_black_and_the_centre_is_the_picture():
    src, dst = grid(), pg.Surface((400, 240))
    src.fill((90, 120, 200))
    tube.Bulge((400, 240)).apply(src, dst)
    for corner in ((0, 0), (399, 0), (0, 239), (399, 239)):
        assert sum(dst.get_at(corner)[:3]) == 0
    assert dst.get_at((200, 120))[:3] == pytest.approx((90, 120, 200), abs=30)  # (the glare adds)


def test_it_works_at_other_shapes_and_sizes_and_the_stronger_shape_is_narrower_at_the_top():
    soft = tube.Shape(k=0.05, sag=0.015, radius=0.06, glare=14)
    for size in ((1280, 720), (900, 700), (2560, 1440)):
        src, dst = pg.Surface(size), pg.Surface(size)
        src.fill((50, 50, 50))
        tube.Bulge(size).apply(src, dst)
        tube.Bulge(size, soft).apply(src, dst)
    flat, strong = pg.Surface((400, 240)), pg.Surface((400, 240))
    src = pg.Surface((400, 240))
    src.fill((200, 200, 200))
    tube.Bulge((400, 240), soft).apply(src, flat)
    tube.Bulge((400, 240), tube.ARCADE).apply(src, strong)
    assert lit_span(strong, 10)[0] > lit_span(flat, 10)[0]


def test_a_picture_for_another_surface_is_handled_by_remaking_the_pieces():
    bulge = tube.Bulge((400, 240))
    a, b = pg.Surface((400, 240)), pg.Surface((400, 240))
    for dst in (a, b, a):
        bulge.apply(grid(), dst)
    assert lit_span(b, 120) is not None


def test_the_fringe_slips_red_and_blue_apart_and_leaves_green_and_the_edges():
    canvas = pg.Surface((100, 40))
    canvas.fill((0, 0, 0))
    pg.draw.rect(canvas, (255, 255, 255), (40, 10, 20, 20))
    fringe = tube.Fringe((100, 40))
    fringe.apply(canvas, pg.Rect(10, 0, 80, 40), 3)
    inside = canvas.get_at((50, 20))[:3]
    assert inside == (255, 255, 255)
    assert canvas.get_at((42, 20))[:3] == (0, 255, 255)  # red slipped right: no red at the left end
    assert canvas.get_at((58, 20))[:3] == (
        255,
        255,
        0,
    )  # blue slipped left: no blue at the right end
    assert canvas.get_at((41, 20))[:3][1] == 255  # the green did not move
    assert canvas.get_at((10, 20))[:3] == (0, 0, 0) and canvas.get_at((89, 20))[:3] == (0, 0, 0)


def test_the_fringe_of_zero_does_nothing_and_a_box_off_the_canvas_is_clipped():
    canvas = pg.Surface((100, 40))
    canvas.fill((9, 9, 9))
    fringe = tube.Fringe((20, 10))
    fringe.apply(canvas, pg.Rect(0, 0, 50, 20), 0)
    fringe.apply(canvas, pg.Rect(80, 30, 100, 100), 2)  # bigger than its buffers, half outside
    fringe.apply(canvas, pg.Rect(500, 500, 10, 10), 2)
    assert canvas.get_at((5, 5))[:3] == (9, 9, 9)
