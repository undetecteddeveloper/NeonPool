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
from game.config import POCKETS, PX_PER_M, TABLE_L, TABLE_W
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


def test_the_table_is_one_flat_dark_plate_a_little_lighter_than_the_night(surf):
    middle = _px(surf, (FIELD_X + FIELD_W / 2, FIELD_Y + FIELD_H / 2))
    corner = _px(surf, (FIELD_X + 60, FIELD_Y + 60))
    assert max(abs(a - b) for a, b in zip(middle, C.TABLE, strict=True)) <= 3  # flat, no shading
    assert middle == corner
    outside = _px(surf, (OUTER_X - 30, OUTER_Y + OUTER_H / 2))
    assert sum(middle) > sum(outside)  # the table reads against the night


def test_the_cloth_next_to_a_pocket_is_plain_night_not_lit(surf):
    r, g, b = _px(surf, to_px(0.13, 0.13))  # just inside the field, beside the corner pocket
    assert r + g + b < 120 and b >= r and b >= g


def test_the_rim_is_a_cyan_line_with_a_halo_that_fades_to_the_night(surf):
    mid_y = OUTER_Y + OUTER_H / 2
    r, g, b = _px(surf, (OUTER_X + 1, mid_y))
    assert g > 150 and b > 150 and r < g - 80  # lit cyan
    halo = _px(surf, (OUTER_X - 5, mid_y))
    far = _px(surf, (OUTER_X - 40, mid_y))
    night = tuple(backdrop.night(V.size).get_at((OUTER_X - 40, round(mid_y))))[:3]
    assert sum(halo) > sum(far) + 30  # light spills outside the rim ...
    assert sum(far) <= sum(night) + 3  # ... but not far: there it is the night again


def test_pockets_are_black_where_the_physics_has_them(surf):
    for px, py, _ in POCKETS:
        assert sum(_px(surf, to_px(px, py))) < 60


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


# --- the neon cue (replaces the pull bar, 2026-10-29) ---------------------------------------
def test_the_cue_lies_behind_the_ball_and_travels_less_than_the_hand():
    centre = (500.0, 300.0)
    for pull in (0.0, 80.0, 220.0):
        tip, u = draw.cue_tip(centre, (1.0, 0.0), pull)
        assert u == pytest.approx((-1.0, 0.0))  # the cue is on the far side from the shot
        shown = centre[0] - tip[0] - draw.RIM - draw.STICK_GAP
        assert shown == pytest.approx(pull * config.CUE_SHOW_PULL)  # 25% less than the pull
        assert tip[1] == pytest.approx(centre[1])
    assert 0.7 <= config.CUE_SHOW_PULL <= 0.8  # the user asked for 20-30% less travel


def test_the_cue_narrows_to_its_tip():
    quad = draw.stick_outline((0.0, 0.0), (1.0, 0.0))
    tip_w = abs(quad[0][1] - quad[3][1])
    butt_w = abs(quad[1][1] - quad[2][1])
    assert tip_w < butt_w
    assert quad[1][0] == pytest.approx(draw.STICK_LEN)


def test_the_cue_gets_hotter_the_harder_the_pull():
    assert draw.power_color(0.0) == C.CYAN  # a gentle pull is cold
    hot = draw.power_color(1.0)
    assert hot[0] > 240 and hot[1] > 200  # a full pull is white-hot
    reds = [draw.power_color(p / 20)[0] for p in range(21)]
    blues = [draw.power_color(p / 20)[2] for p in range(12, 21)]
    assert reds == sorted(reds)  # warmer and warmer ...
    assert blues[0] > blues[-3]  # ... the blue drains away towards the top


def test_the_cue_is_drawn_with_a_white_tip_in_the_colour_of_its_heat():
    def frame(power: float) -> pg.Surface:
        canvas = pg.Surface(V.size)
        canvas.fill((0, 0, 0))
        draw.draw_cue(canvas, V, (640.0, 360.0), (1.0, 0.0), 40.0, power, 0.0)
        return canvas

    weak, strong = frame(0.1), frame(0.9)
    tip_x = 640 - draw.RIM - draw.STICK_GAP - 40 * config.CUE_SHOW_PULL - 3
    assert min(weak.get_at((round(tip_x), 360))[:3]) > 200  # the white tip
    body = (round(tip_x - 100), 362)  # on the body, off the bright core line
    assert strong.get_at(body)[0] > weak.get_at(body)[0] + 40  # hot: much more red
    assert weak.get_at(body)[2] > weak.get_at(body)[0]  # cold: blue rather than red


def test_the_cue_fades_in_on_the_cue_ball_and_out_off_it(scene):
    cue = scene.world.balls[0]
    on, off = to_px(cue.x, cue.y), (100.0, 100.0)
    scene.handle_event(pg.event.Event(pg.MOUSEMOTION, pos=on, rel=(0, 0), buttons=(0, 0, 0)))
    scene.update(draw.CUE_FADE_IN_S / 2)
    assert 0.3 < scene._cue_alpha < 0.8  # fading in, not popping
    scene.update(draw.CUE_FADE_IN_S)
    assert scene._cue_alpha == 1.0
    scene.handle_event(pg.event.Event(pg.MOUSEMOTION, pos=off, rel=(0, 0), buttons=(0, 0, 0)))
    scene.update(draw.CUE_FADE_OUT_S / 2)
    assert 0.2 < scene._cue_alpha < 0.8  # fading out
    scene.update(draw.CUE_FADE_OUT_S)
    assert scene._cue_alpha == 0.0


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


def pocket_outward(px: float, py: float) -> tuple[float, float]:
    """Unit vector towards the outside of the table at a pocket: diagonal at a corner pocket,
    straight up/down at a middle pocket."""
    ux = (px > TABLE_L * 0.75) - (px < TABLE_L * 0.25)  # -1, 0 or +1
    uy = (py > TABLE_W * 0.75) - (py < TABLE_W * 0.25)
    n = math.hypot(ux, uy)
    return ux / n, uy / n


def test_pockets_are_a_ring_of_pink_light_round_a_black_hole(surf):
    for px, py, pr in POCKETS:
        c = to_px(px, py)
        r = pr * PX_PER_M
        ux, uy = pocket_outward(px, py)

        def at(radius: float, c=c, ux=ux, uy=uy) -> tuple[int, int, int]:
            return _px(surf, (c[0] + ux * radius, c[1] + uy * radius))

        ring = max((at(r + table.LIP_PX + d) for d in (-1.0, -0.5, 0.0, 0.5, 1.0)), key=sum)
        assert ring[0] > 180 and ring[2] > 140 and ring[1] < ring[0] - 80  # pink light
        assert all(sum(at(r * k)) < 25 for k in (0.0, 0.3, 0.6, 0.85))  # black all the way in


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
    """The notice hangs under the table. The big arcade word may cross the table, but only while
    every ball is still (notices are made when a shot ends) and it is gone at the first click."""
    i18n.set_lang(lang)
    scene.rules.cue_in_hand = True  # the 2-line case: the foul and the "place the ball" hint
    plain = pg.Surface(scene.view.canvas)
    scene._notice_left = 0.0
    scene.draw(plain)
    with_notice = pg.Surface(scene.view.canvas)
    scene._notify("foul", "foul.no_cushion")  # the longest foul text
    assert scene._callout is not None and scene.world.at_rest()
    scene._callout = None  # the call-out aside, the table itself is untouched
    scene.draw(with_notice)
    table_rect = scene.view.rect(OUTER_X - 6, OUTER_Y - 6, OUTER_W + 12, OUTER_H + 12)
    assert pg.image.tobytes(plain.subsurface(table_rect), "RGB") == pg.image.tobytes(
        with_notice.subsurface(table_rect), "RGB"
    )
    below = pg.Rect(0, table_rect.bottom, plain.get_width(), plain.get_height() - table_rect.bottom)
    assert pg.image.tobytes(plain.subsurface(below), "RGB") != pg.image.tobytes(
        with_notice.subsurface(below), "RGB"
    )  # ... and the notice is there, under the table
    assert hud.BANNER_PAD + 24 * 2 + OUTER_Y + OUTER_H + 12 < config.LOGICAL_SIZE[1]


def test_the_arcade_word_goes_away_at_a_click_or_by_itself(scene):
    scene._notify("foul", "foul.no_cushion")
    scene.handle_event(pg.event.Event(pg.MOUSEBUTTONDOWN, pos=(5, 5), button=1))
    assert scene._callout is None
    scene._notify("info", "notice.group_solid")
    word, _, at = scene._callout
    assert word == i18n.t("callout.solid")
    a, b = pg.Surface(scene.view.canvas), pg.Surface(scene.view.canvas)
    scene._clock = at + hud.CALLOUT_S + 0.01  # after its time it draws nothing
    scene.draw(a)
    scene._callout = None
    scene.draw(b)
    assert pg.image.tobytes(a, "RGB") == pg.image.tobytes(b, "RGB")
