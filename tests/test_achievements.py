"""Achievements (docs/plans/20261105-thanh-tuu.md, GAME_DESIGN "Phản hồi lần 43"): which ones there
are, when each is earned, that the progress is kept, and what the player sees (the cup in the
menu, the list, the card that slides in)."""

import json

import pygame as pg
import pytest

from game import achievements as ach
from game import config, i18n, settings
from game.app import App
from game.physics import Shot
from game.render import achieve, hud
from game.render.view import View
from game.rules.eight_ball import LOST, RERACK, WON, ShotResult
from game.scenes import achievements as panel

# ---- the catalogue ----------------------------------------------------------------------------


def test_there_are_twenty_of_which_four_are_secret():
    assert len(ach.CATALOGUE) == 20
    assert sum(a.secret for a in ach.CATALOGUE) == 4
    assert {a.group for a in ach.CATALOGUE} == {ach.FREE, ach.PRACTICE, ach.DUO}


@pytest.mark.parametrize("lang", ["vi", "en"])
def test_every_achievement_has_a_name_and_a_way_to_earn_it_in_both_languages(lang):
    table = i18n.table(lang)
    for a in ach.CATALOGUE:
        assert table.get(f"ach.{a.id}"), (lang, a.id)
        assert table.get(f"ach.{a.id}.d"), (lang, a.id)
    for key in ("menu.achievements", "ach.title", "ach.count", "ach.unlocked", "ach.secret",
                "ach.secret.d", "ach.hint"):  # fmt: skip
        assert table.get(key), (lang, key)


@pytest.mark.parametrize("lang", ["vi", "en"])
def test_the_words_of_a_row_fit_in_its_column(lang):
    pg.init()
    i18n.set_lang(lang)
    v = View(1.0)
    room = panel.COL_W - panel.TEXT_DX
    try:
        for a in ach.CATALOGUE:
            assert hud.text_width(v, i18n.t(f"ach.{a.id}"), panel.NAME_SIZE, True) <= room, a.id
            assert hud.text_width(v, i18n.t(f"ach.{a.id}.d"), panel.DESC_SIZE) <= room, a.id
        assert hud.text_width(v, i18n.t("ach.secret.d"), panel.DESC_SIZE) <= room
    finally:
        i18n.set_lang("vi")


# ---- when each is earned ----------------------------------------------------------------------


def tracker():
    s = settings.Settings()
    told: list[str] = []
    return ach.Tracker(s, announce=told.append), s, told


def shot(pocketed=(), group=None, outcome=None):
    return ShotResult(pocketed=tuple(pocketed), group=group, outcome=outcome)


def test_free_play_first_shot_pot_group_and_triple():
    tr, _, _ = tracker()
    assert tr.free_shot(shot(), 1, 0) == ["first_shot"]
    assert tr.free_shot(shot([3]), 2, 0) == ["first_pot"]
    assert tr.free_shot(shot([3], group="solid"), 3, 0) == ["pick_group"]
    assert tr.free_shot(shot([1, 2, 4]), 4, 0) == ["triple"]


def test_free_play_win_clean_win_and_the_secrets():
    tr, s, _ = tracker()
    got = tr.free_shot(shot([8], outcome=WON), 10, 0)
    assert {"win", "clean_win", "quick_win"} <= set(got)
    assert s.ach_wins == 1 and s.ach_clean_streak == 1
    tr2, _, _ = tracker()
    got = tr2.free_shot(shot([8], outcome=WON), 13, 2)
    assert "win" in got and "clean_win" not in got and "quick_win" not in got
    tr3, _, _ = tracker()
    assert "eight_break" in tr3.free_shot(shot([8], outcome=RERACK), 1, 0)


def test_a_win_after_five_fouls_is_a_comeback_four_is_not():
    tr, _, _ = tracker()
    assert "comeback" not in tr.free_shot(shot([8], outcome=WON), 20, 4)
    tr, _, _ = tracker()
    assert "comeback" in tr.free_shot(shot([8], outcome=WON), 20, 5)


def test_three_clean_wins_in_a_row_a_foul_or_a_loss_starts_over():
    tr, s, _ = tracker()
    for _ in range(2):
        tr.free_shot(shot([8], outcome=WON), 15, 0)
    assert not tr.has("hat_trick")
    tr.free_shot(shot([8], outcome=WON), 15, 1)  # a win, but with a foul
    assert s.ach_clean_streak == 0
    for _ in range(2):
        tr.free_shot(shot([8], outcome=WON), 15, 0)
    tr.free_shot(shot([8], outcome=LOST), 15, 0)
    assert s.ach_clean_streak == 0 and not tr.has("hat_trick")
    for _ in range(3):
        tr.free_shot(shot([8], outcome=WON), 15, 0)
    assert tr.has("hat_trick")


def test_ten_free_play_wins():
    tr, _, _ = tracker()
    for _ in range(9):
        tr.free_shot(shot([8], outcome=WON), 15, 1)
    assert not tr.has("win_10")
    tr.free_shot(shot([8], outcome=WON), 15, 1)
    assert tr.has("win_10")


def test_practice_streaks_count_as_they_grow_and_each_mode_has_its_own_wins():
    tr, _, _ = tracker()
    assert tr.practice_shot("ghost", "easy", 4, None) == []
    assert tr.practice_shot("ghost", "easy", 5, None) == ["ghost_5"]
    assert tr.practice_shot("ghost", "easy", 10, None) == ["ghost_10"]
    assert tr.practice_shot("ghost", "easy", 15, WON) == ["ghost_clear"]
    assert tr.practice_shot("call", "easy", 15, WON) == ["call_win"]
    assert tr.practice_shot("call", "hard", 15, WON) == ["call_hard"]
    assert tr.practice_shot("sprint", "easy", 15, WON) == ["sprint_win"]
    assert tr.practice_shot("sprint", "hard", 15, WON) == [
        "sprint_hard"
    ]  # (sprint_win was earned above)


def test_a_lost_practice_run_earns_no_win():
    tr, _, _ = tracker()
    assert tr.practice_shot("call", "hard", 9, LOST) == []
    assert tr.practice_shot("sprint", "hard", 9, LOST) == []


def test_two_player_wins():
    tr, s, _ = tracker()
    assert tr.duo_won() == ["duo_win"]
    for _ in range(3):
        tr.duo_won()
    assert not tr.has("duo_5")
    assert tr.duo_won() == ["duo_5"] and s.ach_duo_wins == 5


def test_each_is_earned_and_announced_once():
    tr, s, told = tracker()
    tr.free_shot(shot([3]), 1, 0)
    tr.free_shot(shot([3]), 2, 0)
    assert told == ["first_shot", "first_pot"]
    assert s.achievements == ["first_shot", "first_pot"] and tr.count == 2


# ---- kept for good ----------------------------------------------------------------------------


def test_progress_is_saved_and_comes_back(tmp_path):
    path = tmp_path / "s.json"
    s = settings.Settings()
    tr = ach.Tracker(s, save=lambda: settings.save(s, path))
    tr.free_shot(shot([8], outcome=WON), 9, 0)
    back = settings.load(path)
    assert back.achievements == s.achievements and "win" in back.achievements
    assert (back.ach_wins, back.ach_clean_streak) == (1, 1)


def test_a_broken_progress_file_gives_only_what_is_valid(tmp_path):
    path = tmp_path / "s.json"
    path.write_text(json.dumps({"achievements": ["win", "nope", "win", 7], "ach_wins": "x",
                                "ach_duo_wins": True}))  # fmt: skip
    s = settings.load(path)
    assert s.achievements == ["win"]
    assert s.ach_wins == 0 and s.ach_duo_wins == 0


# ---- the cards --------------------------------------------------------------------------------


def test_cards_come_one_at_a_time_in_order_each_with_its_own_start():
    started: list[str] = []
    q = achieve.Toasts(on_start=started.append)
    q.push("win", "free")
    q.push("duo_win", "duo")
    q.update(0.0)
    assert q.showing == "win" and started == ["win"]
    for _ in range(3):  # still the first: a card is not cut short by the next
        q.update(1.0)
        assert q.showing == "win"
    q.update(3.0)
    assert q.showing is None  # the first has gone
    q.update(achieve.GAP_S + 0.01)
    assert q.showing == "duo_win" and started == ["win", "duo_win"]
    q.update(10.0)
    assert not q.active


def test_a_card_rises_from_below_rests_then_leaves():
    q = achieve.Toasts()
    q.push("win", "free")
    q.update(0.0)
    assert q.offset() == pytest.approx(achieve.SLIDE_PX)
    q.update(achieve.SLIDE_IN_S + 0.1)
    assert q.offset() == 0.0
    q.update(achieve.HOLD_S)
    assert q.offset() > 0.0


# ---- in the game --------------------------------------------------------------------------------


@pytest.fixture
def app(monkeypatch, tmp_path):
    monkeypatch.setenv("NEONPOOL_SETTINGS", str(tmp_path / "settings.json"))
    pg.init()
    a = App(pg.display.set_mode(config.LOGICAL_SIZE))
    a.skip_transition()
    yield a
    pg.quit()
    i18n.set_lang("vi")


def click(pos):
    return pg.event.Event(pg.MOUSEBUTTONDOWN, pos=pos, button=1)


def test_the_cup_in_the_corner_opens_the_list_and_esc_closes_it(app):
    menu = app.menu
    app.handle_event(click(menu._trophy_rect().center))
    assert menu.achievements.is_open
    app.handle_event(pg.event.Event(pg.KEYDOWN, key=pg.K_ESCAPE))
    for _ in range(30):
        app.update(1 / 60)
    assert not menu.achievements.is_open


def test_the_t_key_opens_the_list_and_a_click_outside_closes_it(app):
    app.handle_event(pg.event.Event(pg.KEYDOWN, key=pg.K_t))
    assert app.menu.achievements.is_open
    app.handle_event(click((5, 5)))
    for _ in range(30):
        app.update(1 / 60)
    assert not app.menu.achievements.is_open


@pytest.mark.parametrize("lang", ["vi", "en"])
@pytest.mark.parametrize("earned", [[], [a.id for a in ach.CATALOGUE]], ids=["none", "all"])
def test_the_list_draws_whatever_has_been_earned(app, lang, earned):
    i18n.set_lang(lang)
    app.settings.achievements = list(earned)
    app.menu.achievements.open()
    app.menu.achievements.k = 1.0
    for _ in range(3):
        app.update(1 / 60)
        app.draw()


def test_a_free_play_shot_that_ends_earns_the_first_achievement_and_a_card_comes(app):
    app.go_play()
    scene = app.play
    scene.fire(Shot(0.0, 0.5, 0.0))
    for _ in range(60 * 30):
        app.update(1 / 60)
        if not scene._live:
            break
    assert app.achievements.has("first_shot")
    assert app.toasts.active
    app.draw()  # the card paints over the table


def test_a_won_two_player_game_is_counted_but_a_room_left_empty_is_not(app):
    # NetPlayScene._enter_result needs a live session; what it hands on is checked here
    assert app.achievements.duo_won() == ["duo_win"]
    assert app.settings.ach_duo_wins == 1
