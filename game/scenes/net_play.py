"""The table in a two-player game: the same table scene, with the other player on the network.

A `Session` (game/net/session.py) owns the simulation and the referee's word; this scene shows it
and turns the mouse into shots. Over the solo scene it adds: a coin toss at the start, two name
plates above the table (whose turn it is, group, balls left), the other player's cue moving as
they aim, the cue ball in hand placed by whoever fouled against, a result card with both players,
and a card when the connection ends. Also: the clock of the shot (a bar under the plate of the
player on turn, beeps in its last seconds), the score of the room between the plates, three
reaction buttons, Esc = a card with Resume / Give up, a card while the link is down, and a
rematch from the result card. See docs/GAME_DESIGN.md (network play, feedback 17).
"""

from __future__ import annotations

import math

import pygame as pg

from game.config import (
    GRAB_RADIUS_M,
    NET_DIAL_HOLD_S,
    NET_EMOTES,
    NET_LINK_CARD_DELAY_S,
    NET_REJOIN_S,
    NET_TOSS_SCORE_AT_S,
    NET_TURN_S,
    NET_TURN_WARN_S,
    NOTICE_S,
    PX_PER_M,
)
from game.i18n import t
from game.net import protocol as p
from game.net import session as net_session
from game.net import toss
from game.physics import Shot
from game.render import draw, hud
from game.render import palette as C
from game.render.layout import (
    OUTER_W,
    OUTER_X,
    PANEL_H,
    PANEL_W,
    PANEL_X,
    PANEL_Y,
    TABLE_GLOW,
    to_m,
    to_px,
)
from game.render.view import View
from game.rules.eight_ball import LOST, LOST_EARLY, LOST_FOUL, PLAYING, RERACK, WON
from game.rules.two_player import LOST_DROPPED, LOST_SURRENDER, MatchShot
from game.scenes.play import CALLOUT_AT, CALLOUTS, PlayScene
from game.tally import Tally

# group -> (what you are told when YOU were given it, what you are told when the other player was)
GROUP_NOTICES = {
    "solid": ("notice.group_solid", "net.notice.group_them_solid"),
    "stripe": ("notice.group_stripe", "net.notice.group_them_stripe"),
}
COIN_R = hud.COIN_R  # the coin of the toss; its times are game/net/toss.py
COIN_HOP_PX = 64.0  # how high it is thrown
TABLE_RECT = pg.Rect(*TABLE_GLOW)  # what goes dark while the coin is tossed (not the plates)
# why the other player lost -> what you are told (the reason is theirs: t(reason) is for the loser)
WON_REASONS = {
    LOST_EARLY: "net.won_early",
    LOST_FOUL: "net.won_foul",
    LOST_SURRENDER: "net.won_surrender",
    LOST_DROPPED: "net.won_dropped",
}
BLINK_HZ = 2.0  # the clock bar blinks this often in its last seconds
WAIT_LABEL_MAX = 150  # a "waiting for <name>…" longer than this (logical px) becomes "Waiting…"


class NetRules:
    """What the solo scene reads from its rules, for a two-player game as seen by YOU."""

    def __init__(self, session: net_session.Session, ended) -> None:
        self._session, self._ended = session, ended

    @property
    def _m(self):
        return self._session.match

    @property
    def phase(self) -> str:
        if self._m.over:
            return WON if self._m.winner == self._session.me else LOST
        return LOST if self._ended() else PLAYING

    @property
    def cue_in_hand(self) -> bool:
        return self._m.cue_in_hand and self._m.turn == self._session.me

    @property
    def shots(self) -> int:
        return self._m.shots[self._session.me]

    @property
    def fouls(self) -> int:
        return self._m.fouls[self._session.me]

    @property
    def pocketed(self) -> set[int]:
        return self._m.pocketed

    @property
    def group(self) -> str | None:
        return self._m.groups[self._session.me]

    @property
    def is_break(self) -> bool:
        return self._m.is_break

    def eight_is_next(self) -> bool:
        return self._m.eight_is_next(self._session.me)


class NetPlayScene(PlayScene):
    PANEL_KEYS = hud.NET_PANEL_KEYS

    @property
    def RESULT_DEFAULT(self) -> str:  # noqa: N802 (the solo scene has it as a class constant)
        """The button Enter presses on the result card: Rematch while it can be asked for."""
        return "again" if self._ended_note is None and self._can_again() else "menu"

    def _result_rects(self) -> dict[str, pg.Rect]:
        if self._ended_note is not None:
            return {"menu": hud.NOTICE_BUTTON}
        return dict(hud.NET_BUTTONS)

    def __init__(self, app, session: net_session.Session) -> None:
        super().__init__(app)
        self.session = session
        self.world = session.world
        self.rules = NetRules(session, lambda: self._ended_note is not None)
        self._me, self._them = session.me, 1 - session.me
        self._game_no = session.game_no  # a rematch makes a new one: and a new scene
        self._seen_shots = session.shots_started
        self._started_at = self._clock  # the start of the game (the look, the coin) runs from here
        self._toss = toss.Toss(session.game_no > 1, session.breaker)
        self._toss_age = 0.0  # ... as it was at the last update (for the sounds)
        self._vs_board = hud.Scoreboard()  # the score between the plates rolls when it changes
        before = list(session.wins)
        if session.prev_winner is not None:  # a rematch: the point of the last game comes in late
            before[session.prev_winner] -= 1
        self._wins_before = (before[self._me], before[self._them])
        self._card: str | None = None  # a small card over the table: "esc" or "sure"
        self._card_at = -99.0
        self._card_sel = 0  # which of its buttons is chosen
        self._card_fx = hud.ButtonFx()
        self._link_open = False  # the "connection lost" card is up
        self._emote_fx = hud.ButtonFx()
        self._emote_hover: int | None = None
        self._bubbles: dict[int, tuple[int, float]] = {}  # player -> (reaction, when it was said)
        self._warned = -1  # the last second of the clock that was beeped
        self._net_notice: tuple[str, str] | None = None  # (kind, words)
        self._remote_alpha = 0.0  # the other player's cue fades in and out
        self._tallies: list[Tally] = []  # one per player, me first
        self._ended_note: tuple[str, str] | None = None  # (title key, words): the link ended
        self._result_shown = False

    def set_view(self, v: View) -> None:
        """The solo table already made the sprites and the table picture for this size: share
        them instead of making them again (about 90 ms, right when the game begins)."""
        solo = getattr(self.app, "play", None)
        if solo is not None and solo is not self and solo.view.same_as(v):
            self.view, self.sprites, self.table = v, solo.sprites, solo.table
            if hasattr(self, "_frozen"):
                self._frozen.clear()
        else:
            super().set_view(v)

    # --- who is who ---
    def _name(self, player: int) -> str:
        return self.session.names[player] or t("net.default_name")

    def _toss_done(self) -> bool:
        return self._clock - self._started_at >= self._toss.total_s

    def _breaker_known(self) -> bool:
        return self._toss.breaker_known(self._clock - self._started_at)

    def leave(self) -> None:
        self.session.leave()

    # --- what may be done now ---
    def _can_aim(self) -> bool:
        return self._toss_done() and self.session.can_shoot

    def _dial_ok(self) -> bool:
        return self._can_aim()

    def _holding(self) -> bool:
        return self._toss_done() and self.session.can_place

    def fire(self, shot: Shot) -> None:
        pull = self.drag.bar_length
        played = self.session.shoot(shot)
        if played is None:
            return
        self._shot_visuals(played, pull)
        self._break_pending = self.session.match.is_break
        self._seen_shots = self.session.shots_started

    def _hand_event(self, e: pg.event.Event) -> bool:
        """Place the cue ball you have in hand: press it, drag, let go."""
        session = self.session
        if not (self._toss_done() and session.can_place):
            self.placing = False
            return False
        cue = self.world.balls[0]
        if e.type == pg.MOUSEBUTTONDOWN and e.button == 1:
            cx, cy = to_px(cue.x, cue.y)
            if math.hypot(e.pos[0] - cx, e.pos[1] - cy) <= GRAB_RADIUS_M * PX_PER_M:
                self.placing, self._place_ok = True, True
                self.app.audio.play_cue_pick()
                return True
        elif e.type == pg.MOUSEMOTION and self.placing:
            self._place_ok = session.place_cue(*to_m(*e.pos))  # False: it stays on its last spot
        elif e.type == pg.MOUSEBUTTONUP and e.button == 1 and self.placing:
            self.placing = False
            session.release_cue()
            self.app.audio.play_cue_put()
            return True
        return False

    def handle_event(self, e: pg.event.Event) -> None:
        card = self._card_showing()
        if card is not None:
            self._card_event(e, card)
        elif self.rules.phase == PLAYING and self._emote_event(e):
            return
        else:
            super().handle_event(e)

    def _key(self, key: int) -> None:
        if pg.K_1 <= key < pg.K_1 + NET_EMOTES:
            self._send_emote(key - pg.K_1)
        elif key == pg.K_ESCAPE:  # (no restart and no how-to-play card in a two-player game)
            if self.drag.active:
                self.drag.cancel()
            else:
                self._open_card("esc")

    # --- reactions
    def _send_emote(self, code: int) -> None:
        if self.session.send_emote(code):
            self.app.audio.play_click()
            self._emote_fx.press(code, self._clock)

    def _emote_event(self, e: pg.event.Event) -> bool:
        """The three reaction buttons. True when a click was theirs."""
        rects = hud.emote_rects()
        if e.type == pg.MOUSEMOTION:
            hover = next((i for i, r in enumerate(rects) if r.collidepoint(e.pos)), None)
            if hover is not None and hover != self._emote_hover:
                self.app.audio.play_hover()
            self._emote_hover = hover
        elif e.type == pg.MOUSEBUTTONDOWN and e.button == 1:
            for i, rect in enumerate(rects):
                if rect.collidepoint(e.pos):
                    self._send_emote(i)
                    return True
        return False

    # --- the small cards over a game that goes on: Esc, "give up?", "connection lost"
    def _card_showing(self) -> str | None:
        if self._link_open:
            return "link"
        return self._card if self.rules.phase == PLAYING else None

    def _open_card(self, name: str, sel: int | None = None) -> None:
        if self._link_open:
            return  # the card for a lost link has the screen: nothing opens over it
        self._card, self._card_at = name, self._clock
        self._card_sel = self._card_spec(name)[4] if sel is None else sel
        self._card_fx = hud.ButtonFx()
        self.drag.cancel()
        self.placing = False

    def _card_spec(self, name: str):
        """(title, words, [(key, label, main one?)], colour, the button chosen to begin with)."""
        them = self._name(self._them)
        if name == "esc":
            buttons = (("resume", t("net.card.resume"), True),
                       ("surrender", t("net.card.surrender"), False))  # fmt: skip
            return t("net.card.esc_title"), t("net.card.esc_line"), buttons, C.CYAN, 0
        if name == "sure":
            buttons = (("yes", t("net.card.surrender"), False), ("back", t("net.card.back"), True))
            return t("net.card.sure_title"), t("net.card.sure_line", name=them), buttons, C.ERROR, 1
        left = max(0, math.ceil(NET_REJOIN_S - (self.session.link_down_s or 0.0)))
        key = "net.link.host" if self.session.me == net_session.HOST else "net.link.guest"
        buttons = (("leave", t("net.card.leave"), True),)
        return t("net.end.lost"), t(key, name=them, n=left), buttons, C.ERROR, 0

    def _card_rects(self, name: str) -> dict[str, pg.Rect]:
        keys = [b[0] for b in self._card_spec(name)[2]]
        return dict(zip(keys, hud.notice_buttons(len(keys)), strict=True))

    def _card_event(self, e: pg.event.Event, name: str) -> None:
        rects = self._card_rects(name)
        keys = list(rects)
        if e.type == pg.MOUSEMOTION:
            for i, key in enumerate(keys):
                if rects[key].collidepoint(e.pos) and i != self._card_sel:
                    self._card_sel = i
                    self.app.audio.play_hover()
        elif e.type == pg.MOUSEBUTTONDOWN and e.button == 1:
            for key, rect in rects.items():
                if rect.collidepoint(e.pos):
                    self._card_do(name, key)
                    return
        elif e.type == pg.KEYDOWN:
            if e.key == pg.K_ESCAPE and name != "link":
                self._card = None  # (the card for a lost link only goes when the link is back)
            elif e.key in (pg.K_LEFT, pg.K_UP, pg.K_RIGHT, pg.K_DOWN, pg.K_TAB) and len(keys) > 1:
                self._card_sel = (self._card_sel + 1) % len(keys)
                self.app.audio.play_hover()
            elif e.key in (pg.K_RETURN, pg.K_KP_ENTER, pg.K_SPACE):
                self._card_do(name, keys[self._card_sel])

    def _card_do(self, name: str, key: str) -> None:
        self.app.audio.play_click()
        self._card_fx.press(key, self._clock)
        if key in ("resume", "back"):
            self._card = None
        elif key == "surrender":
            self._open_card("sure")
        elif key == "yes":
            self._card = None
            self.session.surrender()
        elif key == "leave":
            self.app.go_menu()

    # --- the result card: Rematch / Back to menu
    def _rematch_state(self) -> str:
        """ready | they_asked | wait (you asked) | gone (the other player left the room)."""
        s = self.session
        if s.phase == net_session.CLOSED or not s.linked:
            return "gone"
        if s.rematch[self._me]:
            return "wait"
        return "they_asked" if s.rematch[self._them] else "ready"

    def _can_again(self) -> bool:
        return self._rematch_state() in ("ready", "they_asked")

    def _result_event(self, e: pg.event.Event) -> None:
        rects = self._result_rects()
        if e.type == pg.KEYDOWN and pg.K_1 <= e.key < pg.K_1 + NET_EMOTES:
            self._send_emote(e.key - pg.K_1)
        elif self._emote_event(e):
            return
        elif e.type == pg.MOUSEMOTION:
            hover = next(
                (k for k, r in rects.items() if r.collidepoint(e.pos) and self._enabled(k)), None
            )
            if hover is not None and hover != self._hover:
                self.app.audio.play_hover()
            self._hover = hover
        elif e.type == pg.MOUSEBUTTONDOWN and e.button == 1:
            for key, rect in rects.items():
                if rect.collidepoint(e.pos):
                    self._result_do(key)
                    return
        elif e.type == pg.KEYDOWN:
            if e.key in (pg.K_RETURN, pg.K_KP_ENTER, pg.K_SPACE):
                self._result_do(self._hover or self.RESULT_DEFAULT)
            elif e.key == pg.K_ESCAPE:
                self.app.go_menu()
            elif (
                e.key in (pg.K_LEFT, pg.K_RIGHT, pg.K_TAB) and len(rects) > 1 and self._can_again()
            ):
                self._hover = "menu" if (self._hover or self.RESULT_DEFAULT) == "again" else "again"
                self.app.audio.play_hover()

    def _enabled(self, key: str) -> bool:
        return key != "again" or self._can_again()

    def _result_do(self, key: str) -> None:
        if key == "again":
            if self.session.ask_rematch():
                self.app.audio.play_click()
                self.result_fx.press("again", self._clock)
        else:
            self.app.audio.play_click()
            self.result_fx.press("menu", self._clock)
            self.app.go_menu()

    # --- time ---
    def _step_world(self, dt: float) -> list:
        events = self.session.update(dt)
        if events:
            self._show_events(events)
        return events

    def update(self, dt: float) -> None:
        s = self.session
        if s.game_no != self._game_no:  # a rematch: a new table and a new coin, in a new scene
            self.app.start_net(s)
            return
        super().update(dt)
        if s.game_no != self._game_no:
            self.app.start_net(s)
            return
        if s.shots_started != self._seen_shots:  # the other player has shot: show their cue darting
            self._seen_shots = s.shots_started
            if s.last_shooter != self._me:
                self._shot_visuals(s.last_shot, s.remote_cue.pull)
                self._break_pending = s.match.is_break
        for res in s.take_judged():
            self._show_judged(res)
        self._send_aim()
        rc = s.remote_cue
        show = rc.visible and s.settled and not s.my_turn and self._toss_done()
        step = dt / draw.CUE_FADE_IN_S if show else -dt / draw.CUE_FADE_OUT_S
        self._remote_alpha = max(0.0, min(1.0, self._remote_alpha + step))
        if s.match is not None and s.match.over and not self._result_shown:
            self._enter_result()
        elif s.phase == net_session.CLOSED and not s.match.over and self._ended_note is None:
            self._end_with_note()
        self._update_extras(dt)

    def _toss_sounds(self) -> None:
        """The start of the game has its sounds: the point added, the throw, a tick for each time
        the coin turns over, the landing. Only what happens between two frames sounds: a jump
        (the dev tool skipping the toss) is silent."""
        age, before = self._clock - self._started_at, self._toss_age
        self._toss_age = age
        if not 0 < age - before < 0.5:
            return
        tt, audio = self._toss, self.app.audio
        if self.session.prev_winner is not None and before < NET_TOSS_SCORE_AT_S <= age:
            audio.play_tally_ting(self.session.prev_winner == self._me, True)
        if self.session.match.over:
            return  # the game ended under the coin: no coin sounds behind the result card
        if before < tt.flip_at <= age:
            audio.play_coin_up()
        turned, all_turns = tt.faces_seen(age), 6 + tt.breaker
        if turned > tt.faces_seen(before):
            audio.play_tally_tick(turned / all_turns)
        if before < tt.land_at <= age:
            audio.play_coin_land()

    def _update_extras(self, dt: float) -> None:
        """The clock's beeps, the reactions, the small cards."""
        s, audio = self.session, self.app.audio
        self._toss_sounds()
        left = math.ceil(s.turn_left_s)
        if left > NET_TURN_WARN_S or not s.playing:
            self._warned = -1
        elif s.my_turn and s.clock_running and self._toss_done() and 0 < left != self._warned:
            self._warned = left  # a beep for each of your last seconds
            audio.play_clock_warn(left)
        for player, code in s.take_emotes():
            self._bubbles[player] = (code, self._clock)
            if player != self._me:
                audio.play_hover()
        if self.rules.phase != PLAYING:
            self._card = None
        wanted = (
            s.phase == net_session.PLAYING
            and s.link_down_s is not None
            and s.link_down_s >= NET_LINK_CARD_DELAY_S
        )
        if wanted and not self._link_open:
            self._link_open, self._card_at, self._card_sel = True, self._clock, 0
            self._card_fx = hud.ButtonFx()
            self.drag.cancel()
        elif not wanted:
            self._link_open = False
        card = self._card_showing()
        if card is not None:
            rects = self._card_rects(card)
            self._card_sel = min(self._card_sel, len(rects) - 1)
            self._card_fx.update(dt, list(rects)[self._card_sel], rects, self._clock)
        rects = dict(enumerate(hud.emote_rects()))
        self._emote_fx.update(dt, self._emote_hover, rects, self._clock)

    def _dialing(self) -> bool:
        """The spin dial is being worked on: the dot is held, or it was moved a moment ago."""
        return self._dial_drag or self._clock - self._spin_at < NET_DIAL_HOLD_S

    def _send_aim(self) -> None:
        s, dialing = self.session, self._dialing()
        if self._can_aim() and self.drag.has_direction:
            s.set_aim(p.AIM_PULLING, self.drag.angle, self.drag.bar_length, dialing)
        elif self._can_aim() and self._cue_alpha > 0.05:
            s.set_aim(p.AIM_RESTING, self.knob.angle, dialing=dialing)
        else:
            s.set_aim(p.AIM_HIDDEN, dialing=dialing)

    def _notify_net(self, kind: str, words: str, key: str) -> None:
        self._net_notice, self._notice_left = (kind, words), NOTICE_S
        word, colour, sound = CALLOUTS[key]
        self._callout = (t(word), colour, self._clock)
        getattr(self.app.audio, f"play_{sound}")()

    def _show_judged(self, res: MatchShot) -> None:
        """A shot has been judged by the referee: say what happened."""
        m = self.session.match
        mine = res.shooter == self._me
        who = self._name(res.shooter)
        if res.timed_out:  # the clock of the shot ran out: the turn went to the other player
            key = "net.timeout_me" if mine else "net.timeout_them"
            words = t("net.notice.timeout_me") if mine else t("net.notice.timeout_them", name=who)
            self._notify_net("foul" if mine else "info", words, key)
            return
        if res.outcome in (WON, LOST):
            return
        if res.outcome == RERACK:
            self.fx.clear()
            self.pocket_times.clear()
            self._break_pending = True
            self._notify_net("info", t("notice.rerack"), "notice.rerack")
            return
        if res.fouls:
            reason = t(res.fouls[0])
            words = reason if mine else t("net.notice.foul_them", name=who, reason=reason)
            self._notify_net("foul", words, "foul")
        elif res.group:
            keys = GROUP_NOTICES[res.group]
            words = t(keys[0]) if mine else t(keys[1], name=who)
            self._notify_net("info", words, GROUP_NOTICES[m.groups[self._me]][0])
        elif mine and res.pocketed and m.eight_is_next(self._me):
            self._notify_net("info", t("notice.eight"), "notice.eight")

    def _enter_result(self) -> None:
        m = self.session.match
        self._result_shown = True
        self._ended_at = self._clock
        won = m.winner == self._me
        (self.app.audio.play_win if won else self.app.audio.play_lose)()
        self._tallies = [
            Tally({"score": m.score(i), "shots": m.shots[i], "fouls": m.fouls[i]})
            for i in (self._me, self._them)
        ]
        self._tally = self._tallies[0]  # the sounds follow YOUR numbers
        self._ticks, self._tinged = dict.fromkeys(self._tally.targets, 0), set()

    def _end_with_note(self) -> None:
        reason = self.session.close_reason
        left = reason == net_session.CLOSE_LEFT
        title = "net.end.left" if left else "net.end.lost"
        line = t("net.end.left_line" if left else "net.end.lost_line", name=self._name(self._them))
        self._ended_note = (title, line)
        self._ended_at = self._clock
        self.app.audio.play_lose()

    # --- drawing ---
    def _banner_lines(self) -> list[tuple[str, tuple[int, int, int]]]:
        lines = []
        if self._net_notice and self._notice_left > 0:
            kind, words = self._net_notice
            lines.append((words, C.ERROR if kind == "foul" else C.ACCENT))
        if not self._toss_done() or self.session.match.over:
            return lines
        if self._holding():
            lines.append((t("notice.hand_drag"), C.TEXT))
        elif self.session.my_turn:
            pass  # your plate is lit; under the table the hint of the first shot may stand
        elif self.session.match.cue_in_hand:
            lines.append((t("net.placing_them", name=self._name(self._them)), C.TEXT))
        else:
            lines.append((t("net.turn_them", name=self._name(self._them)), C.TEXT))
        return lines[:2]

    def _draw_cues(self, canvas: pg.Surface, v: View, over: bool) -> None:
        super()._draw_cues(canvas, v, over)
        rc, cue = self.session.remote_cue, self.world.balls[0]
        if self._remote_alpha > 0.01 and cue.in_play and not over:
            d = (math.cos(rc.angle), math.sin(rc.angle))
            draw.draw_cue(canvas, v, to_px(cue.x, cue.y), d, rc.pull, rc.power, self._clock,
                          self._remote_alpha)  # fmt: skip

    def _plate_rects(self) -> tuple[pg.Rect, pg.Rect]:
        y, w, h = hud.PLATE_Y, hud.PLATE_W, hud.PLATE_H
        return pg.Rect(OUTER_X, y, w, h), pg.Rect(OUTER_X + OUTER_W - w, y, w, h)

    def _draw_panel(self, canvas: pg.Surface, v: View) -> None:
        super()._draw_panel(canvas, v)
        m, s = self.session.match, self.session
        mine, theirs = self._plate_rects()
        for rect, player in ((mine, self._me), (theirs, self._them)):
            group = m.groups[player]
            name = self._name(player)
            hud.name_plate(
                canvas, v, rect,
                t("net.you", name=name) if player == self._me else name,
                t(f"group.{group}") if group else t("group.open"),
                m.group_left(player),
                turn=m.turn == player and not m.over and s.playing and self._breaker_known(),
            )  # fmt: skip
        hud.versus(canvas, v, OUTER_X + OUTER_W / 2, self._shown_wins(), first=s.game_no == 1,
                   board=self._vs_board, clock=self._clock)  # fmt: skip
        if s.playing and not m.over and self._toss_done():
            turn_rect = mine if m.turn == self._me else theirs
            warn = s.clock_running and s.turn_left_s <= NET_TURN_WARN_S
            blink = int(self._clock * BLINK_HZ * 2) % 2 == 0
            hud.turn_bar(
                canvas, v, turn_rect, s.turn_left_s / NET_TURN_S, warn=warn, blink_on=blink
            )
        self._draw_ping(canvas, v)
        self._draw_spin_line(canvas, v, theirs)
        self._draw_emotes(canvas, v)

    def _draw_ping(self, canvas: pg.Surface, v: View) -> None:
        """The round trip to the other player, small, under the side panel: green, amber, red;
        dashes until the first answer (and while the link is down)."""
        s = self.session
        ms = round(s.rtt_s * 1000) if s.rtt_s is not None and s.linked else None
        hud.ping_tag(canvas, v, t("net.ping", ms="--" if ms is None else ms), ms,
                     PANEL_X + PANEL_W, PANEL_Y + PANEL_H + 14)  # fmt: skip

    def _draw_spin_line(self, canvas: pg.Surface, v: View, plate: pg.Rect) -> None:
        """Above the other player's plate: they are setting the spin (while they do, and for a
        moment after; it fades over its last third of a second)."""
        s, m = self.session, self.session.match
        rc = s.remote_cue
        if not (s.playing and not m.over and m.turn == self._them and s.settled):
            return
        if not rc.tuning_spin or not self._toss_done():
            return
        k = round(min(1.0, rc.dial_left / 0.35) * 4) / 4
        hud.pulse_status(canvas, v, t("net.spin_them", name=self._name(self._them)),
                         (plate.right, plate.y - 16), self._clock, size=13,
                         color=C.lerp(C.BG, C.MAGENTA, k), align="right")  # fmt: skip

    def _draw_emotes(self, canvas: pg.Surface, v: View) -> None:
        """The reaction buttons (above the side panel) and what each player last said."""
        s = self.session
        for i, rect in enumerate(hud.emote_rects()):
            hud.emote_chip(canvas, v, rect, t(f"net.emote.{i}"), str(i + 1), self._emote_fx, i,
                           self._clock, enabled=s.emote_ready)  # fmt: skip
        mine, theirs = self._plate_rects()
        for player, (code, at) in self._bubbles.items():
            plate = mine if player == self._me else theirs
            hud.emote_bubble(canvas, v, plate, player == self._me, t(f"net.emote.{code}"),
                             self._clock - at)  # fmt: skip

    def draw(self, canvas: pg.Surface) -> None:
        super().draw(canvas)
        v = self.view
        if self.rules.phase != PLAYING:  # the reactions stay on top of the result card
            self._draw_emotes(canvas, v)
        card = self._card_showing()
        if card is not None:
            title, line, buttons, mood, _ = self._card_spec(card)
            hud.draw_notice(canvas, v, title, line, self._clock - self._card_at, self._card_fx,
                            self._clock, mood=mood, buttons=buttons, dim=False)  # fmt: skip

    def _draw_overlays(self, canvas: pg.Surface, v: View, over: bool) -> None:
        super()._draw_overlays(canvas, v, over)
        self._draw_toss(canvas, v)

    def _shown_wins(self) -> tuple[int, int]:
        """The score between the plates: after a rematch it starts as it was and gets the point
        of the last game NET_TOSS_SCORE_AT_S in (it rolls, the board sees the change). The point
        of THIS game waits for the next one: while the result card is up it is not shown."""
        if self._clock - self._started_at < NET_TOSS_SCORE_AT_S:
            return self._wins_before
        return self._card_wins()

    def _draw_toss(self, canvas: pg.Surface, v: View) -> None:
        """The start of the game: the table goes dark, the coin waits with its line, is thrown,
        spins, slows and lands on the breaker's name; the table lights up again. A game that
        ends in the middle of it (the other player gave up) shows no coin: just the card."""
        if self.session.match.over:
            return
        age, tt = self._clock - self._started_at, self._toss
        hud.dim_rect(canvas, v, TABLE_RECT, tt.dim(age))  # (the plates and the side panel stay lit)
        phase = tt.phase(age)
        if phase in (toss.LEAD, toss.DONE):
            return
        theta = tt.spin(age)
        squash = abs(math.cos(theta))
        face = round(theta / math.pi) % 2
        cx, cy = CALLOUT_AT
        bob = 3.0 * math.sin(age * 4.0) if phase == toss.HOLD else 0.0
        top = cy - COIN_R - COIN_HOP_PX * tt.hop(age) + bob
        hud.toss_coin(canvas, v, cx, top, squash, face)
        if squash > 0.45:
            hud.text(canvas, v, self._name(face), 14, C.WHITE, (cx, top + COIN_R), bold=True,
                     center=True)  # fmt: skip
        if phase == toss.LAND:
            words, size, colour = t("net.breaks", name=self._name(tt.breaker)), 18, C.WHITE
        else:
            words, size, colour = t("net.coin"), 17, C.TEXT
        hud.text(canvas, v, words, size, colour, (cx, cy + COIN_R + 26), bold=True, center=True)

    # --- the result card: both players, and a card for a connection that ended ---
    def _result_numbers(self) -> tuple[list[list[int]], list[list[float]]]:
        """What the card shows now: rows (score, shots, fouls) by column (you, them)."""
        m, age = self.session.match, self._clock - self._ended_at
        names = ("score", "shots", "fouls")
        if not self._tallies:  # not counting: whole
            whole = [[m.score(i), m.shots[i], m.fouls[i]] for i in (self._me, self._them)]
            return [[whole[c][r] for c in (0, 1)] for r in range(3)], [[0.0, 0.0]] * 3
        values = [[tl.value(n, age) for tl in self._tallies] for n in names]
        flashes = [[tl.flash(n, age) for tl in self._tallies] for n in names]
        return values, flashes

    def _result_words(self) -> tuple[str | None, bool]:
        m = self.session.match
        won = m.winner == self._me
        last = m.last
        if last is None or not last.reason:
            return None, won
        if last.shooter == self._me:
            return t(last.reason), won
        key = WON_REASONS.get(last.reason, "net.won_foul")
        return t(key, name=self._name(last.shooter)), won

    def _names_row(self) -> tuple[tuple[str, str], tuple[bool, bool]]:
        won = self.session.match.winner == self._me
        return (self._name(self._me), self._name(self._them)), (won, not won)

    def _row_names(self) -> tuple[str, str, str, str]:
        return (t("result.score"), t("hud.shots"), t("hud.fouls"), t("net.wins_row"))

    def _wins(self) -> tuple[int, int]:
        """Games won in this room so far: yours, theirs."""
        return (self.session.wins[self._me], self.session.wins[self._them])

    def _card_wins(self) -> tuple[int, int]:
        """The games won BEFORE this one: what the row of the result card and (once the point of
        the game before has come in) the plates show. The point of this game is added at the
        start of the next one, between the plates (the player sees it come in)."""
        won = list(self.session.wins)
        if self.session.match.over and self.session.counted:
            won[self.session.match.winner] -= 1
        return (won[self._me], won[self._them])

    def _again_view(self) -> tuple[tuple[str, bool], tuple[str, tuple[int, int, int]] | None]:
        """The Rematch button (its words, can it be pressed) and the line above the buttons."""
        state, name = self._rematch_state(), self._name(self._them)
        if state == "wait":
            words = t("net.rematch.wait", name=name)
            if hud.text_width(self.view, words, 17, True) > WAIT_LABEL_MAX:
                words = t("net.rematch.wait_short")
            return (words, False), None
        if state == "gone":
            return (t("net.again"), False), (t("net.rematch.gone", name=name), C.TEXT_DIM)
        note = (
            (t("net.rematch.they_asked", name=name), C.MAGENTA) if state == "they_asked" else None
        )
        return (t("net.again"), True), note

    def _draw_result_frame(self, canvas: pg.Surface, v: View) -> None:
        if self._ended_note is not None:
            title, line = self._ended_note
            hud.draw_notice_frame(canvas, v, t(title), line)
            return
        reason, won = self._result_words()
        names, won_by = self._names_row()
        hud.draw_net_result_frame(canvas, v, won=won, reason=reason, names=names, won_by=won_by,
                                  row_names=self._row_names(), wins=self._card_wins())  # fmt: skip

    def _draw_result_live(self, canvas: pg.Surface, v: View) -> None:
        if self._ended_note is not None:
            hud.draw_notice_live(canvas, v, self.result_fx, self._clock)
            return
        values, flashes = self._result_numbers()
        again, note = self._again_view()
        hud.draw_net_result_live(canvas, v, values=values, flashes=flashes, fx=self.result_fx,
                                 clock=self._clock, again=again, note=note)  # fmt: skip

    def _draw_result(self, canvas: pg.Surface, v: View) -> None:
        age = self._clock - self._ended_at
        if self._ended_note is not None:
            title, line = self._ended_note
            hud.draw_notice(canvas, v, t(title), line, age, self.result_fx, self._clock)
            return
        reason, won = self._result_words()
        names, won_by = self._names_row()
        values, flashes = self._result_numbers()
        again, note = self._again_view()
        hud.draw_net_result(canvas, v, won=won, reason=reason, names=names, won_by=won_by,
                            row_names=self._row_names(), wins=self._card_wins(), values=values,
                            flashes=flashes, again=again, note=note, age=age, fx=self.result_fx,
                            clock=self._clock)  # fmt: skip
