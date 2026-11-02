"""Round of 2026-10-29: settings that are kept, the cue turned like a dial, screen changes like an
old tube, buttons that move, and text whose Vietnamese marks never push a letter down."""

import json
import math
import unicodedata
from pathlib import Path

import pygame as pg
import pytest

from game import app as app_module
from game import config, i18n, settings
from game.app import App
from game.input.drag import DragAim, Knob
from game.render import fonts, hud
from game.render.layout import to_px
from game.render.view import View
from game.scenes import settings as settings_panel

ROOT = Path(__file__).resolve().parent.parent
V = View(1.0)


def key(k):
    return pg.event.Event(pg.KEYDOWN, key=k)


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("NEONPOOL_SETTINGS", str(tmp_path / "settings.json"))
    pg.init()
    pg.display.set_mode(config.LOGICAL_SIZE)
    a = App(pg.display.get_surface())
    a.skip_transition()
    yield a
    pg.quit()
    i18n.set_lang("vi")


# --- settings that are kept ----------------------------------------------------------------
def test_settings_survive_a_restart(tmp_path):
    path = tmp_path / "s.json"
    settings.save(
        settings.Settings(lang="en", volume=0.3, music=0.2, shake=False, show_fps=True), path
    )
    back = settings.load(path)
    assert (back.lang, back.volume, back.music) == ("en", 0.3, 0.2)
    assert (back.shake, back.show_fps) == (False, True)


def test_a_missing_or_broken_file_gives_the_defaults(tmp_path):
    assert settings.load(tmp_path / "none.json") == settings.Settings()
    broken = tmp_path / "broken.json"
    broken.write_text("{ not json", encoding="utf-8")
    assert settings.load(broken) == settings.Settings()
    odd = tmp_path / "odd.json"
    odd.write_text(
        json.dumps({"lang": "fr", "volume": 7, "music": -3, "shake": "yes"}), encoding="utf-8"
    )
    s = settings.load(odd)
    assert s.lang == "vi" and s.volume == 1.0 and s.shake is True  # each value checked
    assert s.music == 0.0  # clamped, like the volume


def test_the_practice_best_streak_survives_a_restart_and_is_clamped(tmp_path):
    path = tmp_path / "s.json"
    settings.save(settings.Settings(practice_best=9), path)
    assert settings.load(path).practice_best == 9
    out_of_range = tmp_path / "odd.json"
    out_of_range.write_text(json.dumps({"practice_best": 99}), encoding="utf-8")
    assert settings.load(out_of_range).practice_best == 15  # clamped to the most balls on a table
    bad_type = tmp_path / "bad.json"
    bad_type.write_text(json.dumps({"practice_best": True}), encoding="utf-8")
    assert settings.load(bad_type).practice_best == 0  # a bool is not an int here


def test_changing_a_setting_applies_it_and_saves_it_at_once(app, tmp_path):
    app.change_settings(lang="en", volume=0.4, music=0.6, show_fps=True)
    assert i18n.get_lang() == "en" and app.audio.volume == pytest.approx(0.4)
    assert app.audio.music_volume == pytest.approx(0.6)
    on_disk = json.loads((tmp_path / "settings.json").read_text(encoding="utf-8"))
    assert on_disk["lang"] == "en" and on_disk["volume"] == 0.4 and on_disk["show_fps"] is True
    assert on_disk["music"] == 0.6
    again = App(pg.display.get_surface())  # the game is started again
    assert i18n.get_lang() == "en" and again.settings.show_fps
    assert again.audio.music_volume == pytest.approx(0.6)


def test_the_menu_opens_settings_and_the_keys_change_every_row(app, tmp_path):
    for _ in range(2):
        app.handle_event(key(pg.K_DOWN))  # play, how to play, settings
    app.handle_event(key(pg.K_RETURN))
    panel = app.menu.settings
    assert panel.is_open
    app.handle_event(key(pg.K_RIGHT))  # language
    assert i18n.get_lang() == "en"
    app.handle_event(key(pg.K_DOWN))
    before = app.settings.volume
    app.handle_event(key(pg.K_LEFT))  # volume, one step down
    assert app.settings.volume == pytest.approx(before - config.VOLUME_STEP)
    app.handle_event(key(pg.K_DOWN))
    before_music = app.settings.music
    app.handle_event(key(pg.K_RIGHT))  # music, one step up
    assert app.settings.music == pytest.approx(before_music + config.VOLUME_STEP)
    assert app.settings.volume == pytest.approx(before - config.VOLUME_STEP)  # its own bar
    app.handle_event(key(pg.K_DOWN))
    app.handle_event(key(pg.K_RETURN))  # shake off
    app.handle_event(key(pg.K_DOWN))
    app.handle_event(key(pg.K_RETURN))  # fps on
    assert not app.settings.shake and app.settings.show_fps
    app.handle_event(key(pg.K_ESCAPE))
    for _ in range(30):
        app.update(1 / 60)
    assert not panel.is_open
    saved = settings.load(tmp_path / "settings.json")
    assert saved.lang == "en" and not saved.shake and saved.show_fps


def test_the_volume_bar_follows_a_click(app):
    panel = app.menu.settings
    panel.open()
    row = settings_panel.row_rect(settings_panel.ROWS.index("volume"))
    x = settings_panel.TRACK[0] + (settings_panel.TRACK[1] - settings_panel.TRACK[0]) * 0.3
    app.menu.handle_event(pg.event.Event(pg.MOUSEBUTTONDOWN, pos=(x, row.centery), button=1))
    assert app.settings.volume == pytest.approx(0.3)


def test_the_music_bar_follows_a_click_and_a_drag_and_leaves_the_volume_alone(app):
    panel = app.menu.settings
    panel.open()
    row = settings_panel.row_rect(settings_panel.ROWS.index("music"))
    lo, hi = settings_panel.TRACK
    volume = app.settings.volume
    down = pg.event.Event(pg.MOUSEBUTTONDOWN, pos=(lo + (hi - lo) * 0.2, row.centery), button=1)
    app.menu.handle_event(down)
    assert app.settings.music == pytest.approx(0.2)
    move = pg.event.Event(pg.MOUSEMOTION, pos=(lo + (hi - lo) * 0.9, row.centery), rel=(0, 0),
                          buttons=(1, 0, 0))  # fmt: skip
    app.menu.handle_event(move)
    assert app.settings.music == pytest.approx(0.9)
    app.menu.handle_event(pg.event.Event(pg.MOUSEBUTTONUP, pos=move.pos, button=1))
    assert app.settings.volume == pytest.approx(volume)


def test_every_row_of_the_settings_panel_fits_inside_it(app):
    panel = settings_panel.PANEL
    for i in range(len(settings_panel.ROWS)):
        assert panel.contains(settings_panel.row_rect(i)), settings_panel.ROWS[i]
    for lang in ("vi", "en"):
        i18n.set_lang(lang)
        app.menu.settings.open()
        for _ in range(30):
            app.update(1 / 60)
            app.draw()


def test_shake_off_means_the_screen_never_shakes(app):
    app.go_play()
    app.change_settings(shake=False)
    play = app.play
    from game.physics import BallHitBall

    play._show_events([BallHitBall(0, 1, 6.0)])  # the break, very hard
    play.fx.update(0.01)
    assert play.shake_offset() == (0.0, 0.0)
    app.change_settings(shake=True)
    play._break_pending = True
    play._show_events([BallHitBall(0, 1, 6.0)])
    play.fx.update(0.01)
    assert play.shake_offset() != (0.0, 0.0)


def test_the_fps_counter_shows_only_when_asked(app):
    app.draw()
    corner = pg.Rect(0, 0, 90, 34)
    plain = pg.image.tobytes(pg.display.get_surface().subsurface(corner), "RGB")
    app.change_settings(show_fps=True)
    app.draw()
    shown = pg.image.tobytes(pg.display.get_surface().subsurface(corner), "RGB")
    assert plain != shown


# --- the cue as a dial ----------------------------------------------------------------------
def test_going_round_the_ball_turns_the_cue_one_for_one():
    knob = Knob(0.0)
    c = (500.0, 300.0)
    for deg in range(0, 91, 5):  # a quarter turn, clockwise on screen
        a = math.radians(deg)
        knob.move(c, (c[0] + 20 * math.cos(a), c[1] + 20 * math.sin(a)))
    assert knob.angle == pytest.approx(math.pi / 2, abs=1e-6)
    knob.release()  # off the ball and back on somewhere else: no jump
    knob.move(c, (c[0] - 20, c[1]))
    assert knob.angle == pytest.approx(math.pi / 2, abs=1e-6)


def test_the_very_centre_of_the_ball_does_not_turn_the_cue():
    knob = Knob(1.0)
    c = (0.0, 0.0)
    knob.move(c, (20.0, 0.0))
    knob.move(c, (0.5, 0.5))  # inside the dead spot
    knob.move(c, (-20.0, 0.0))  # straight through the centre: half a turn, ignored
    assert knob.angle == pytest.approx(1.0)


def test_the_pull_sets_the_direction_as_well_as_the_power_and_may_change_all_along():
    d = DragAim()
    d.begin((505, 300))  # pressed a little off the centre of the ball: that changes nothing
    d.move((505, 300 + config.MAX_DRAG_PX))  # pulled straight down: the shot goes up
    assert d.angle == pytest.approx(-math.pi / 2) and d.power == pytest.approx(1.0)
    d.move((505 + config.MAX_DRAG_PX / 2, 300))  # still pulling: sideways, half way
    assert d.angle == pytest.approx(math.pi)  # the aim followed the pull, it was not locked
    shot = d.end()
    assert shot.angle == pytest.approx(math.pi)
    assert shot.power == pytest.approx(0.5**config.POWER_CURVE)


def test_in_the_game_the_dial_sets_the_shot(app):
    app.go_play()
    play = app.play
    cue = play.world.balls[0]
    cx, cy = to_px(cue.x, cue.y)

    def move(x, y, buttons=(0, 0, 0)):
        play.handle_event(pg.event.Event(pg.MOUSEMOTION, pos=(x, y), rel=(0, 0), buttons=buttons))

    def press(x, y):
        play.handle_event(pg.event.Event(pg.MOUSEBUTTONDOWN, pos=(x, y), button=1))

    def release(x, y):
        play.handle_event(pg.event.Event(pg.MOUSEBUTTONUP, pos=(x, y), button=1))

    move(cx + 15, cy)  # onto the ball, on its right
    move(cx, cy + 15)  # a quarter turn round it (clockwise on screen)
    assert play.knob.angle == pytest.approx(math.pi / 2, abs=1e-6)
    press(cx, cy + 15)
    move(cx, cy - 105, (1, 0, 0))  # pulled up, back along the cue: the cue stays as dialled
    assert play.drag.angle == pytest.approx(math.pi / 2, abs=1e-6)
    move(cx - 120, cy + 15, (1, 0, 0))  # ... and then pulled to the left: the aim follows
    assert play.drag.angle == pytest.approx(0.0, abs=1e-6)
    release(cx - 120, cy + 15)
    assert cue.vx > 0 and abs(cue.vy) < 1e-6  # the ball goes right, away from the pull


def test_a_cancelled_pull_leaves_the_cue_where_the_pull_put_it(app):
    app.go_play()
    play = app.play
    cx, cy = to_px(play.world.balls[0].x, play.world.balls[0].y)
    play.handle_event(pg.event.Event(pg.MOUSEBUTTONDOWN, pos=(cx, cy), button=1))
    play.handle_event(
        pg.event.Event(pg.MOUSEMOTION, pos=(cx, cy + 60), rel=(0, 0), buttons=(1, 0, 0))
    )
    play.handle_event(pg.event.Event(pg.MOUSEBUTTONDOWN, pos=(cx, cy + 60), button=3))  # cancel
    assert not play.drag.active
    assert play.knob.angle == pytest.approx(-math.pi / 2, abs=1e-6)  # pulled down: aims up


# --- the screen changes like an old tube ------------------------------------------------------
def test_a_scene_change_folds_the_old_picture_into_a_line(app):
    for _ in range(3):
        app.update(1 / 60)
        app.draw()
    app.go_play()
    assert app.scene is app.play  # the game is in the new scene at once ...
    app.update(app_module.TUBE_OFF_S * 0.5)
    app.draw()
    screen = pg.display.get_surface()
    w, h = screen.get_size()
    top = sum(sum(screen.get_at((x, 5))[:3]) for x in range(0, w, 40))
    middle = sum(sum(screen.get_at((x, h // 2))[:3]) for x in range(0, w, 40))
    assert middle > top + 500  # ... while the picture is a bright line in the middle
    app.update(app_module.TUBE_OFF_S + app_module.TUBE_ON_S)
    app.draw()  # and then it is the new scene, full size


# --- buttons that move ------------------------------------------------------------------------
def test_a_chosen_button_lights_up_gradually_and_the_frame_glides_to_it():
    fx = hud.ButtonFx()
    rects = {"a": pg.Rect(0, 0, 100, 40), "b": pg.Rect(0, 60, 100, 40)}
    fx.update(0.0, "a", rects, 0.0)
    fx.update(1.0, "a", rects, 1.0)
    assert fx.lit["a"] == 1.0 and fx.frame[1] == pytest.approx(0, abs=0.5)
    fx.update(hud.BTN_EASE_S / 2, "b", rects, 1.0 + hud.BTN_EASE_S / 2)
    assert 0 < fx.lit["b"] < 1 and 0 < fx.lit["a"] < 1  # one fades in as the other fades out
    assert 0 < fx.frame[1] < 60  # the frame is on its way
    fx.press("b", 2.0)
    assert fx.press_k("b", 2.0) == 1.0 and fx.press_k("b", 2.0 + hud.PRESS_S) == 0.0


def test_the_score_rolls_to_its_new_value():
    board = hud.Scoreboard()
    board.flash("shots", 4, 0.0)
    board.flash("shots", 5, 1.0)
    old, k = board.roll("shots", 1.0 + hud.ROLL_S / 2)
    assert old == 4 and 0 < k < 1
    assert board.roll("shots", 1.0 + hud.ROLL_S + 0.01) == (None, 1.0)


# --- Vietnamese marks never push a letter down --------------------------------------------
def _letters() -> set[str]:
    """Every capital and digit the game can show (both languages, also in CAPITAL labels)."""
    chars = set()
    for lang in ("vi", "en"):
        for value in json.loads(
            (ROOT / "lang" / f"{lang}.json").read_text(encoding="utf-8")
        ).values():
            chars |= set(value.upper())
    keep = set()
    for ch in chars:
        below = "̣" in unicodedata.normalize("NFD", ch)  # a dot below: ink under the line
        if (ch.isupper() or ch.isdigit()) and not below and ch not in "QJ":
            keep.add(ch)
    return keep


@pytest.mark.parametrize("face", ["body", "bold", "heavy", "display"])
@pytest.mark.parametrize("track", [0, 2])
def test_every_capital_sits_on_the_same_baseline_as_an_h(face, track):
    pg.font.init()
    for ch in sorted(_letters()):
        surf, base = hud._render(f"H{ch}H", 30, face, (255, 255, 255), track)
        font = fonts.face(30, face)
        w_h = font.size("H")[0]
        x0, x1 = w_h + track, w_h + track + font.size(ch)[0]

        def ink_bottom(a: int, b: int, surf=surf) -> int:
            rows = [y for y in range(surf.get_height()) for x in range(a, b)
                    if surf.get_at((x, y))[3] > 140]  # fmt: skip
            return max(rows)

        assert ink_bottom(0, w_h) == base - 1, (face, track, "H")
        assert abs(ink_bottom(x0 + 1, x1 - 1) - (base - 1)) <= 1, (face, track, hex(ord(ch)))


# --- the menu behind the panel is a picture while the panel is up ----------------------------
def _run(app, seconds):
    for _ in range(round(seconds * 60)):
        app.update(1 / 60)
        app.draw()


def test_with_the_settings_open_the_menu_behind_is_not_drawn_again_every_frame(app, monkeypatch):
    app.sync_view(force=True)
    app.skip_transition()
    panel = app.menu.settings
    for k in (pg.K_DOWN, pg.K_DOWN, pg.K_RETURN):
        app.handle_event(key(k))
    _run(app, 0.6)  # the panel has slid up
    size = pg.display.get_surface().get_size()
    assert panel.is_open and panel.covers_scene(size)
    drawn = []
    monkeypatch.setattr(app.menu.synth, "draw", lambda *a, **k: drawn.append(1))
    _run(app, 0.5)
    assert drawn == []  # the menu is a picture now: its own drawing is skipped
    app.handle_event(key(pg.K_DOWN))  # but the panel itself still answers
    _run(app, 0.3)
    assert panel.sel == 1 and drawn == []


def test_closing_the_settings_brings_the_live_menu_back(app, monkeypatch):
    app.sync_view(force=True)
    app.skip_transition()
    panel = app.menu.settings
    for k in (pg.K_DOWN, pg.K_DOWN, pg.K_RETURN):
        app.handle_event(key(k))
    _run(app, 0.6)
    app.handle_event(key(pg.K_ESCAPE))
    size = pg.display.get_surface().get_size()
    assert panel.is_open and not panel.covers_scene(size)  # closing: the live menu is drawn
    drawn = []
    real = app.menu.synth.draw
    monkeypatch.setattr(app.menu.synth, "draw", lambda *a, **k: (drawn.append(1), real(*a, **k)))
    _run(app, 0.3)
    assert drawn and not panel.is_open
    drawn.clear()
    _run(app, 0.2)
    assert drawn  # and it goes on being drawn every frame
