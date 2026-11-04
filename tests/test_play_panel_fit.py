"""The Play panel is only as tall as the step it shows, and glides between heights."""

import pygame as pg
import pytest

from game import config
from game.app import App
from game.render import draw
from game.render import palette as C
from game.render.floating import MORPH_S
from game.render.view import View
from game.scenes import play_panel as pp
from game.scenes import settings as settings_panel


@pytest.fixture
def app():
    pg.init()
    screen = pg.display.set_mode(config.LOGICAL_SIZE)
    a = App(screen)
    a.skip_transition()
    yield a
    pg.quit()


def frames(a, n, dt=1 / 60):
    for _ in range(n):
        a.update(dt)
        a.draw()


def key(a, k):
    a.handle_event(pg.event.Event(pg.KEYDOWN, key=k))


def open_panel(a):
    a.menu.sel = 0
    key(a, pg.K_RETURN)
    frames(a, 30)
    return a.menu.play_panel


def test_every_step_is_only_as_tall_as_what_it_holds(app):
    panel = app.menu.play_panel
    for step in pp.ITEMS:
        panel.step = step
        frame, rects = panel.rect(), panel._rects()
        assert frame.h == pp.HEIGHT[step]
        assert all(frame.contains(r) for r in rects.values()), step
        # nothing empty below the lowest button: the same margin at every step
        assert frame.bottom - max(r.bottom for r in rects.values()) == 18, step
    assert pp.HEIGHT[pp.CHOOSE] < 400  # the first step held two buttons in a 440 px frame
    assert pp.HEIGHT[pp.PRACTICE] <= pp.PANEL.h  # three big buttons and Back still fit the panel


def test_the_practice_step_has_three_big_buttons_and_back_under_them(app):
    rects = pp.RECTS[pp.PRACTICE]
    big = [rects[m] for m in config.PRACTICE_MODES]
    assert [r.h for r in big] == [76, 76, 76]
    assert [b.top - a.bottom for a, b in zip(big, big[1:], strict=False)] == [12, 12]
    assert rects["back"].top > big[-1].bottom and not rects["back"].colliderect(big[-1])
    assert len({r.x for r in big}) == 1 and len({r.w for r in big}) == 1


@pytest.mark.parametrize("lang", ["vi", "en"])
@pytest.mark.parametrize("scale", [0.5, 0.82, 1.0, 1.5])
@pytest.mark.parametrize("level", config.PRACTICE_LEVELS)
def test_the_level_step_is_as_tall_as_its_caption_and_leaves_nothing_empty(app, lang, scale, level):
    from game import i18n
    from game.render import hud

    i18n.set_lang(lang)
    try:
        panel = app.menu.play_panel
        panel.step, panel.level, panel._v = pp.LEVEL, level, View(scale)
        frame, rects = panel.rect(), panel._rects()
        _, _, lines, caption_y = panel._level()
        assert frame.h == panel.fit_h() and abs(frame.centery - pp.PANEL.centery) <= 1
        assert frame.bottom - rects["back"].bottom == 18  # the same margin as every other step
        assert all(frame.contains(r) for r in rects.values())
        # the caption is broken to fit under the row, and the frame holds exactly its lines
        assert lines == hud.wrap(
            panel._v, i18n.t(f"practice.level.{level}_sub"), pp.CAPTION_SIZE, pp.W - 32
        )
        assert all(hud.text_width(panel._v, ln, pp.CAPTION_SIZE) <= pp.W - 32 for ln in lines)
        assert caption_y == rects["level"].bottom + pp.CAPTION_GAP
        assert rects["start"].top == caption_y + len(lines) * pp.CAPTION_STEP + pp.START_GAP
        # Back (left) and Start (right) share one row as wide as the column: the gap comes out of
        # it and Start takes 60% of what is left, Back 40%
        back, start = rects["back"], rects["start"]
        assert back.top == start.top and back.h == start.h == pp.START_H
        assert (back.left, start.right) == (pp.X, pp.X + pp.W)
        assert start.left - back.right == pp.ACTION_GAP
        assert start.w == round((pp.W - pp.ACTION_GAP) * 0.6)
        assert back.w + start.w + pp.ACTION_GAP == pp.W and back.w < start.w
        assert frame.h % 2 == 0  # (an odd height would leave the frame half a pixel off centre)
    finally:
        i18n.set_lang("vi")


def test_a_longer_caption_makes_a_taller_frame_and_a_shorter_one_a_shorter_frame(app):
    from game import i18n

    panel = app.menu.play_panel
    panel.step, panel._v = pp.LEVEL, View(1.0)
    table = i18n.table(i18n.get_lang())
    old = table["practice.level.easy_sub"]
    one = panel._level("easy")[0]
    try:
        table["practice.level.easy_sub"] = (old + " ") * 4
        four_lines = len(panel._level("easy")[2])
        assert (
            four_lines > 1 and panel._level("easy")[0] == one + (four_lines - 1) * pp.CAPTION_STEP
        )
        assert panel._level("hard")[0] != panel._level("easy")[0]  # each level: its own height
    finally:
        table["practice.level.easy_sub"] = old
    assert panel._level("easy")[0] == one


def test_changing_the_level_glides_the_frame_when_the_caption_changes_height(app):
    from game import i18n

    panel = open_panel(app)
    panel._goto(pp.PRACTICE)
    frames(app, 30)
    panel.mode, panel.level = "ghost", "easy"
    panel._goto(pp.LEVEL, pp.ITEMS[pp.LEVEL].index("level"))
    frames(app, 40)
    table = i18n.table(i18n.get_lang())
    old = table["practice.level.hard_sub"]
    try:
        table["practice.level.hard_sub"] = (old + " ") * 3  # a caption of more lines
        before = panel.rect().h
        key(app, pg.K_RIGHT)
        assert panel.level == "hard" and panel._morph is not None
        assert panel._morph.to_h == panel._level("hard")[0] > before
        heights = []
        for _ in range(30):
            frames(app, 1)
            heights.append(panel.rect().h)
        assert before < heights[3] < heights[-1] == panel.fit_h()  # it glided, it did not jump
        # a change that keeps the height does not move the frame at all
        table["practice.level.hard_sub"] = table["practice.level.easy_sub"]
        key(app, pg.K_LEFT)
        assert panel.level == "easy" and panel._morph is None
    finally:
        table["practice.level.hard_sub"] = old


def test_the_frame_is_centred_whatever_its_height(app):
    panel = app.menu.play_panel
    for step in pp.ITEMS:
        panel.step = step
        assert abs(panel.rect().centery - pp.PANEL.centery) <= 1, step


def test_changing_step_glides_the_frame_to_the_new_height(app):
    panel = open_panel(app)
    start = panel.rect().h
    assert start == pp.HEIGHT[pp.CHOOSE] and panel._morph is None
    key(app, pg.K_DOWN)
    key(app, pg.K_RETURN)  # Two players
    assert panel.step == pp.SETUP and panel._morph is not None
    heights = []
    for _ in range(40):
        frames(app, 1, 0.01)
        heights.append(panel.rect().h)
        assert abs(panel.rect().centery - pp.PANEL.centery) <= 1
    target = pp.HEIGHT[pp.SETUP]
    assert heights == sorted(heights) and heights[0] < target  # growing, never past it
    assert heights[-1] == target and panel._morph is None
    assert 40 * 0.01 > MORPH_S  # (the run was long enough to finish)


def blank_share(a, panel):
    """How much of the panel's content area is the plain panel colour (1.0: nothing painted)."""
    area = a.view.rect(*panel._inner(panel.rect())).clip(pg.display.get_surface().get_rect())
    px = pg.surfarray.array3d(pg.display.get_surface().subsurface(area))
    near = (
        abs(px.astype(int) - panel._inside(a.view)).max(axis=2) <= 3
    )  # (the edge's glow reaches in)
    return float(near.mean())


def test_the_old_content_fades_out_then_the_new_one_fades_in(app):
    panel = open_panel(app)
    key(app, pg.K_DOWN)
    key(app, pg.K_RETURN)
    frames(app, 3, 0.01)  # 0.03 s: the old step is still there, fainter
    early = blank_share(app, panel)
    frames(app, 10, 0.01)  # 0.13 s: between the two: nothing of either
    middle = blank_share(app, panel)
    frames(app, 40, 0.01)  # done: the new step, whole
    late = blank_share(app, panel)
    assert middle > 0.995 > early  # (the button just pressed flashes: no comparison with rest)
    assert late < 0.95 and panel._morph is None


def test_a_change_of_step_makes_no_new_frame_sprite_per_frame(app):
    panel = app.menu.play_panel
    draw._rr_cache.clear()
    panel.prewarm(app.view)
    panel = open_panel(app)
    before = {k for k in draw._rr_cache if k[1] == pp.PANEL.w}  # frame-wide sprites
    key(app, pg.K_DOWN)
    key(app, pg.K_RETURN)
    frames(app, 40, 0.01)
    after = {k for k in draw._rr_cache if k[1] == pp.PANEL.w}
    assert after == before, after - before


def test_the_stretched_frame_looks_like_a_frame_of_its_own_size(app):
    v = View(1.0)
    size = (560, 480)
    plain, stretched = pg.Surface(size), pg.Surface(size)
    for surf in (plain, stretched):
        surf.fill(C.BG)
    for h in (150, 260, 311):
        draw.blit_rrect(plain, v, 40, 60, 480, h, 10, C.PANEL, 1.8, C.VIOLET, 1.0)
        draw.blit_rrect_stretch(stretched, v, 40, 60, 480, h, 10, C.PANEL, 1.8, C.VIOLET, 1.0)
        a, b = pg.surfarray.array3d(plain).astype(int), pg.surfarray.array3d(stretched).astype(int)
        assert abs(a - b).mean() < 0.35, h
        assert abs(a - b).max() <= 40, h
        plain.fill(C.BG)
        stretched.fill(C.BG)


def test_a_stretched_frame_too_short_to_have_a_middle_still_draws(app):
    v = View(1.0)
    surf = pg.Surface((560, 200))
    surf.fill(C.BG)
    draw.blit_rrect_stretch(surf, v, 40, 20, 480, 30, 10, C.PANEL, 1.8, C.VIOLET, 1.0)
    assert all(abs(x - y) <= 3 for x, y in zip(surf.get_at((280, 35))[:3], C.PANEL, strict=True))


def test_settings_keeps_its_fixed_frame(app):
    settings = app.menu.settings
    assert not settings.RESIZES and settings.rect() == settings_panel.PANEL


def test_closing_in_the_middle_of_a_change_ends_it(app):
    panel = open_panel(app)
    key(app, pg.K_DOWN)
    key(app, pg.K_RETURN)
    frames(app, 3, 0.01)
    assert panel._morph is not None
    key(app, pg.K_ESCAPE)  # back to the first step, then close
    key(app, pg.K_ESCAPE)
    frames(app, 40, 0.01)
    assert not panel.is_open and panel._morph is None


def test_a_step_changed_before_the_panel_has_ever_been_drawn_just_changes(app):
    panel = app.menu.play_panel
    panel.open()
    panel._goto(pp.JOINING)  # (no picture of the old step exists to fade)
    assert panel._morph is None and panel.rect().h == pp.HEIGHT[pp.JOINING]
