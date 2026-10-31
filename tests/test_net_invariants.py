"""A two-player game left to play itself (the dev tool's bot), game after game, ended at every
moment of its start: what the screen shows may never contradict what the rules say.

These were found by hand in the dev tool (a coin under the result card, the score moving with the
card up, the bot shooting while the coin was in the air). This is the same walk done by the
machine, with every frame watched. One test per kind of check would miss the next such bug: the
walk is what finds it.
"""

import pygame as pg
import pytest

from game import config, i18n
from game.app import App
from game.net import toss
from game.render import hud
from tools.devkit.check import DT
from tools.devkit.harness import Harness

END_AT_S = (0.1, 1.0, 3.0, 4.6, 6.0)  # seconds into the game's start when it is given up
CYCLES = 2  # games in a row for each of them
DRAW_EVERY = 3  # frames (the rest only advance time): the spies see 20 pictures a second


@pytest.fixture
def world(monkeypatch):
    pg.init()
    app = App(pg.display.set_mode(config.LOGICAL_SIZE))
    app.change_settings(lang="vi", show_fps=False)
    harness = Harness(app)
    yield app, harness
    harness.reset()
    pg.quit()
    i18n.set_lang("vi")


class Watch:
    """Every frame of the walk is checked against what must always hold."""

    def __init__(self, app, h, monkeypatch):
        self.app, self.h = app, h
        self.errors: list[str] = []
        self.frames = 0
        self.t = 0.0
        self.coin = self.dark = 0
        self._shown: dict[int, tuple[tuple[int, int], float]] = {}  # scene -> (score, age) before
        self._shots: dict[int, int] = {}  # session -> shots begun before
        real_coin, real_dim = hud.toss_coin, hud.dim_rect

        def coin(*args, **kw):
            self.coin += 1
            return real_coin(*args, **kw)

        def dim(canvas, v, rect, k):
            self.dark += k > 0
            return real_dim(canvas, v, rect, k)

        monkeypatch.setattr(hud, "toss_coin", coin)
        monkeypatch.setattr(hud, "dim_rect", dim)

    def fail(self, what: str) -> None:
        if len(self.errors) < 8:
            self.errors.append(f"t={self.t:6.2f}s game {self.app.net.session.game_no}: {what}")

    def step(self) -> None:
        app, h = self.app, self.h
        self.coin = self.dark = 0
        h.tick(DT)
        app.update(DT)
        drawn = self.frames % DRAW_EVERY == 0
        if drawn:
            app.draw()
        self.frames += 1
        self.t += DT
        scene = app.net
        if scene is None:
            return
        s = scene.session
        age = scene._clock - scene._started_at
        if drawn and s.match.over and (self.coin or self.dark):
            self.fail("a coin or a dark table drawn under the result card")
        # the score between the plates moves only when the point of the game before rolls in
        shown = scene._shown_wins()
        before = self._shown.get(id(scene))
        if before is not None and shown != before[0]:
            crossed = before[1] < config.NET_TOSS_SCORE_AT_S <= age
            if not crossed:
                self.fail(
                    f"the score between the plates moved {before[0]} -> {shown} at age {age:.2f}"
                )
        self._shown[id(scene)] = (shown, age)
        # nobody takes a shot before the coin has landed (either machine, whoever drives it)
        for sess in h.sessions():
            began = self._shots.get(id(sess), sess.shots_started)
            if sess.shots_started > began and sess._toss_left > 0:
                self.fail(f"a shot began with {sess._toss_left:.2f}s of the coin left")
            self._shots[id(sess)] = sess.shots_started

    def until(self, cond, seconds: float, what: str) -> None:
        for _ in range(round(seconds / DT)):
            if cond():
                return
            self.step()
        assert cond(), f"never came true in {seconds}s: {what}"


def end_and_ask_again(watch: Watch, end_at: float, giver) -> None:
    """The game on screen is given up `end_at` seconds into its start; the card stands until
    the player presses Rematch (the bot has asked by itself); then the next game's scene."""
    app, h = watch.app, watch.h
    scene = app.net
    watch.until(lambda: scene._clock - scene._started_at >= end_at, 12.0, "the game's start")
    in_the_coin = not scene._toss_done()
    assert in_the_coin == (end_at < scene._toss.total_s)  # the walk ends it where it says
    giver.surrender()
    watch.until(lambda: scene._result_shown, 5.0, "the result card")
    watch.until(lambda: h.mine.rematch[h.fake.me], 8.0, "the bot asks for another game")
    for _ in range(round(1.5 / DT)):  # the card stands; nobody has pressed Rematch
        watch.step()
    assert app.net is scene and h.mine.game_no == scene._game_no  # still the same game
    scene._result_do("again")
    watch.until(lambda: app.net is not scene, 5.0, "the new game's scene")


@pytest.mark.parametrize("end_at", END_AT_S)
def test_games_in_a_row_with_the_bot_never_contradict_themselves(world, monkeypatch, end_at):
    app, h = world
    watch = Watch(app, h, monkeypatch)
    h.start_net(me_host=True, breaker="random")
    h.bot.auto = True  # F3 in the dev tool: it plays its turns and asks for the rematch itself
    for cycle in range(CYCLES):
        end_and_ask_again(watch, end_at, h.fake if cycle % 2 else h.mine)
        assert app.net.session.game_no == cycle + 2 and app.net._toss.again
    # the last game is played: the whole start, then the bot plays (it must not have been early)
    scene = app.net
    watch.until(lambda: scene._toss_done(), toss.total_s(True) + 3.0, "the coin")
    watch.until(lambda: h.fake.shots_started + h.mine.shots_started > 0, 40.0, "a shot")
    assert watch.errors == []
    assert watch.frames > 600
