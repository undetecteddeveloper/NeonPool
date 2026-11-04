"""Practice, round 2 (docs/plans/20261102-luyen-tap.md AC14-AC21): the countdown before a run, the
counter in the side panel, the cells of the side panels, and the Practice button's words."""

import math

import pygame as pg
import pytest

from game import config, i18n
from game.app import App
from game.physics import BallPocketed
from game.render import draw, hud
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


def lives_words(why_key):
    """The card's why when the last life went: two lines, the headline and the last shot's cause."""
    return f"{i18n.t('practice.out_of_lives')}\n{i18n.t('practice.last_one', why=i18n.t(why_key))}"


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


def test_ac15_no_ring_is_drawn_round_the_ball_to_hit(app, monkeypatch):
    rings = []
    monkeypatch.setattr(draw, "draw_pocket_call", lambda *a: rings.append(a))
    monkeypatch.setattr(draw, "draw_ring", lambda *a, **kw: rings.append(a))
    app.go_practice()
    run(app, config.PRACTICE_READY_S + 0.5)
    app.practice.rules.target = 6  # (a target is called: the panel shows the ball; the table
    app.practice.draw(pg.display.get_surface())  # does not, and no pocket is called in this drill)
    assert rings == []


# --- AC16: every second of the count has its own sound, the start rings -----------------------
def test_ac16_every_second_of_the_count_sounds_and_the_start_rings(app, monkeypatch):
    counts, rings, warns = [], [], []
    monkeypatch.setattr(app.audio, "play_count", lambda: counts.append(1))
    monkeypatch.setattr(app.audio, "play_notice", lambda: rings.append(1))
    monkeypatch.setattr(app.audio, "play_clock_warn", lambda left: warns.append(left))
    app.go_practice()
    run(app, config.PRACTICE_READY_S + 0.5)
    assert len(counts) == config.PRACTICE_READY_S and rings == [1] and warns == []


def test_ac16_no_hint_under_the_table_while_counting_then_the_breaking_hint(app):
    app.go_practice()
    assert app.practice._hint_words() is None
    run(app, config.PRACTICE_READY_S + 0.5)
    # round 38: no target yet (the break has not settled), so this slot explains why instead
    assert app.practice._hint_words() == i18n.t("practice.breaking")
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


# --- AC20 / AC34 / AC39: the words of a play button keep clear of its arrow -------------------
def _room(rect):
    arrow_right, gap = 24, 16  # the arrow of a lit button sits at x + 18, 6 wide
    return rect.w - 2 * (arrow_right + gap)  # the line is centred: the same room on both sides


@pytest.mark.parametrize("lang", ["vi", "en"])
def test_ac20_no_description_of_a_play_button_reaches_the_arrow(lang):
    i18n.set_lang(lang)
    rect = pp.RECTS[pp.MODE]["practice"]
    names = [n for n in i18n.table(lang) if n.startswith("play.") and n.endswith("_sub")]
    assert len(names) >= 4
    for name in names:
        assert hud.text_width(V, i18n.t(name), 13) <= _room(rect), (lang, name)


@pytest.mark.parametrize("lang", ["vi", "en"])
def test_ac34_the_words_of_the_three_runs_fit_their_buttons(lang):
    i18n.set_lang(lang)
    for mode in config.PRACTICE_MODES:
        rect = pp.RECTS[pp.PRACTICE][mode]
        name, sub = i18n.t(f"practice.mode.{mode}"), i18n.t(f"practice.mode.{mode}_sub")
        assert not name.startswith("practice.mode"), (lang, mode)  # (a key shown is a bug)
        assert not sub.startswith("practice.mode"), (lang, mode)
        assert hud.text_width(V, sub, 13) <= _room(rect), (lang, mode)
        assert hud.text_width(V, name, 20, True) <= _room(rect), (lang, mode)


def open_practice_step(app):
    panel = app.menu.play_panel
    panel.open()
    panel._goto(pp.MODE)
    app.handle_event(key(pg.K_DOWN))  # Practice
    app.handle_event(key(pg.K_RETURN))
    return panel


def test_ac34_practice_opens_a_step_with_three_runs_not_the_table(app):
    panel = open_practice_step(app)
    assert panel.step == pp.PRACTICE and app.scene is app.menu
    assert pp.ITEMS[pp.PRACTICE] == ("ghost", "call", "sprint", "back")
    assert panel.sel == 0 and panel.is_open


@pytest.mark.parametrize("mode", config.PRACTICE_MODES)
def test_ac34_each_button_starts_its_own_run(app, mode):
    panel = open_practice_step(app)
    panel._choose(pp.ITEMS[pp.PRACTICE].index(mode))
    app.handle_event(key(pg.K_RETURN))  # the run: its Level step opens, Start is chosen
    assert panel.step == pp.LEVEL and panel._item() == "start" and app.scene is app.menu
    app.handle_event(key(pg.K_RETURN))  # Start
    assert app.scene is app.practice and not panel.is_open
    assert app.practice.mode == mode and app.practice.rules.mode == mode
    assert app.practice.counting_down  # a fresh run


@pytest.mark.parametrize("mode", config.PRACTICE_MODES)
def test_ac34_a_click_on_a_run_button_starts_it(app, mode):
    panel = open_practice_step(app)
    panel.k = 1.0
    app.handle_event(
        pg.event.Event(pg.MOUSEBUTTONDOWN, pos=pp.RECTS[pp.PRACTICE][mode].center, button=1)
    )
    assert panel.step == pp.LEVEL and panel.mode == mode  # the Level step of that run
    app.handle_event(
        pg.event.Event(pg.MOUSEBUTTONDOWN, pos=panel._rects()["start"].center, button=1)
    )
    assert app.scene is app.practice and app.practice.mode == mode


def test_ac34_back_and_esc_go_back_one_step_to_the_mode_step(app):
    panel = open_practice_step(app)
    panel._choose(pp.ITEMS[pp.PRACTICE].index("back"))
    app.handle_event(key(pg.K_RETURN))
    assert panel.step == pp.MODE and pp.ITEMS[pp.MODE][panel.sel] == "practice"
    assert app.scene is app.menu
    app.handle_event(key(pg.K_RETURN))  # Practice again
    assert panel.step == pp.PRACTICE
    app.handle_event(key(pg.K_ESCAPE))
    assert panel.step == pp.MODE and panel.is_open and app.scene is app.menu


def test_ac34_free_play_still_goes_straight_to_the_table(app):
    panel = app.menu.play_panel
    panel.open()
    panel._goto(pp.MODE)
    app.handle_event(key(pg.K_RETURN))  # Free play, the first button
    assert app.scene is app.play and not panel.is_open


def test_ac34_a_run_started_again_from_the_panel_keeps_no_old_mode(app):
    open_practice_step(app)
    app.handle_event(key(pg.K_DOWN))
    app.handle_event(key(pg.K_RETURN))  # Call the Pocket
    app.handle_event(key(pg.K_RETURN))  # Start
    assert app.practice.mode == "call"
    app.go_menu()
    open_practice_step(app)
    app.handle_event(key(pg.K_RETURN))  # Beat the Ghost
    app.handle_event(key(pg.K_RETURN))  # Start
    assert app.practice.mode == "ghost" and app.practice.rules.mode == "ghost"


# --- AC45: the Level step (Easy / Hard) and the bests that follow the level ----------------------
def open_level_step(app, mode="ghost"):
    panel = open_practice_step(app)
    panel._choose(pp.ITEMS[pp.PRACTICE].index(mode))
    app.handle_event(key(pg.K_RETURN))
    assert panel.step == pp.LEVEL
    return panel


def click(app, pos):
    app.handle_event(pg.event.Event(pg.MOUSEBUTTONDOWN, pos=pos, button=1))


def test_ac45_the_level_step_has_the_row_then_start_then_back(app):
    panel = open_level_step(app, "call")
    assert pp.ITEMS[pp.LEVEL] == ("level", "start", "back")
    assert panel.title() == i18n.t("practice.mode.call") and panel.level == "easy"  # the first time
    assert panel._item() == "start"  # Enter begins; the row is a setting, not what it starts
    app.handle_event(key(pg.K_UP))
    assert panel._item() == "level"


@pytest.mark.parametrize("mode", config.PRACTICE_MODES)
@pytest.mark.parametrize("level", config.PRACTICE_LEVELS)
def test_ac45_start_begins_the_run_at_the_level_shown_and_remembers_it(app, mode, level):
    panel = open_level_step(app, mode)
    panel.level = "hard" if level == "easy" else "easy"
    app.handle_event(key(pg.K_UP))  # the row
    app.handle_event(key(pg.K_RIGHT if level == "hard" else pg.K_LEFT))
    assert panel.level == level
    click(app, panel._rects()["start"].center)
    assert app.scene is app.practice and not panel.is_open
    assert (app.practice.mode, app.practice.level) == (mode, level)
    assert app.practice.rules.mode == mode and app.practice.rules.level == level
    assert app.settings.practice_level == level  # kept for the next time
    assert settings_file_level(app) == level


def settings_file_level(app):
    import json
    import os

    with open(os.environ["NEONPOOL_SETTINGS"], encoding="utf-8") as f:
        return json.load(f)["practice_level"]


def test_ac45_the_next_visit_shows_the_level_played_last(app):
    app.change_settings(practice_level="hard")
    panel = open_level_step(app)
    assert panel.level == "hard"
    app.handle_event(key(pg.K_RETURN))  # Start
    app.go_menu()
    app.menu.play_panel.dismiss()
    assert open_level_step(app).level == "hard"


def test_ac45_the_row_changes_by_arrows_keys_enter_and_clicks_but_never_starts(app):
    panel = open_level_step(app)
    app.handle_event(key(pg.K_UP))
    assert panel.level == "easy"
    app.handle_event(key(pg.K_RIGHT))
    assert panel.level == "hard"
    app.handle_event(key(pg.K_a))
    assert panel.level == "easy"
    app.handle_event(key(pg.K_d))
    assert panel.level == "hard"
    app.handle_event(key(pg.K_RETURN))  # Enter on the row changes it, as on Settings' rows
    assert panel.level == "easy" and panel.step == pp.LEVEL and app.scene is app.menu
    row = panel._rects()["level"]
    click(app, (row.right - hud.CHOOSER_FROM_RIGHT + hud.CHOOSER_HALF, row.centery))  # the > arrow
    assert panel.level == "hard"
    click(app, (row.right - hud.CHOOSER_FROM_RIGHT - hud.CHOOSER_HALF, row.centery))  # the < arrow
    assert panel.level == "easy" and app.scene is app.menu


def test_ac45_back_and_esc_return_to_the_run_that_was_pressed_and_start_nothing(app):
    panel = open_level_step(app, "sprint")
    click(app, panel._rects()["back"].center)
    assert panel.step == pp.PRACTICE and panel._item() == "sprint" and app.scene is app.menu
    app.handle_event(key(pg.K_RETURN))
    app.handle_event(key(pg.K_ESCAPE))
    assert panel.step == pp.PRACTICE and panel._item() == "sprint" and panel.is_open
    assert app.settings.practice_level == "easy"  # nothing was saved


def test_ac45_a_new_run_from_the_card_or_r_keeps_mode_and_level(app):
    scene = start_mode(app, "call", "easy")
    app.handle_event(key(pg.K_r))
    assert (scene.mode, scene.level, scene.rules.level) == ("call", "easy", "easy")
    scene.new_game()
    assert (scene.mode, scene.level, scene.rules.level) == ("call", "easy", "easy")
    app.go_practice("sprint")  # no level given: the one last played (here the settings')
    assert scene.level == app.settings.practice_level


def test_ac45_a_run_with_no_level_given_takes_the_one_in_the_settings(app):
    app.change_settings(practice_level="hard")
    app.go_practice("ghost")
    assert app.practice.level == "hard" and app.practice.rules.level == "hard"
    app.go_practice("ghost", "easy")
    assert app.practice.level == "easy" and app.practice.rules.level == "easy"


@pytest.mark.parametrize("mode", config.PRACTICE_MODES)
def test_ac45_the_best_follows_the_level_and_one_does_not_cover_the_other(app, mode):
    from game import settings

    scene = start_mode(app, mode, "hard")
    lose(scene, 6)
    scene = start_mode(app, mode, "easy")
    lose(scene, 2)
    assert settings.best_for(app.settings, mode, "hard") == 6  # Easy's 2 did not touch Hard's 6
    assert settings.best_for(app.settings, mode, "easy") == 2
    scene = start_mode(app, mode, "easy")
    lose(scene, 9)
    assert settings.best_for(app.settings, mode, "easy") == 9
    assert settings.best_for(app.settings, mode, "hard") == 6


@pytest.mark.parametrize("level", config.PRACTICE_LEVELS)
def test_ac45_the_panel_and_the_card_read_the_best_of_their_level(app, monkeypatch, level):
    app.change_settings(practice_best=3, practice_best_easy=8)
    seen = record_panel(monkeypatch)
    card = []
    monkeypatch.setattr(hud, "draw_result", lambda canvas, v, **kw: card.append(kw))
    scene = start_mode(app, "ghost", level)
    scene.draw(pg.display.get_surface())
    expected = {"hard": 3, "easy": 8}[level]
    assert seen[-1]["best"] == expected
    lose(scene, 1)
    run(app, 4.0)
    scene.draw(pg.display.get_surface())
    assert card[-1]["rows"][1] == (i18n.t("practice.best"), expected)


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
    whiff(app, scene)  # the break: free, no target yet (round 38)
    whiff(app, scene)  # a real miss now that a target is assigned
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
    whiff(app, scene)  # the break: free, no target yet (round 38)
    for _ in range(config.PRACTICE_LIVES):
        assert scene.rules.phase == "playing"
        whiff(app, scene)
    assert scene.rules.phase == "lost" and scene._lost_words() == lives_words("practice.miss")


def test_ac21_the_clock_running_out_costs_a_life_and_starts_a_fresh_clock(app):
    scene = start(app)
    run(app, config.PRACTICE_SHOT_S + 0.5)
    assert scene.rules.lives == config.PRACTICE_LIVES - 1 and scene.rules.phase == "playing"
    assert scene._shot_left > config.PRACTICE_SHOT_S - 1.0
    assert scene._notice == ("foul", "practice.lost_timeout")


# --- AC24 / AC26 (lần 37, 39): the notice under the table is ONE card, never more than two lines
def told(monkeypatch, lines, in_hand=None):
    def stub(balls, n, *, cue_in_hand=False, **_):
        return (in_hand if cue_in_hand and in_hand is not None else lines).get(n, 0)

    monkeypatch.setattr("game.rules.practice.pot_lines", stub)


def three_balls(scene):
    scene.rules.pocketed = set(range(1, 16)) - {6, 7, 8}
    balls = scene.world.balls
    for n in range(1, 16):
        balls[n].in_play = n in (6, 7, 8)
    for n, (x, y) in {0: (0.3, 0.3), 8: (0.6, 0.3), 6: (0.9, 0.3), 7: (0.3, 0.9)}.items():
        balls[n].x, balls[n].y, balls[n].vx, balls[n].vy = x, y, 0.0, 0.0
    balls[0].in_play = True


def miss(scene):
    scene.rules.on_shot()
    scene._live = True
    scene._end_shot()


def test_ac24_a_swap_shares_the_notice_with_the_reason_and_never_overlaps_it(app, monkeypatch):
    told(monkeypatch, {7: 1, 8: 1})  # the held 6 has lost every pot line
    scene = start(app)
    three_balls(scene)
    scene.rules.target = 6
    miss(scene)
    assert scene.rules.target_swapped and scene.rules.target in (7, 8)
    words = [w for w, _ in scene._banner_lines()]
    assert words == [i18n.t("practice.miss"), i18n.t("practice.target_swapped")]
    assert scene._hint_words() is None  # nothing else hangs in the strip under the table
    run(app, config.NOTICE_S + 0.5)
    assert scene._banner_lines() == [] and scene._swap_left == 0.0


def test_ac26_no_line_from_here_gives_the_cue_ball_in_hand_and_says_so_in_the_same_card(
    app, monkeypatch
):
    told(monkeypatch, {}, in_hand={6: 1})
    scene = start(app)
    three_balls(scene)
    scene.rules.target = 6
    miss(scene)
    assert scene.rules.hand_given and scene.rules.target == 6
    assert scene._holding() and not scene._can_aim()  # it can be picked up and put down
    words = [w for w, _ in scene._banner_lines()]
    assert words == [i18n.t("practice.miss"), i18n.t("practice.hand_given")]
    assert i18n.t("notice.hand_drag") not in words  # (the given line says what to do)
    assert scene.rules.lives == config.PRACTICE_LIVES - 1  # only the miss cost a life


def test_ac24_the_card_never_has_more_than_two_lines_even_for_a_scratch_and_a_swap(
    app, monkeypatch
):
    told(monkeypatch, {7: 1, 8: 1})
    scene = start(app)
    three_balls(scene)
    scene.rules.target = 6
    scene.rules.on_shot()
    scene._live = True
    scene.rules.on_events([BallPocketed(0, 0)])
    scene._end_shot()  # the cue ball in a pocket AND the held 6 without a line
    assert scene.rules.cue_in_hand and scene.rules.target_swapped
    words = [w for w, _ in scene._banner_lines()]
    assert words == [i18n.t("foul.scratch"), i18n.t("practice.target_swapped")]


def test_ac24_the_card_fits_in_the_strip_under_the_table_at_the_smallest_window(app, monkeypatch):
    told(monkeypatch, {}, in_hand={6: 1})
    scene = start(app)
    three_balls(scene)
    scene.rules.target = 6
    miss(scene)
    for lang in ("vi", "en"):
        i18n.set_lang(lang)
        width = max(hud.text_width(V, w, 16, True) for w, _ in scene._banner_lines()) + 44
        assert width < 600  # well inside the width of the table (about 970 px)
    assert len(scene._banner_lines()) * 24 + hud.BANNER_PAD + 12 <= 98  # the free strip's height


def test_ac25_the_breaking_line_gives_way_to_a_notice_hanging_in_the_same_strip(app):
    app.go_practice()
    run(app, config.PRACTICE_READY_S + 0.5)
    scene = app.practice
    assert scene._hint_words() == i18n.t("practice.breaking")
    scene._timeout()  # stalled past the clock before the break: a life and a notice
    assert scene._banner_lines() and scene._hint_words() is None  # one at a time
    run(app, config.NOTICE_S + 0.5)
    assert scene._hint_words() == i18n.t("practice.breaking")


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


# --- the drills (docs/plans/20261104-luyen-tap-da-che-do.md AC35-AC39) ----------------------------
def start_mode(app, mode, level="hard"):
    app.go_practice(mode, level)
    run(app, config.PRACTICE_READY_S + 0.5)
    return app.practice


def ring_pixels(scene, pocket_index):
    """How many pixels around a pocket differ from the same frame with no pocket called."""
    canvas = pg.display.get_surface()
    scene.draw(canvas)
    with_ring = canvas.copy()
    keep, scene.rules.pocket = scene.rules.pocket, None
    scene.draw(canvas)
    scene.rules.pocket = keep
    x, y, r = config.POCKETS[pocket_index]
    cx, cy = to_px(x, y)
    reach = round(r * config.PX_PER_M) + 20
    box = pg.Rect(round(cx) - reach, round(cy) - reach, 2 * reach, 2 * reach).clip(
        canvas.get_rect()
    )
    return sum(
        with_ring.get_at((px, py)) != canvas.get_at((px, py))
        for px in range(box.left, box.right)
        for py in range(box.top, box.bottom)
    )


# --- AC35: Call the Pocket -----------------------------------------------------------------------
def test_ac35_the_called_pocket_has_a_ring_and_no_other_pocket_does(app):
    scene = start_mode(app, "call")
    scene.rules.target, scene.rules.pocket = 6, 3
    assert ring_pixels(scene, 3) > 100  # a ring about the mouth of the pocket
    assert ring_pixels(scene, 0) == 0 and ring_pixels(scene, 4) == 0  # ... and only there


def test_ac35_the_ring_is_drawn_only_while_a_pocket_is_called_and_the_run_is_on(app, monkeypatch):
    rings = []
    monkeypatch.setattr(
        draw, "draw_pocket_call", lambda canvas, v, pocket, clock: rings.append(pocket)
    )
    canvas = pg.display.get_surface()
    app.go_practice("call")
    app.practice.rules.pocket = 2
    app.practice.draw(canvas)
    assert rings == []  # the wait: nothing is shown yet
    run(app, config.PRACTICE_READY_S + 0.5)
    app.practice.rules.pocket = None
    app.practice.draw(canvas)
    assert rings == []  # no pocket is called (the break)
    app.practice.rules.pocket = 2
    app.practice.draw(canvas)
    assert rings == [2]
    app.practice.rules.phase = "lost"
    app.practice.draw(canvas)
    assert rings == [2]  # the run is over


def test_ac35_the_ring_is_never_drawn_in_the_other_drills(app, monkeypatch):
    rings = []
    monkeypatch.setattr(draw, "draw_pocket_call", lambda *a: rings.append(a))
    for mode in ("ghost", "sprint"):
        scene = start_mode(app, mode)
        scene.rules.target = 6
        scene.draw(pg.display.get_surface())
    assert rings == []


def test_ac35_the_hint_under_the_table_says_which_pocket_counts(app):
    scene = start_mode(app, "call")
    assert scene._hint_words() == i18n.t("practice.breaking")  # (nothing is called yet)
    scene.rules.target, scene.rules.pocket = 6, 3
    assert scene._hint_words() == i18n.t("practice.call_hint")
    scene._notice, scene._notice_left = ("foul", "practice.miss"), 3.0
    assert scene._hint_words() is None  # a notice in the same strip wins
    assert start_mode(app, "ghost")._hint_words() == i18n.t("practice.breaking")


def aim_at(scene, *, target=6, pocket=2):
    three_balls(scene)
    scene.rules.target, scene.rules.pocket = target, pocket
    scene.rules._ask = (False, config.PRACTICE_LINE_MARGIN_M)


def pockets_told(monkeypatch, table):
    monkeypatch.setattr(
        "game.rules.practice.pot_pockets", lambda balls, n, **_: list(table.get(n, []))
    )


def test_ac35_the_target_in_another_pocket_is_a_miss_with_its_own_words(app, monkeypatch):
    pockets_told(monkeypatch, {7: [1], 8: [1]})
    scene = start_mode(app, "call")
    aim_at(scene)
    scene.rules.on_shot()
    scene._live = True
    scene.rules.on_events([BallPocketed(6, 5)])  # the 6 went down, but not in the pocket 2
    scene._end_shot()
    assert scene.rules.lives == config.PRACTICE_LIVES - 1 and scene.rules.streak == 0
    assert scene._notice == ("foul", "practice.miss_pocket")


def test_ac35_the_card_says_the_wrong_pocket_when_that_was_the_last_life(app, monkeypatch):
    pockets_told(monkeypatch, {7: [1], 8: [1]})
    scene = start_mode(app, "call")
    aim_at(scene)
    scene.rules.lives = 1
    scene.rules.on_shot()
    scene._live = True
    scene.rules.on_events([BallPocketed(6, 5)])
    scene._end_shot()
    assert scene.rules.phase == "lost"
    assert scene._lost_words() == lives_words("practice.miss_pocket")


def test_ac35_a_plain_miss_in_this_drill_keeps_the_usual_words(app, monkeypatch):
    pockets_told(monkeypatch, {6: [2], 7: [1], 8: [1]})
    scene = start_mode(app, "call")
    aim_at(scene)
    miss(scene)
    assert scene._notice == ("foul", "practice.miss")


def test_ac35_a_pocket_that_lost_its_line_says_pocket_changed_not_ball_changed(app, monkeypatch):
    pockets_told(monkeypatch, {6: [3], 7: [1], 8: [1]})  # the 6 stays, its pocket 2 is blocked
    scene = start_mode(app, "call")
    aim_at(scene)
    miss(scene)
    assert scene.rules.target == 6 and scene.rules.pocket == 3 and scene.rules.target_swapped
    assert [w for w, _ in scene._banner_lines()] == [
        i18n.t("practice.miss"),
        i18n.t("practice.pocket_swapped"),
    ]


def test_ac35_a_ball_that_lost_every_line_says_ball_changed(app, monkeypatch):
    pockets_told(monkeypatch, {7: [1], 8: [1]})
    scene = start_mode(app, "call")
    aim_at(scene)
    miss(scene)
    assert scene.rules.target in (7, 8) and scene.rules.target_swapped
    assert i18n.t("practice.target_swapped") in [w for w, _ in scene._banner_lines()]


def test_ac35_the_called_ring_is_drawn_by_the_shared_component_at_the_pockets_place():
    canvas = pg.Surface(config.LOGICAL_SIZE, pg.SRCALPHA)
    draw.draw_pocket_call(canvas, V, 5, 0.0)
    box = canvas.get_bounding_rect()
    x, y, r = config.POCKETS[5]
    cx, cy = to_px(x, y)
    assert abs(box.centerx - cx) <= 1 and abs(box.centery - cy) <= 1
    assert box.w >= 2 * r * config.PX_PER_M  # at least the size of the mouth


# --- AC36: Sprint ------------------------------------------------------------
def test_ac36_the_clock_runs_only_while_the_player_may_aim(app):
    from game.physics import Shot

    app.go_practice("sprint")
    scene = app.practice
    run(app, config.PRACTICE_READY_S - 0.5)
    assert scene.rules.time_left == config.SPRINT_START_S  # the wait is not on the clock
    run(app, 1.5)
    assert config.SPRINT_START_S - 1.2 < scene.rules.time_left < config.SPRINT_START_S - 0.8
    before = scene.rules.time_left
    scene.fire(Shot(math.pi, 0.1, 0.0))
    run(app, 0.5)
    assert scene._live and scene.rules.time_left == before  # the balls rolling: stopped
    for _ in range(60 * 30):
        if not scene._live:
            break
        app.update(RUN_DT)
    assert not scene._live and before - 2 * RUN_DT < scene.rules.time_left <= before
    before = scene.rules.time_left
    run(app, 1.0)
    assert scene.rules.time_left < before  # aiming again: it runs


def test_ac36_the_clock_stops_in_hand_and_behind_the_help_card(app):
    scene = start_mode(app, "sprint")
    scene.rules.cue_in_hand = True
    left = scene.rules.time_left
    run(app, 2.0)
    assert scene.rules.time_left == left  # placing the cue ball: stopped
    scene.rules.cue_in_hand = False
    app.open_help()
    run(app, 2.0)
    assert scene.rules.time_left == left
    app.help.close()
    run(app, 1.0)
    assert scene.rules.time_left < left


def test_ac36_there_is_no_shot_clock_and_no_lives_in_sprint(app, monkeypatch):
    seen = record_panel(monkeypatch)
    lights = []
    monkeypatch.setattr(hud, "draw_lives", lambda *a: lights.append(a))
    scene = start_mode(app, "sprint")
    run(app, config.PRACTICE_SHOT_S + 5.0)  # longer than a shot's clock in the other drills
    assert scene.rules.phase == "playing" and scene.rules.lives == config.PRACTICE_LIVES
    assert scene._shot_left == config.PRACTICE_SHOT_S and scene._notice is None
    scene.draw(pg.display.get_surface())
    assert seen[-1]["lives"] is None and lights == []


def test_ac36_the_lives_row_is_still_drawn_in_the_other_drills(app, monkeypatch):
    lights = []
    monkeypatch.setattr(hud, "draw_lives", lambda *a: lights.append(a))
    for mode in ("ghost", "call"):
        start_mode(app, mode).draw(pg.display.get_surface())
    assert len(lights) == 2


def test_ac36_the_counter_shows_the_runs_time_rounded_up_with_its_own_word(app, monkeypatch):
    seen = record_panel(monkeypatch)
    app.go_practice("sprint")
    app.practice.draw(pg.display.get_surface())
    assert seen[-1]["count_word"] == "practice.count"  # the wait still counts the wait
    assert seen[-1]["count"] == math.ceil(config.PRACTICE_READY_S)
    run(app, config.PRACTICE_READY_S + 0.5)
    scene = app.practice
    scene.rules.time_left = 41.2
    scene.draw(pg.display.get_surface())
    assert seen[-1]["count"] == 42 and seen[-1]["count_word"] == "practice.time"
    assert seen[-1]["score_word"] == "practice.potted"
    assert not seen[-1]["warn"]


def test_ac36_the_other_drills_keep_their_words(app, monkeypatch):
    seen = record_panel(monkeypatch)
    for mode in ("ghost", "call"):
        start_mode(app, mode).draw(pg.display.get_surface())
        assert seen[-1]["score_word"] == "practice.streak"
        assert seen[-1]["count_word"] == "practice.count"
        assert seen[-1]["count"] == config.PRACTICE_SHOT_S and seen[-1]["lives"] is not None


def test_ac36_the_clock_is_red_and_ticks_in_its_last_seconds(app, monkeypatch):
    seen = record_panel(monkeypatch)
    warns = []
    monkeypatch.setattr(app.audio, "play_clock_warn", lambda left: warns.append(left))
    scene = start_mode(app, "sprint")
    scene.rules.time_left = config.PRACTICE_WARN_S + 0.5
    run(app, 2.2)
    scene.draw(pg.display.get_surface())
    assert seen[-1]["warn"] and warns[:2] == [config.PRACTICE_WARN_S, config.PRACTICE_WARN_S - 1]


def test_ac36_the_clock_running_out_loses_the_run_with_its_own_words(app):
    scene = start_mode(app, "sprint")
    scene.rules.streak = 4
    scene.rules.time_left = 0.5
    run(app, 1.0)
    assert scene.rules.phase == "lost" and scene._lost_words() == i18n.t("practice.time_up")
    assert app.settings.practice_best_sprint == 4


def test_ac36_the_seconds_a_shot_won_or_cost_are_told_in_the_card(app, monkeypatch):
    pockets_told(monkeypatch, {7: [1], 8: [1]})
    scene = start_mode(app, "sprint")
    three_balls(scene)
    scene.rules.target = 6
    start_time = scene.rules.time_left
    scene.rules.on_shot()
    scene._live = True
    scene.rules.on_events([BallPocketed(6, 2)])  # a pot: time is won
    scene._end_shot()
    assert scene.rules.time_left == start_time + config.SPRINT_POT_BONUS_S
    words = [w for w, _ in scene._banner_lines()]
    assert words == [i18n.t("practice.time_gain", s=int(config.SPRINT_POT_BONUS_S))]
    scene.rules.target = 7
    before = scene.rules.time_left
    miss(scene)  # a miss: time is lost, said on the reason's own line
    assert scene.rules.time_left == before - config.SPRINT_MISS_COST_S
    words = [w for w, _ in scene._banner_lines()]
    cost = i18n.t("practice.time_loss", s=int(config.SPRINT_MISS_COST_S))
    assert words[0] == f"{i18n.t('practice.miss')} \u00b7 {cost}" and len(words) <= 2
    run(app, config.NOTICE_S + 0.5)
    assert scene._banner_lines() == []


def test_ac36_a_scratch_in_sprint_tells_its_cost_and_still_has_room_for_the_how_to(app):
    scene = start_mode(app, "sprint")
    three_balls(scene)
    scene.rules.target = 6
    scene.rules.on_shot()
    scene._live = True
    scene.rules.on_events([BallPocketed(0, 0)])
    scene._end_shot()
    words = [w for w, _ in scene._banner_lines()]
    cost = i18n.t("practice.time_loss", s=int(config.SPRINT_SCRATCH_COST_S))
    assert words == [f"{i18n.t('foul.scratch')} \u00b7 {cost}", i18n.t("notice.hand_drag")]


# --- AC37: the card and the best of each drill ------------------------------
def lose(scene, streak):
    scene.rules.streak = streak
    scene.rules.lives = 1
    scene.rules.time_left = 0.01
    scene.update(RUN_DT)  # (the clock of Sprint)
    if scene.rules.phase == "playing":
        scene._timeout()
    assert scene.rules.phase == "lost"


@pytest.mark.parametrize("mode", ["ghost", "call", "sprint"])
def test_ac37_the_best_is_kept_for_each_drill_apart_and_only_goes_up(app, mode):
    scene = start_mode(app, mode)
    lose(scene, 5)
    fields = {
        "ghost": "practice_best",
        "call": "practice_best_call",
        "sprint": "practice_best_sprint",
    }
    assert getattr(app.settings, fields[mode]) == 5
    assert [getattr(app.settings, f) for m, f in fields.items() if m != mode] == [0, 0]
    scene = start_mode(app, mode)
    lose(scene, 3)
    assert getattr(app.settings, fields[mode]) == 5  # a lower run does not lower it
    scene = start_mode(app, mode)
    lose(scene, 9)
    assert getattr(app.settings, fields[mode]) == 9


@pytest.mark.parametrize("mode", ["ghost", "call", "sprint"])
def test_ac37_the_panel_and_the_card_read_the_best_of_their_own_drill(app, monkeypatch, mode):
    app.change_settings(practice_best=2, practice_best_call=4, practice_best_sprint=6)
    seen = record_panel(monkeypatch)
    card = []
    monkeypatch.setattr(hud, "draw_result", lambda canvas, v, **kw: card.append(kw))
    scene = start_mode(app, mode)
    scene.draw(pg.display.get_surface())
    expected = {"ghost": 2, "call": 4, "sprint": 6}[mode]
    assert seen[-1]["best"] == expected
    lose(scene, 1)
    run(app, 4.0)
    scene.draw(pg.display.get_surface())
    assert card[-1]["rows"][1] == (i18n.t("practice.best"), expected)
    assert card[-1]["score_label"] == i18n.t(
        "practice.potted" if mode == "sprint" else "practice.streak"
    )


def test_ac37_a_new_run_keeps_the_drill(app):
    scene = start_mode(app, "sprint")
    app.handle_event(key(pg.K_r))
    assert scene.mode == "sprint" and type(scene.rules).__name__ == "SprintRun"
    assert scene.rules.time_left == config.SPRINT_START_S and scene.counting_down
    run(app, config.PRACTICE_READY_S + 0.5)
    lose(scene, 2)
    run(app, 4.0)
    scene.new_game()  # what the card's "new game" does
    assert scene.mode == "sprint" and type(scene.rules).__name__ == "SprintRun"
    app.go_menu()
    app.go_practice("call")
    assert scene.mode == "call" and type(scene.rules).__name__ == "CallRun"
    app.go_practice()
    assert scene.mode == "ghost" and type(scene.rules).__name__ == "GhostRun"


def test_ac37_the_card_of_a_run_lost_to_lives_in_the_other_drills_names_its_cause(app):
    scene = start_mode(app, "call")
    lose(scene, 2)
    assert scene._lost_words() == lives_words("practice.lost_timeout")


# --- AC39: the words of the drills fit in both languages ------------------------------
NEW_KEYS = (
    "practice.call_hint",
    "practice.pocket_swapped",
    "practice.miss_pocket",
    "practice.time",
    "practice.potted",
    "practice.time_up",
    "practice.time_gain",
    "practice.time_loss",
)


def test_ac39_every_new_word_has_both_languages():
    for name in NEW_KEYS:
        vi, en = i18n.table("vi")[name], i18n.table("en")[name]
        assert vi and en and vi != name and en != name


@pytest.mark.parametrize("lang", ["vi", "en"])
def test_ac39_the_new_cell_words_fit_their_cells(lang):
    i18n.set_lang(lang)
    canvas = pg.Surface((400, 100))
    for name in ("practice.time", "practice.potted"):
        assert hud.label_centered(canvas, V, i18n.t(name), (200, 20)).w <= 2 * hud.CELL_INSET


@pytest.mark.parametrize("lang", ["vi", "en"])
def test_ac39_every_line_of_the_notice_fits_the_strip_under_the_table(lang):
    i18n.set_lang(lang)
    gain = i18n.t("practice.time_gain", s=8)
    loss = i18n.t("practice.time_loss", s=10)
    lines = [gain]
    for name in ("practice.miss", "practice.miss_pocket", "foul.scratch", "practice.lost_timeout"):
        lines.append(f"{i18n.t(name)} \u00b7 {loss}")
    lines += [i18n.t("practice.pocket_swapped"), i18n.t("practice.target_swapped")]
    for line in lines:
        assert hud.text_width(V, line, 16, True) + 44 < 600, (lang, line)
    assert hud.text_width(V, i18n.t("practice.call_hint"), 16) < 600


@pytest.mark.parametrize("lang", ["vi", "en"])
def test_ac39_the_reasons_on_the_result_card_fit_in_two_lines(lang):
    i18n.set_lang(lang)
    room = hud.RESULT_CARD.w - 60
    for reason in (i18n.t("practice.time_up"), lives_words("practice.miss_pocket")):
        assert len(hud.reason_lines(V, reason, room)) <= 2, (lang, reason)


# --- AC44: the card of a run lost to lives says it in two lines of its own ---------------
LAST_CAUSES = ("practice.miss", "practice.miss_pocket", "foul.scratch", "practice.lost_timeout")
MIN_VIEW = View.for_window((1050, 590))  # the smallest window the game allows


def card_ink(view, reason):
    """(the lines drawn for `reason`, the pixels only the reason put on the card's frame)."""
    c = hud.RESULT_CARD
    size = view.canvas
    with_reason, without = pg.Surface(size), pg.Surface(size)
    for surf, why in ((with_reason, reason), (without, None)):
        hud.draw_result_frame(surf, view, won=False, reason=why, row_names=["a", "b"])
    rect = pg.Rect(0, 0, 0, 0)
    px_w, px_wo = pg.PixelArray(with_reason), pg.PixelArray(without)
    band_h = hud.RESULT_SCORE_Y - 60  # (from under the title down to the score line)
    inner = view.rect(c.x + 8, c.y + 80, c.w - 16, band_h)
    xs, ys = [], []
    for y in range(inner.top, inner.bottom):
        for x in range(inner.left, inner.right):
            if px_w[x, y] != px_wo[x, y]:
                xs.append(x)
                ys.append(y)
    del px_w, px_wo
    if xs:
        rect = pg.Rect(min(xs), min(ys), max(xs) - min(xs) + 1, max(ys) - min(ys) + 1)
    return hud.reason_lines(view, reason, c.w - 60), rect


@pytest.mark.parametrize("lang", ["vi", "en"])
def test_ac44_the_card_of_a_run_lost_to_lives_has_two_lines_of_its_own(app, lang):
    i18n.set_lang(lang)
    scene = start_mode(app, "ghost")
    for cause in LAST_CAUSES:
        scene._miss_key = None
        scene.rules.phase, scene.rules.last = "lost", type("R", (), {"lost_life": cause})()
        words = scene._lost_words()
        assert words == lives_words(cause)
        head, last = words.split("\n")
        assert head == i18n.t("practice.out_of_lives") and "{" not in last
        assert last == i18n.t("practice.last_one", why=i18n.t(cause))
        assert hud.reason_lines(V, words, hud.RESULT_CARD.w - 60) == [head, last]


@pytest.mark.parametrize("lang", ["vi", "en"])
@pytest.mark.parametrize("view", [V, MIN_VIEW], ids=["1280x720", "1050x590"])
def test_ac44_both_lines_fit_the_card_and_stay_above_the_score_line(lang, view):
    i18n.set_lang(lang)
    c = hud.RESULT_CARD
    for cause in LAST_CAUSES:
        lines, ink = card_ink(view, lives_words(cause))
        assert len(lines) == 2, (lang, cause, lines)
        assert ink.w > 0
        left, right = view.pt((c.x + 30, 0))[0], view.pt((c.right - 30, 0))[0]
        assert left <= ink.left and ink.right <= right, (lang, cause, ink)
        assert ink.bottom <= view.pt((0, c.y + hud.RESULT_SCORE_Y))[1], (lang, cause, ink)
        # two bands of ink, not one run-on line and not three
        one_line = card_ink(view, lines[0])[1]
        assert ink.height > one_line.height, (lang, cause)


def test_ac44_the_clock_in_sprint_stays_one_line_and_free_play_is_not_split():
    for lang in ("vi", "en"):
        i18n.set_lang(lang)
        assert hud.reason_lines(V, i18n.t("practice.time_up"), 340) == [i18n.t("practice.time_up")]
    long = "word " * 40
    assert len(hud.reason_lines(V, long, 340)) == 2  # (still wraps, still capped)
    i18n.set_lang("vi")
