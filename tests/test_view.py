"""Rendering at the real window resolution (feedback: blurry menu balls, jagged pockets)."""

import pygame as pg
import pytest

from game import app as app_module
from game.app import App
from game.config import LOGICAL_SIZE
from game.render.view import View


def test_view_scales_and_leaves_no_gap_between_neighbouring_rects():
    v = View(0.8203)
    a, b = v.rect(10, 10, 33.3, 5), v.rect(10 + 33.3, 10, 20, 5)
    assert a.right == b.left  # rounded per edge, not per size


def test_view_for_window_matches_the_fitted_canvas():
    assert View.for_window((1280, 720)).s == 1.0
    # 1050x590 is slightly wider than 16:9, so the height limits: canvas 1049x590
    assert View.for_window((1050, 590)).size == (1049, 590)
    assert View.for_window((2560, 720)).s == 1.0  # wide window: height limits


@pytest.mark.parametrize("desktop", [(1280, 720), (1366, 768), (1920, 1080), (2560, 1440)])
def test_start_window_fits_the_screen_and_keeps_16_9(monkeypatch, desktop):
    monkeypatch.setattr(pg.display, "get_desktop_sizes", lambda: [desktop])
    w, h = app_module._start_size()
    assert w <= desktop[0] - 40 and h <= desktop[1] - 130  # room for title bar and taskbar
    assert abs(w / h - LOGICAL_SIZE[0] / LOGICAL_SIZE[1]) < 0.01


@pytest.fixture
def app():
    pg.init()
    pg.display.set_mode((1280, 720))
    a = App(pg.display.get_surface())
    yield a
    pg.quit()


@pytest.mark.parametrize("size", [(1050, 590), (1920, 1080), (640, 360), (900, 900)])
def test_every_screen_is_rebuilt_sharp_for_any_window_size(app, size):
    pg.display.set_mode(size, pg.RESIZABLE)
    app.sync_view(force=True)
    assert app.view.same_as(View.for_window(size))
    assert app.canvas.get_size() == app.view.size
    assert app.play.table.get_size() == app.view.size  # built for this size, not stretched
    for go in (app.go_menu, app.go_play):
        go()
        app.draw()


def test_resizing_keeps_the_mouse_mapping_correct(app):
    pg.display.set_mode((1050, 590), pg.RESIZABLE)
    app.sync_view(force=True)
    app.go_play()
    cue = app.play.world.balls[0]
    from game.render.layout import to_px

    lx, ly = to_px(cue.x, cue.y)
    s = app.view.s
    app.handle_event(
        pg.event.Event(pg.MOUSEBUTTONDOWN, pos=(round(lx * s), round(ly * s)), button=1)
    )
    assert app.play.drag.active  # pressed exactly on the cue ball at the new size


def test_settling_delay_stretches_instead_of_rebuilding(app, monkeypatch):
    old = app.view
    pg.display.set_mode((1050, 590), pg.RESIZABLE)
    app.draw()  # window just changed: keep the old assets for now
    assert app.view is old
    app.sync_view(force=True)
    assert app.view is not old
