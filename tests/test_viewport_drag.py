import math

import pytest

from game.config import MAX_DRAG_PX, MIN_PULL_PX, POWER_CURVE
from game.input.drag import DragAim
from game.render.viewport import fit, window_to_logical

LOGICAL = (1280, 720)


# --- AC9: window scaling and mouse mapping ------------------------------------------------
def test_fit_exact_window_has_no_bars():
    assert fit((1280, 720), LOGICAL) == (1.0, 0, 0, 1280, 720)


def test_fit_wider_window_adds_side_bars_and_keeps_aspect():
    scale, x, y, w, h = fit((1920, 720), LOGICAL)
    assert (scale, y, h) == (1.0, 0, 720) and w == 1280 and x == 320


def test_fit_taller_window_adds_top_bottom_bars():
    scale, x, y, w, h = fit((1280, 1000), LOGICAL)
    assert x == 0 and w == 1280 and h == 720 and y == 140 and scale == 1.0


def test_fit_scales_and_centres():
    scale, x, y, w, h = fit((640, 480), LOGICAL)
    assert scale == 0.5 and (w, h) == (640, 360) and (x, y) == (0, 60)


@pytest.mark.parametrize("window", [(1280, 720), (640, 480), (1920, 1080), (900, 900), (2560, 720)])
def test_mouse_mapping_hits_canvas_corners_and_centre(window):
    scale, x, y, w, h = fit(window, LOGICAL)
    assert window_to_logical((x, y), window, LOGICAL) == pytest.approx((0, 0), abs=1e-6)
    assert window_to_logical((x + w / 2, y + h / 2), window, LOGICAL) == pytest.approx(
        (640, 360), abs=1.0
    )
    assert window_to_logical((x + w, y + h), window, LOGICAL) == pytest.approx((1280, 720), abs=1.0)


# --- AC4: drag aiming -----------------------------------------------------------------------
def test_pull_left_shoots_right():
    d = DragAim()
    d.begin((500, 300), (500, 300))
    d.move((400, 300))  # pulled to the left of the cue ball
    shot = d.end()
    assert shot is not None and shot.angle == pytest.approx(0.0)  # shoots to the right (+x)
    assert shot.power == pytest.approx((100 / MAX_DRAG_PX) ** POWER_CURVE)


def test_pull_down_shoots_up_screen():
    d = DragAim()
    d.begin((500, 300), (500, 300))
    d.move((500, 360))
    shot = d.end()
    assert shot.angle == pytest.approx(-math.pi / 2)  # up = -y in screen/table coordinates


def test_power_is_clamped_to_one():
    d = DragAim()
    d.begin((0, 0), (0, 0))
    d.move((-5000, 0))
    assert d.power == 1.0 and d.end().power == 1.0


def test_weak_pull_cancels():
    d = DragAim()
    d.begin((0, 0), (0, 0))
    d.move((-MIN_PULL_PX * 0.5, 0))
    assert d.end() is None and not d.active


def test_cancel_and_idle_state():
    d = DragAim()
    assert d.power == 0.0 and not d.has_direction and d.end() is None
    d.begin((10, 10), (10, 10))
    assert d.active and not d.has_direction  # pointer on the ball: no direction yet
    d.move((60, 10))
    d.cancel()
    assert not d.active and d.end() is None


# --- feedback 2026-10-28: the pull bar must not grow forever ---------------------------------
def test_bar_length_grows_with_the_pull_then_stops_at_full_power():
    d = DragAim()
    assert d.bar_length == 0.0
    d.begin((0, 0), (0, 0))
    d.move((-MAX_DRAG_PX / 2, 0))
    assert d.bar_length == pytest.approx(MAX_DRAG_PX / 2)
    d.move((-MAX_DRAG_PX * 5, 0))  # the mouse is far beyond full power
    assert d.bar_length == MAX_DRAG_PX and d.power == 1.0
    d.cancel()
    assert d.bar_length == 0.0


def test_power_is_gentle_at_first_and_strong_at_the_end():
    d = DragAim()
    d.begin((0, 0), (0, 0))
    powers = []
    for fraction in (0.25, 0.5, 0.75, 1.0):
        d.move((-MAX_DRAG_PX * fraction, 0))
        powers.append(d.power)
    assert powers == sorted(powers) and powers[-1] == 1.0
    assert powers[1] < 0.5  # half the pull gives clearly less than half the power
    assert powers[0] < powers[1] / 2


def test_a_pull_just_above_the_minimum_still_shoots():
    d = DragAim()
    d.begin((0, 0), (0, 0))
    d.move((-MIN_PULL_PX * 1.5, 0))
    assert d.end() is not None
