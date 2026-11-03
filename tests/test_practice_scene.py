"""Practice, round 2 (docs/plans/20261102-luyen-tap.md AC14-AC21): the countdown before a run, the
counter in the side panel, the cells of the side panels, and the Practice button's words."""

import math

import pygame as pg
import pytest

from game import config, i18n
from game.app import App
from game.render import hud
from game.render.layout import to_px
from game.render.view import View
from game.scenes import play_panel as pp

V = View(1.0)
RUN_DT = 1 / 60


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("NEONPOOL_SETTINGS", str(tmp_path / "settings.json"))
    pg.init()
    a = App(pg.display.set_mode(config.LOGICAL_SIZE))
    a.skip_transition()
    yield a
    pg.quit()
    i18n.set_lang("vi")


def key(k):
    return pg.event.Event(pg.KEYDOWN, key=k)


def run(app, seconds):
    for _ in range(round(seconds / RUN_DT)):
        app.update(RUN_DT)


def record_panel(monkeypatch):
    seen = []
    monkeypatch.setattr(hud, "draw_practice_panel", lambda canvas, v, **kw: seen.append(kw))
    return seen


# --- AC14: a new run waits, and nothing may be touched ---------------------------------------
def test_ac14_a_new_run_waits_before_anything_may_be_touched(app):
    app.go_practice()
    scene = app.practice
    assert scene.counting_down and scene._ready_left == config.PRACTICE_READY_S
    assert not scene._can_aim() and not scene._dial_ok()
    cue = scene.world.balls[0]
    cx, cy = (round(v) for v in to_px(cue.x, cue.y))
    app.handle_event(pg.event.Event(pg.MOUSEBUTTONDOWN, pos=(cx, cy), button=1))
    assert not scene.drag.active  # a press on the cue ball starts no aim


def test_ac14_the_wait_is_over_after_its_seconds_and_the_shot_clock_starts_only_then(app):
    app.go_practice()
    scene = app.practice
    run(app, config.PRACTICE_READY_S - 0.5)
    assert scene.counting_down and scene._shot_left == config.PRACTICE_SHOT_S  # not ticking
    run(app, 0.7)
    assert not scene.counting_down and scene._can_aim()
    assert config.PRACTICE_SHOT_S - 0.5 < scene._shot_left < config.PRACTICE_SHOT_S


# --- AC15: the ball to hit is shown only when the wait is over -------------------------------
def test_ac15_the_ball_to_hit_is_shown_only_after_the_wait(app, monkeypatch):
    seen = record_panel(monkeypatch)
    app.go_practice()
    canvas = pg.display.get_surface()
    app.practice.draw(canvas)
    run(app, config.PRACTICE_READY_S + 0.2)
    app.practice.draw(canvas)
    during, after = seen
    assert not during["target_shown"] and during["counting_down"]
    assert during["count"] == math.ceil(config.PRACTICE_READY_S)  # the counter shows the wait
    assert after["target_shown"] and not after["counting_down"]
    assert (
        after["target"] == app.practice.rules.target and after["count"] == config.PRACTICE_SHOT_S
    )  # ... then the clock


def test_ac15_no_ring_is_drawn_round_the_ball_to_hit(app):
    from game.scenes.practice import PracticeScene

    assert "_draw_cues" not in vars(PracticeScene)  # the panel shows the ball; the table does not


# --- AC16: every second of the count has its own sound, the start rings -----------------------
def test_ac16_every_second_of_the_count_sounds_and_the_start_rings(app, monkeypatch):
    counts, rings, warns = [], [], []
    monkeypatch.setattr(app.audio, "play_count", lambda: counts.append(1))
    monkeypatch.setattr(app.audio, "play_notice", lambda: rings.append(1))
    monkeypatch.setattr(app.audio, "play_clock_warn", lambda left: warns.append(left))
    app.go_practice()
    run(app, config.PRACTICE_READY_S + 0.5)
    assert len(counts) == config.PRACTICE_READY_S and rings == [1] and warns == []


def test_ac16_no_aim_hint_under_the_table_while_counting_then_the_hint(app):
    app.go_practice()
    assert app.practice._hint_words() is None
    run(app, config.PRACTICE_READY_S + 0.5)
    assert app.practice._hint_words() == i18n.t("hud.hint")
    app.handle_event(key(pg.K_r))
    assert app.practice._hint_words() is None


# --- AC17: every new run starts with the wait --------------------------------------------------
def test_ac17_a_restart_and_a_new_run_from_the_menu_wait_again(app):
    app.go_practice()
    run(app, config.PRACTICE_READY_S + 1.0)
    assert not app.practice.counting_down
    app.handle_event(key(pg.K_r))  # restart
    assert app.practice.counting_down and app.practice._ready_left == config.PRACTICE_READY_S
    run(app, config.PRACTICE_READY_S + 1.0)
    app.go_menu()
    app.go_practice()  # a new run chosen at the mode step
    assert app.practice.counting_down
    assert app.practice.rules.shots == 0 and app.practice.rules.phase == "playing"


def test_ac17_a_run_that_has_ended_is_not_shown_again_when_practice_is_chosen_again(app):
    app.go_practice()
    app.practice.rules.lives = 1
    app.practice.rules.timeout()  # the last life: the run is lost
    assert app.practice.rules.phase == "lost"
    app.go_menu()
    app.go_practice()
    assert app.practice.rules.phase == "playing" and app.practice.counting_down


# --- AC18: the help card stops Practice like it stops Free play ------------------------------
def test_ac18_the_help_card_holds_the_wait_and_the_shot_clock(app):
    app.go_practice()
    scene = app.practice
    run(app, 1.0)
    app.open_help()
    ready = scene._ready_left
    run(app, 2.0)
    assert scene._ready_left == ready  # still waiting behind the card
    app.help.close()
    run(app, config.PRACTICE_READY_S)
    assert not scene.counting_down
    app.open_help()
    left = scene._shot_left
    run(app, 2.0)
    assert scene._shot_left == left


# --- AC19: the cells of the side panels sit evenly -------------------------------------------
def test_ac19_the_two_cells_of_a_row_mirror_each_other_about_the_panel_centre():
    left, right = hud.CELL_AXES
    assert left - hud.PANEL_X0 == hud.PANEL_X1 - right == hud.CELL_INSET
    assert (left + right) / 2 == hud.PANEL_CX


@pytest.mark.parametrize("lang", ["vi", "en"])
def test_ac19_every_cell_word_and_number_fits_its_cell(lang):
    i18n.set_lang(lang)
    canvas = pg.Surface((400, 100))
    width = 2 * hud.CELL_INSET
    for name in ("hud.shots", "hud.fouls", "practice.streak", "practice.best",
                 "practice.target", "practice.count"):  # fmt: skip
        assert hud.label_centered(canvas, V, i18n.t(name), (200, 20)).w <= width, (lang, name)
    assert hud.text_width(V, i18n.t("practice.cleared"), hud.CELL_WORD_SIZE, True) <= width
    assert hud.digits_width(3, 32) <= width  # the widest number of a cell: the shots of Free play


@pytest.mark.parametrize("lang", ["vi", "en"])
def test_ac19_a_centred_label_is_centred_on_its_axis(lang):
    i18n.set_lang(lang)
    canvas = pg.Surface((400, 100))
    for name in ("practice.streak", "practice.target", "hud.shots"):
        rect = hud.label_centered(canvas, V, i18n.t(name), (200, 20))
        assert abs(rect.centerx - 200) <= 1, (lang, name, rect)


# --- AC20: the words of the Practice button keep clear of its arrow ---------------------------
@pytest.mark.parametrize("lang", ["vi", "en"])
def test_ac20_no_description_of_a_play_button_reaches_the_arrow(lang):
    i18n.set_lang(lang)
    rect = pp.RECTS[pp.MODE]["practice"]
    arrow_right, gap = 24, 16  # the arrow of a lit button sits at x + 18, 6 wide
    room = rect.w - 2 * (arrow_right + gap)  # the line is centred: the same room on both sides
    names = [n for n in i18n.table(lang) if n.startswith("play.") and n.endswith("_sub")]
    assert len(names) >= 4
    for name in names:
        assert hud.text_width(V, i18n.t(name), 13) <= room, (lang, name)


# --- AC21: three lives (round 4, GAME_DESIGN lần 33) ------------------------------------------
def start(app):
    app.go_practice()
    run(app, config.PRACTICE_READY_S + 0.5)
    return app.practice


def whiff(app, scene):
    """A soft shot away from the balls: it touches nothing and pots nothing."""
    from game.physics import Shot

    scene.fire(Shot(math.pi, 0.1, 0.0))
    for _ in range(60 * 30):
        if not scene._live:
            return
        app.update(RUN_DT)
    raise AssertionError("the balls never stopped")


def test_ac21_a_miss_costs_a_life_shows_it_and_the_run_goes_on(app, monkeypatch):
    seen = record_panel(monkeypatch)
    scene = start(app)
    whiff(app, scene)
    assert scene.rules.lives == config.PRACTICE_LIVES - 1 and scene.rules.phase == "playing"
    assert scene._notice == ("foul", "practice.miss")
    scene.draw(pg.display.get_surface())
    assert seen[-1]["lives"] == config.PRACTICE_LIVES - 1
    assert scene._can_aim()  # nothing is in hand after a plain miss


def test_ac21_the_cue_ball_in_a_pocket_costs_a_life_and_is_put_back_in_hand(app):
    scene = start(app)
    scene.world.balls[0].in_play = False  # as if it had gone into a pocket this shot
    scene.rules.on_shot()
    scene._live = True
    scene.rules.on_events(
        [__import__("game.physics", fromlist=["BallPocketed"]).BallPocketed(0, 0)]
    )
    scene._end_shot()
    assert scene.rules.lives == config.PRACTICE_LIVES - 1 and scene.rules.cue_in_hand
    assert scene.world.balls[0].in_play  # back on the table, to be placed
    assert not scene._can_aim() and scene._holding()


def test_ac21_three_misses_lose_the_run_and_the_card_says_why(app):
    scene = start(app)
    for _ in range(config.PRACTICE_LIVES):
        assert scene.rules.phase == "playing"
        whiff(app, scene)
    assert scene.rules.phase == "lost" and scene._lost_words() == i18n.t(
        "practice.out_of_lives", why=i18n.t("practice.miss")
    )


def test_ac21_the_clock_running_out_costs_a_life_and_starts_a_fresh_clock(app):
    scene = start(app)
    run(app, config.PRACTICE_SHOT_S + 0.5)
    assert scene.rules.lives == config.PRACTICE_LIVES - 1 and scene.rules.phase == "playing"
    assert scene._shot_left > config.PRACTICE_SHOT_S - 1.0
    assert scene._notice == ("foul", "practice.lost_timeout")


# --- AC24 (lần 37): a blocked target is swapped, and the table says so for a few seconds -------
def test_ac24_a_target_blocked_by_a_moved_ball_is_swapped_with_a_hint_line(app):
    scene = start(app)
    scene.rules.pocketed = set(range(1, 16)) - {6, 7, 8}
    scene.rules.target = 6
    balls = scene.world.balls
    balls[0].x, balls[0].y, balls[0].in_play = 0.3, 0.3, True  # the cue ball
    balls[8].x, balls[8].y, balls[8].in_play = 0.6, 0.3, True  # sits between the cue and the 6
    balls[6].x, balls[6].y, balls[6].in_play = 0.9, 0.3, True  # directly behind the 8
    balls[7].x, balls[7].y, balls[7].in_play = 0.3, 0.9, True  # a clear line
    scene.rules.on_shot()
    scene._live = True
    scene._end_shot()  # a miss: the 6 stayed down, now blocked by the 8
    assert scene.rules.target_swapped and scene.rules.target in (7, 8)
    assert scene._swap_left == config.NOTICE_S
    assert scene._hint_words() == i18n.t("practice.target_swapped")
    run(app, config.NOTICE_S + 0.5)
    assert scene._swap_left == 0.0 and scene._hint_words() != i18n.t("practice.target_swapped")


# --- AC22: the dark screen of the wait, the lives above the panel (round 5, lần 34) -----------
def test_ac22_the_whole_screen_is_dark_during_the_wait_with_the_words_in_the_middle(
    app, monkeypatch
):
    dims, words = [], []
    monkeypatch.setattr(hud, "dim_screen", lambda canvas, k: dims.append(k))
    monkeypatch.setattr(hud, "glow_text", lambda c, v, s, *a, **kw: words.append(s))
    app.go_practice()
    canvas = pg.display.get_surface()
    app.practice.draw(canvas)
    assert dims == [1.0] and words[-1] == i18n.t("practice.counting")
    run(app, config.PRACTICE_READY_S + config.PRACTICE_DIM_FADE_S + 0.5)
    dims.clear()
    words.clear()
    app.practice.draw(canvas)
    assert dims == [] and i18n.t("practice.counting") not in words  # back to normal


def test_ac22_the_dark_clears_gradually_when_the_wait_is_over(app):
    app.go_practice()
    run(app, config.PRACTICE_READY_S + config.PRACTICE_DIM_FADE_S / 2)
    assert 0.0 < app.practice._dim_k < 1.0


def test_ac22_the_lives_are_drawn_above_the_side_panel_not_inside_it():
    canvas = pg.Surface(config.LOGICAL_SIZE)
    hud.draw_lives(canvas, V, 2)
    lit = pg.mask.from_threshold(canvas, (0, 0, 0), (1, 1, 1))
    lit.invert()
    box = lit.get_bounding_rects()
    assert box
    top = min(r.top for r in box)
    bottom = max(r.bottom for r in box)
    left, right = min(r.left for r in box), max(r.right for r in box)
    from game.render.layout import PANEL_W, PANEL_X, PANEL_Y

    assert 0 <= top and bottom < PANEL_Y  # above the panel's frame
    assert left >= PANEL_X and right <= PANEL_X + PANEL_W  # over its width
    assert abs((left + right) / 2 - hud.PANEL_CX) <= 2  # centred on it


def test_ac22_the_leave_card_has_its_words_in_both_languages():
    for lang in ("vi", "en"):
        i18n.set_lang(lang)
        words = [i18n.t(k) for k in ("leave.title", "leave.line", "leave.stay", "leave.leave")]
        assert all(w and not w.startswith("leave.") for w in words), lang
