"""Look of the table, balls and pull bar. Feedback kept since 2026-10-28: no checkers, a square
pull bar, deep pockets, notices off the cloth, cushion ends rounded. The look itself is neon
(2026-10-29): a night-blue cloth, a rail and cushions of light, pockets ringed in pink-violet,
balls like lamps."""

import math
from types import SimpleNamespace

import pygame as pg
import pytest

from game import config, i18n
from game.app import App
from game.config import POCKETS, PX_PER_M
from game.physics import Contact
from game.render import backdrop, draw, hud, table
from game.render import palette as C
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


def test_cloth_is_night_blue_and_brighter_in_the_middle_than_near_the_corners(surf):
    middle = _px(surf, (FIELD_X + FIELD_W / 2, FIELD_Y + FIELD_H / 2))
    corner = _px(surf, (FIELD_X + 40, FIELD_Y + 40))
    assert sum(middle) > sum(corner) + 60
    assert middle[2] > middle[1] > middle[0]  # blue, with the least red


def test_the_cloth_next_to_a_pocket_is_plain_night_not_lit(surf):
    r, g, b = _px(surf, to_px(0.13, 0.13))  # just inside the field, beside the corner pocket
    assert r + g + b < 120 and b >= g >= r


def test_the_rim_is_a_cyan_line_with_a_halo_that_fades_to_the_night(surf):
    mid_y = OUTER_Y + OUTER_H / 2
    r, g, b = _px(surf, (OUTER_X + 1, mid_y))
    assert g > 150 and b > 150 and r < g - 80  # lit cyan
    night = backdrop.night(V.size)
    halo = tuple(surf.get_at((OUTER_X - 5, round(mid_y))))[:3]
    far = tuple(surf.get_at((OUTER_X - 40, round(mid_y))))[:3]
    base = tuple(night.get_at((OUTER_X - 5, round(mid_y))))[:3]
    assert sum(halo) > sum(base) + 30  # light spills outside the rim
    assert far == tuple(night.get_at((OUTER_X - 40, round(mid_y))))[:3]  # ... and not far


def test_pockets_are_black_where_the_physics_has_them(surf):
    for px, py, _ in POCKETS:
        assert sum(_px(surf, to_px(px, py))) < 60


def test_diamonds_clear_the_housings_and_pockets():
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


# --- balls: dark lamps ---------------------------------------------------------------------
def _sprite_px(spr: pg.Surface, dx: float, dy: float) -> tuple[int, int, int, int]:
    """The pixel `dx, dy` logical px from the sprite's centre (it is drawn at 1x here)."""
    c = spr.get_width() / 2
    return tuple(spr.get_at((int(c + dx), int(c + dy))))


def test_a_solid_ball_is_a_dark_body_with_a_lit_ring_in_its_own_colour():
    spr = draw.BallSprites(V).get(3)
    ring = _sprite_px(spr, -draw.BALL_PX, 0)
    body = _sprite_px(spr, -draw.BALL_PX * 0.7, 0)
    assert ring[0] > 200 and ring[1] < 110  # the red of ball 3, lit
    assert sum(body[:3]) < 80  # the body is dark


def test_a_stripe_has_lit_chords_where_a_solid_has_none():
    sprites = draw.BallSprites(V)
    spot = (-draw.BALL_PX * 0.5, -draw.BALL_PX * 0.52)  # on the upper chord of a stripe
    stripe, solid = _sprite_px(sprites.get(11), *spot), _sprite_px(sprites.get(3), *spot)
    assert stripe[0] > solid[0] + 150


def test_the_cue_ball_is_one_lit_disc():
    spr = draw.BallSprites(V).get(0)
    assert min(_sprite_px(spr, 0, 0)[:3]) > 220
    assert min(_sprite_px(spr, draw.BALL_PX * 0.6, draw.BALL_PX * 0.6)[:3]) > 220


def test_a_ball_gives_light_evenly_all_round_it_not_a_shadow_on_one_side():
    canvas = pg.Surface(V.size)
    canvas.fill((20, 20, 30))
    ball = SimpleNamespace(in_play=True, x=1.27, y=0.635, number=3)
    draw.draw_balls(canvas, V, [ball], draw.BallSprites(V))
    cx, cy = to_px(ball.x, ball.y)
    reach = int(draw.BALL_PX + draw.HALO_PX) + 2
    total = sx = sy = 0.0
    for x in range(int(cx) - reach, int(cx) + reach):
        for y in range(int(cy) - reach, int(cy) + reach):
            light = max(0, canvas.get_at((x, y))[0] - 20)  # red light added by the ball
            total, sx, sy = total + light, sx + light * (x + 0.5), sy + light * (y + 0.5)
    assert total > 2000  # the ball gives light
    # the centre of that light is the centre of the ball: a shadow or a glow on one side would
    # pull it away (the sprite is placed on whole pixels, so half a pixel is the most it can be off)
    assert abs(sx / total - cx) < 0.7 and abs(sy / total - cy) < 0.7


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
    canvas.fill((0, 0, 0))
    cue = SimpleNamespace(x=1.27, y=0.635)
    far = (cue.x + 0.5, cue.y)
    contact = Contact("cushion", 0.5, far)
    draw.draw_aim(canvas, V, cue, contact, (1.0, 0.0), 100.0, 0.5)
    cx, cy = to_px(cue.x, cue.y)
    end_x = cx - draw.RIM - 3 - 100  # outer face of the far end
    reach = draw.BAR_HALF_W
    for sign in (-1, 1):  # both far corners are lit: a round tip would leave them dark
        corner = canvas.get_at((round(end_x + 1.5), round(cy + sign * (reach - 1.5))))
        assert sum(corner[:3]) > 300


def test_the_bar_goes_from_cyan_to_pink_violet_with_power():
    weak, strong = draw.power_color(0.0), draw.power_color(1.0)
    assert weak == C.CYAN and strong == C.MAGENTA
    mid = draw.power_color(0.5)
    assert min(weak[0], strong[0]) < mid[0] < max(weak[0], strong[0])


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
    assert max(d for _, d in pts) == t  # the base on the rail side is straight


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


def test_the_cushion_edge_facing_the_cloth_is_lit(surf):
    a, b, out = table.cushion_strips()[0]  # the top-left cushion
    mid = ((a[0] + b[0]) / 2, a[1])
    r, g, bl = _px(surf, mid)
    assert g > 140 and bl > 170  # the lit edge (cyan family) ...
    assert _brightness(surf, (mid[0], mid[1] + 14)) < 120  # ... and the cloth under it is night


def test_pockets_are_a_ring_of_light_round_a_deep_hole_sunk_outwards(surf):
    for px, py, pr in POCKETS:
        c = to_px(px, py)
        r = pr * PX_PER_M
        ux, uy = table.pocket_outward(px, py)

        def at(radius: float, sign: int = 1, c=c, ux=ux, uy=uy) -> int:
            return _brightness(surf, (c[0] + sign * ux * radius, c[1] + sign * uy * radius))

        ring = max(at(r + table.LIP_PX + d) for d in (-1.0, -0.5, 0.0, 0.5, 1.0))
        assert ring > at(r * 0.5) + 300  # the ring is pink-violet light, the hole is black
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
