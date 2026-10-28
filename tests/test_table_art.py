"""Look of the table, balls and pull bar (feedback 2026-10-28: no checkers, shadows straight down,
square pull bar, table after the reference picture)."""

import math
from types import SimpleNamespace

import pygame as pg
import pytest

from game.config import POCKETS, PX_PER_M
from game.physics import Contact
from game.render import draw, table
from game.render.layout import FIELD_H, FIELD_W, FIELD_X, FIELD_Y, to_px
from game.render.view import View

V = View(1.0)


@pytest.fixture(scope="module")
def surf() -> pg.Surface:
    return table.build_table(V)


def _px(surf: pg.Surface, p: tuple[float, float]) -> tuple[int, int, int]:
    return tuple(surf.get_at((round(p[0]), round(p[1]))))[:3]


def test_table_has_the_canvas_size(surf):
    assert surf.get_size() == (1280, 720)
    assert table.build_table(View(0.82)).get_size() == View(0.82).size


def test_cloth_is_a_smooth_gradient_not_checkers(surf):
    sq = FIELD_W / 20  # the old checker squares
    y = FIELD_Y + FIELD_H * 0.37
    for ix in range(1, 20):
        x = FIELD_X + ix * sq
        left, right = _px(surf, (x - 2, y)), _px(surf, (x + 2, y))
        assert max(abs(a - b) for a, b in zip(left, right, strict=True)) <= 3, ix


def test_cloth_is_brighter_in_the_middle_than_near_the_corners(surf):
    middle = _px(surf, (FIELD_X + FIELD_W / 2, FIELD_Y + FIELD_H / 2))
    corner = _px(surf, (FIELD_X + 40, FIELD_Y + 40))
    assert sum(middle) > sum(corner) + 60
    assert middle[1] > middle[0] and middle[1] > middle[2]  # still green


def test_plates_stay_off_the_cloth_next_to_a_pocket(surf):
    r, g, b = _px(surf, to_px(0.13, 0.13))  # just inside the field, beside the corner pocket
    assert g > r + 20 and g > b + 20


def test_pockets_are_black_where_the_physics_has_them(surf):
    for px, py, _ in POCKETS:
        assert sum(_px(surf, to_px(px, py))) < 60


def test_wood_is_brown_with_a_bright_middle():
    edge, mid = table.wood_color(0.5), table.wood_color(table.WOOD_PX * 0.55)
    assert sum(mid) > sum(edge)
    assert mid[0] > mid[1] > mid[2]  # brown: red > green > blue


def test_diamonds_clear_the_plates_and_pockets():
    pts = table.sight_points()
    assert len(pts) == 18  # 6 on each long rail, 3 on each short rail
    for x, y in pts:
        for (px, py, pw, ph), _ in table.plate_rects():
            assert (
                not pg.Rect(px, py, pw, ph)
                .inflate(2 * table.SIGHT_R, 2 * table.SIGHT_R)
                .collidepoint(x, y)
            )
        for mx, my, mr in POCKETS:
            assert math.dist((x, y), to_px(mx, my)) > mr * PX_PER_M + table.SIGHT_R


def test_grain_is_repeatable():
    assert [table._hash(i, 3) for i in range(5)] == [table._hash(i, 3) for i in range(5)]
    assert all(0.0 <= table._hash(i, 7) < 1.0 for i in range(50))


# --- ball shadow ---------------------------------------------------------------------------
def test_ball_shadow_falls_straight_down():
    grey = 120
    canvas = pg.Surface(V.size)
    canvas.fill((grey, grey, grey))
    ball = SimpleNamespace(in_play=True, x=1.27, y=0.635, number=0)
    draw.draw_balls(canvas, V, [ball], draw.BallSprites(V))
    cx, cy = to_px(ball.x, ball.y)
    rim = draw.RIM
    below = canvas.get_at((round(cx), round(cy + rim + 1.5)))[0]
    right = canvas.get_at((round(cx + rim + 1.5), round(cy)))[0]
    left = canvas.get_at((round(cx - rim - 1.5), round(cy)))[0]
    above = canvas.get_at((round(cx), round(cy - rim - 1.5)))[0]
    assert below < grey - 10  # the shadow shows under the ball
    assert right == left == above == grey  # and nowhere to the sides or on top
    a = canvas.get_at((round(cx - 4), round(cy + rim + 1.5)))[0]
    b = canvas.get_at((round(cx + 4), round(cy + rim + 1.5)))[0]
    assert abs(a - b) <= 2  # symmetric: no sideways tilt


# --- pull bar --------------------------------------------------------------------------------
def test_bar_polygon_is_a_rectangle():
    d = (0.6, 0.8)
    pts = draw._bar_polygon((10.0, 20.0), d, 50.0, 4.0)
    sides = [(pts[(i + 1) % 4][0] - pts[i][0], pts[(i + 1) % 4][1] - pts[i][1]) for i in range(4)]
    for i in range(4):
        a, b = sides[i], sides[(i + 1) % 4]
        assert abs(a[0] * b[0] + a[1] * b[1]) < 1e-9  # right angles
    lengths = sorted(math.hypot(*s) for s in sides)
    assert lengths == pytest.approx([8.0, 8.0, 50.0, 50.0])  # constant width, no taper


def test_pull_bar_ends_are_square_not_round():
    canvas = pg.Surface(V.size)
    canvas.fill((255, 255, 255))
    cue = SimpleNamespace(x=1.27, y=0.635)
    far = (cue.x + 0.5, cue.y)
    contact = Contact("cushion", 0.5, far)
    draw.draw_aim(canvas, V, cue, contact, (1.0, 0.0), 100.0, 0.5)
    cx, cy = to_px(cue.x, cue.y)
    end_x = cx - draw.RIM - 3 - 100 - draw.BAR_EDGE  # outer face of the far end
    reach = draw.BAR_HALF_W + draw.BAR_EDGE
    for sign in (-1, 1):  # both far corners are filled: a round tip would leave them white
        corner = canvas.get_at((round(end_x + 1.5), round(cy + sign * (reach - 1.5))))
        assert sum(corner[:3]) < 150
