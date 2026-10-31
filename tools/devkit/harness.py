"""What a developer needs to put the game in any state with no network and no second player.

`Harness` owns a FAKE opponent: a second `Session` joined to the player's by a `SimRoom` (a link
in virtual time that can be cut, made again, muted and slowed), driven by `Bot` (aims, pulls back
and lets go like a person, or only when told to). It also has the small scripted set-ups the game
needs to reach a state that takes a long game to reach (the 8 sunk early, a foul, the end of a
solo game). Everything here talks to the game through the same calls the game itself uses.
"""

from __future__ import annotations

import logging
import math
import random
from collections.abc import Callable, Generator

from game import config
from game.net import protocol as p
from game.net import session as net_session
from game.net.session import Session
from game.net.transport import SimRoom
from game.physics import Shot
from game.rules.eight_ball import SOLID

log = logging.getLogger("neonpool.dev")

MY_NAME, BOT_NAME = "Dev", "Bot"
Script = Generator[None]  # a script waits by yielding: one yield = one frame
SPEEDS = (0.25, 1.0, 4.0)
LATENCIES = (0.0, 0.06, 0.2)  # seconds, one way
EIGHT_EARLY_SHOT = Shot(-3 * math.pi / 4, 0.7, 0.0)  # from (0.6, 0.6) into the corner pocket


class Bot:
    """The fake opponent's hands. With `auto` it plays every turn it gets (and asks for a rematch
    when a game ends); without, only when `play_once()` is called."""

    THINK_S, AIM_S, PLACE_S, REMATCH_S = 0.8, 1.0, 0.6, 1.5

    def __init__(self) -> None:
        self.auto = False
        self.rng = random.Random(7)
        self._want = False
        self._phase = "idle"
        self._t = 0.0
        self._angle = 0.0
        self._power = 0.5

    def play_once(self) -> None:
        self._want = True

    def update(self, dt: float, s: Session) -> None:
        if not s.playing:
            return
        if s.match.over:
            self._t += dt
            if self.auto and self._t >= self.REMATCH_S and not s.rematch[s.me]:
                s.ask_rematch()
            return
        if not (self.auto or self._want):
            self._phase, self._t = "idle", 0.0
            return
        if s.can_place:
            self._t += dt
            if self._t >= self.PLACE_S:
                self._place(s)
                self._t = 0.0
        elif s.can_shoot:
            self._shoot_step(dt, s)
        else:
            self._phase, self._t = "idle", 0.0

    def _shoot_step(self, dt: float, s: Session) -> None:
        if self._phase == "idle":
            self._phase, self._t = "think", 0.0
            self._pick(s)
        self._t += dt
        if self._phase == "think" and self._t >= self.THINK_S:
            self._phase, self._t = "aim", 0.0
        elif self._phase == "aim":
            k = min(1.0, self._t / self.AIM_S)
            s.set_aim(p.AIM_PULLING, self._angle, k * self._power * config.MAX_DRAG_PX)
            if self._t >= self.AIM_S:
                s.shoot(Shot(self._angle, self._power, 0.0))
                s.set_aim(p.AIM_HIDDEN)
                self._phase, self._want = "idle", False

    def _pick(self, s: Session) -> None:
        cue = s.world.balls[0]
        targets = [b for b in s.world.balls[1:] if b.in_play]
        aim = self.rng.choice(targets) if targets else cue
        self._angle = math.atan2(aim.y - cue.y, aim.x - cue.x) + self.rng.uniform(-0.06, 0.06)
        self._power = self.rng.uniform(0.35, 0.85)

    def _place(self, s: Session) -> None:
        for _ in range(40):
            x = self.rng.uniform(0.3, config.TABLE_L - 0.3)
            y = self.rng.uniform(0.2, config.TABLE_W - 0.2)
            if s.place_cue(x, y):
                s.release_cue()
                return


class Harness:
    def __init__(self, app) -> None:
        self.app = app
        self.room: SimRoom | None = None
        self.mine: Session | None = None  # the session of the player's own screen
        self.fake: Session | None = None  # the opponent's
        self.me_host = True
        self.bot = Bot()
        self.script: Script | None = None
        self.latency = LATENCIES[0]
        self.speed = 1.0
        self.last_error: str | None = None

    # ------------------------------------------------------------------ time
    def tick(self, dt: float) -> None:
        """Once per frame, before `app.update(dt)`: the link, the fake opponent, the script."""
        if self.room is not None:
            self.room.advance(dt)
        if self.fake is not None:
            self.fake.update(dt)
            self.bot.update(dt, self.fake)
            if self.app.net is None and self.fake.phase == net_session.CLOSED:
                self.drop_fake()  # the player left: the room is over
        if self.script is not None:
            try:
                next(self.script)
            except StopIteration:
                self.script = None
            except Exception as exc:  # a broken script must not take the tool down
                log.exception("dev script failed")
                self.last_error = f"script: {exc}"
                self.script = None

    def run_script(self, script: Script) -> None:
        self.script = script

    @staticmethod
    def wait(cond: Callable[[], bool], seconds: float = 30.0) -> Script:
        for _ in range(round(seconds * 60)):
            if cond():
                return
            yield

    # ------------------------------------------------------------------ clean slate
    def close_everything(self) -> None:
        """Every card and panel shut at once (no folding), so a state starts from a clean screen."""
        app = self.app
        app.menu.play_panel.dismiss()
        for panel in (app.help, app.menu.settings):
            panel.is_open = panel._closing = False
            panel.k = 0.0
            panel._frozen.clear()
            if hasattr(panel, "_h"):
                panel._h = panel._morph = None

    def reset(self) -> None:
        """Back to a menu with no game, no fake opponent and no script."""
        self.script = None
        self.close_everything()
        if self.app.net is not None:
            self.app.go_menu()
        self.drop_fake()
        self.app.play.new_game()
        self.app.go_menu()
        self.app.skip_transition()

    def drop_fake(self) -> None:
        if self.fake is not None:
            self.fake.leave()
        self.room = self.mine = self.fake = None
        self.bot._phase, self.bot._t, self.bot._want = "idle", 0.0, False

    # ------------------------------------------------------------------ a two-player game
    @property
    def in_net(self) -> bool:
        return self.mine is not None and self.fake is not None and self.app.net is not None

    def start_net(self, *, me_host: bool = True, breaker: str = "me") -> None:
        """A two-player game against the fake opponent. `breaker`: "me", "bot" or "random"."""
        self.reset()
        self.me_host = me_host
        for seed in range(300):
            room = SimRoom(self.latency, 0.0, 0.0, seed)
            names = (MY_NAME, BOT_NAME) if me_host else (BOT_NAME, MY_NAME)
            host = Session(room.a, True, names[0], rng=random.Random(seed), relink=room.host_relink)
            guest = Session(room.b, False, names[1], relink=room.guest_relink)
            for _ in range(30):
                room.advance(1 / 60)
                host.update(1 / 60)
                guest.update(1 / 60)
            mine, fake = (host, guest) if me_host else (guest, host)
            if host.playing and (
                breaker == "random" or host.breaker == (mine.me if breaker == "me" else fake.me)
            ):
                break
        self.room, self.mine, self.fake = room, mine, fake
        self.app.start_net(mine)
        self.app.skip_transition()

    def ensure_net(self) -> None:
        """A game that is on (a new one if there is none, or the last one is over)."""
        if not self.in_net or self.mine.phase != net_session.PLAYING or self.mine.match.over:
            self.start_net(me_host=self.me_host)

    def host_session(self) -> Session:
        return self.mine if self.me_host else self.fake

    def sessions(self) -> list[Session]:
        return [s for s in (self.mine, self.fake) if s is not None]

    def skip_toss(self) -> None:
        for s in self.sessions():
            s._toss_left = 0.0
        if self.app.net is not None:
            self.app.net._started_at -= 10.0

    def set_clock(self, seconds_left: float) -> None:
        """The clock of the shot being waited for has `seconds_left` to go (on both machines)."""
        self.skip_toss()
        for s in self.sessions():
            s._turn_used = config.NET_TURN_S - seconds_left

    def set_wins(self, mine: int, theirs: int) -> None:
        if self.mine is not None and self.fake is not None:
            self.mine.wins[self.mine.me], self.mine.wins[self.fake.me] = mine, theirs
            self.fake.wins = list(self.mine.wins)

    def set_latency(self, seconds: float) -> None:
        self.latency = seconds
        if self.room is not None:
            self.room.sim.latency_s = seconds
            self.room._args = (seconds, *self.room._args[1:])

    # ------------------------------------------------------------------ scripts
    def shoot_as(self, who: str, shot: Shot) -> None:
        if who == "me" and self.app.net is not None:
            self.app.net.fire(shot)  # through the screen: the cue darts, the sound plays
        elif who == "bot" and self.fake is not None:
            self.fake.shoot(shot)

    def _session_of(self, who: str) -> Session:
        return self.mine if who == "me" else self.fake

    def give_turn_to(self, who: str) -> Script:
        """Let the clock of whoever is on turn run out (no foul), if it is not `who`."""
        yield from self.wait(lambda: self.mine.settled and self.fake.settled)
        target = self._session_of(who).me
        host = self.host_session()
        if host.match.turn != target and not host.match.over:
            host.timeout_turn()
            yield from self.wait(lambda: self.mine.match.turn == self.fake.match.turn == target)
        yield from self.wait(lambda: self.mine.settled and self.fake.settled)

    def place_if_needed(self, who: str) -> Script:
        s = self._session_of(who)
        yield from self.wait(lambda: s.can_place or s.can_shoot)
        if s.can_place:
            s.place_cue(0.6, 0.6)
            s.release_cue()
            yield from self.wait(lambda: s.can_shoot)

    def script_eight_early(self, who: str) -> Script:
        """`who` sinks the 8 at once and so loses the game."""
        yield from self.wait(lambda: self.mine.settled and self.fake.settled)
        host = self.host_session()
        aside = {
            b.number: (0.35 + 0.09 * i, 1.15)
            for i, b in enumerate(host.world.in_play())
            if b.number
        }
        aside.update({8: (0.2, 0.2), 0: (0.6, 0.6)})
        host.match._judge.is_break = False  # (the 8 on the break only racks again: no loss)
        host.reset_table(aside)
        yield from self.wait(
            lambda: self.mine.settled and self.fake.settled
            and self.mine.checkpoints == self.fake.checkpoints
        )  # fmt: skip
        yield from self.give_turn_to(who)
        yield from self.place_if_needed(who)
        self.shoot_as(who, EIGHT_EARLY_SHOT)

    def script_foul(self, who: str) -> Script:
        """`who` shoots and touches nothing: a foul, the other player has the cue ball in hand."""
        yield from self.wait(lambda: self.mine.settled and self.fake.settled)
        host = self.host_session()
        host.reset_table({0: (1.2, 0.7)})
        yield from self.wait(
            lambda: self.mine.settled and self.fake.settled
            and self.mine.checkpoints == self.fake.checkpoints
        )  # fmt: skip
        yield from self.give_turn_to(who)
        yield from self.place_if_needed(who)
        self.shoot_as(who, Shot(-math.pi / 2, 0.1, 0.0))

    def script_dropped_for_good(self, seconds_left: float = 3.0) -> Script:
        """The link breaks and only `seconds_left` of the minute are left."""
        self.room.cut()
        yield from self.wait(lambda: all(s.link_down_s is not None for s in self.sessions()))
        for s in self.sessions():
            s.link_down_s = config.NET_REJOIN_S - seconds_left

    # ------------------------------------------------------------------ solo
    def solo_finish(self, win: bool) -> None:
        """A solo game one shot from its end: the 8 goes in; the group is cleared (win) or not."""
        app = self.app
        self.reset()
        app.go_play()
        scene = app.play
        scene.new_game()
        rules, world = scene.rules, scene.world
        for b in world.balls:
            b.in_play, b.vx, b.vy = False, 0.0, 0.0
        world.place(0, 0.6, 0.6)
        world.place(8, 0.2, 0.2)
        for i, n in enumerate(range(9, 16)):
            world.place(n, 0.35 + 0.09 * i, 1.15)
        if not win:
            for i, n in enumerate((3, 4, 5, 6, 7)):
                world.place(n, 0.35 + 0.09 * i, 0.95)
        rules.is_break, rules.group = False, SOLID
        rules.pocketed = set(range(1, 8)) if win else {1, 2}
        rules.shots, rules.fouls = 14, 2
        app.skip_transition()
        scene.fire(EIGHT_EARLY_SHOT)

    def solo_foul(self) -> None:
        """A soft shot that touches nothing: a foul, and the cue ball in hand."""
        self.reset()
        self.app.go_play()
        self.app.play.new_game()
        self.app.skip_transition()
        self.app.play.fire(Shot(math.pi, 0.1, 0.0))

    # ------------------------------------------------------------------ what the tool shows
    def status(self) -> str:
        parts = [f"x{self.speed:g}"]
        if self.in_net or self.fake is not None:
            link = "mạng OK"
            s = self.mine
            if s is not None and s.link_down_s is not None:
                link = f"RỚT {s.link_down_s:0.0f}s"
            parts += [
                "bot TỰ CHƠI" if self.bot.auto else "bot tay",
                f"trễ {round(self.latency * 1000)} ms",
                link,
            ]
        if self.script is not None:
            parts.append("đang chạy kịch bản…")
        return " · ".join(parts)
