"""Look of the table, balls and pull bar (feedback 2026-10-28: no checkers, shadows straight down,
square pull bar, table after the reference picture)."""

import math
from types import SimpleNamespace

import pygame as pg
import pytest

from game import config, i18n
from game.app import App
from game.config import POCKETS, PX_PER_M
from game.physics import Contact
from game.render import draw, hud, table
from game.render.layout import (
    FIELD_H,
    FIELD_W,
    FIELD_X,
    FIELD_Y,
    OUTER_H,
    OUTER_W,
    OUTER_X,
    OUTER_Y,
    to_px,
)
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


# --- feedback 2026-10-29: notices off the cloth, rounded cushion ends, deep pockets -----------
def _brightness(surf: pg.Surface, p: tuple[float, float]) -> int:
    return sum(_px(surf, p))


def test_cushions_are_rounded_at_both_ends_near_the_pockets():
    length, t, r = 300.0, table.CUSHION_PX, table.CUSHION_END_R
    pts = table.cushion_outline(length)
    assert min(s for s, _ in pts) == 0.0 and max(s for s, _ in pts) == length
    face = [p for p in pts if p[1] < 0.01]  # points on the cloth face
    assert min(s for s, _ in face) == pytest.approx(r)  # the straight face starts r in from the end
    assert max(s for s, _ in face) == pytest.approx(length - r)
    for s, d in pts:  # the corner on the cloth side is cut away, so no point lies nearer than this
        if s < r and d < r:
            assert math.hypot(s - r, d - r) == pytest.approx(r, abs=1e-6)
    assert max(d for _, d in pts) == t  # the base on the wood side is straight


def test_the_cushion_shadow_follows_the_rounded_outline():
    plain, grown = table.cushion_outline(300.0), table.cushion_outline(300.0, e=4.0)
    assert min(d for _, d in grown) == pytest.approx(-4.0)
    assert min(d for _, d in plain) == pytest.approx(0.0)
    assert (min(s for s, _ in grown), max(s for s, _ in grown)) == (0.0, 300.0)  # ends stay put


def test_there_are_six_cushions_and_each_clears_its_pockets():
    strips = table.cushion_strips()
    assert len(strips) == 6
    for a, b, _ in strips:
        for px, py, pr in POCKETS:
            centre = to_px(px, py)
            for end in (a, b):
                assert math.dist(end, centre) >= pr * PX_PER_M - 1e-6 + 1  # no end deep in a pocket


def test_pockets_have_a_light_lip_a_dark_ring_and_a_hole_sunk_outwards(surf):
    for px, py, pr in POCKETS:
        c = to_px(px, py)
        r = pr * PX_PER_M
        ux, uy = table.pocket_outward(px, py)

        def at(radius: float, sign: int = 1, c=c, ux=ux, uy=uy) -> int:
            return _brightness(surf, (c[0] + sign * ux * radius, c[1] + sign * uy * radius))

        lip = at(r + table.LIP_PX * 0.5)
        assert lip > at(r * 0.5) + 150  # the lip is much lighter than the hole
        assert at(r * 0.15, 1) < 25  # the very deepest part is nearly black
        assert at(r * 0.45, -1) > at(r * 0.45, 1) + 15  # the near wall (cloth side) shows


def test_pocket_outward_points_away_from_the_middle_of_the_table():
    assert table.pocket_outward(0.0, 0.0) == pytest.approx((-math.sqrt(0.5), -math.sqrt(0.5)))
    assert table.pocket_outward(1.27, 0.0) == pytest.approx((0.0, -1.0))
    assert table.pocket_outward(1.27, 1.27) == pytest.approx((0.0, 1.0))


@pytest.fixture
def scene():
    pg.init()
    a = App(pg.display.set_mode(config.LOGICAL_SIZE))
    a.go_play()
    yield a.play
    pg.quit()
    i18n.set_lang("vi")


@pytest.mark.parametrize("lang", ["vi", "en"])
def test_notices_never_cover_the_table(scene, lang):
    i18n.set_lang(lang)
    scene.rules.cue_in_hand = True  # the 2-line case: the foul and the "place the ball" hint
    plain = pg.Surface(scene.view.size)
    scene._notice_left = 0.0
    scene.draw(plain)
    with_notice = pg.Surface(scene.view.size)
    scene._notify("foul", "foul.no_cushion")  # the longest foul text
    scene.draw(with_notice)
    table_rect = pg.Rect(OUTER_X - 6, OUTER_Y - 6, OUTER_W + 12, OUTER_H + 12)
    assert pg.image.tobytes(plain.subsurface(table_rect), "RGB") == pg.image.tobytes(
        with_notice.subsurface(table_rect), "RGB"
    )
    below = pg.Rect(
        0, table_rect.bottom, scene.view.size[0], scene.view.size[1] - table_rect.bottom
    )
    assert pg.image.tobytes(plain.subsurface(below), "RGB") != pg.image.tobytes(
        with_notice.subsurface(below), "RGB"
    )  # ... and the notice is there, under the table
    assert hud.BANNER_PAD + 24 * 2 + OUTER_Y + OUTER_H + 12 < config.LOGICAL_SIZE[1]


def _wedge_points(px: float, py: float, pr: float) -> list[tuple[float, float]]:
    """Points in the little wedge between a rounded cushion end and the pocket lip: 1 px past the
    lip along each rail that meets the pocket, and 3 px into the cushion band."""
    ux, uy = table.pocket_outward(px, py)
    cx, cy = to_px(px, py)
    reach = pr * PX_PER_M + table.LIP_PX + 1.0
    wood_y, wood_x = math.copysign(3.0, uy), math.copysign(3.0, ux)
    if ux == 0:  # a middle pocket: the rail runs left and right of it
        return [(cx - reach, cy + wood_y), (cx + reach, cy + wood_y)]
    return [
        (cx - math.copysign(reach, ux), cy + wood_y),
        (cx + wood_x, cy - math.copysign(reach, uy)),
    ]


def test_no_brass_or_wood_peeks_out_next_to_the_rounded_cushion_ends(surf):
    for px, py, pr in POCKETS:
        for p in _wedge_points(px, py, pr):
            r, g, b = _px(surf, p)
            assert g > r + 20 and g > b, (px, py, (r, g, b))  # cushion green, not brass/wood
