"""The table in a two-player game: the same table scene, with the other player on the network.

A `Session` (game/net/session.py) owns the simulation and the referee's word; this scene shows it
and turns the mouse into shots. Over the solo scene it adds: a coin toss at the start, two name
plates above the table (whose turn it is, group, balls left), the other player's cue moving as
they aim, the cue ball in hand placed by whoever fouled against, a result card with both players,
and a card when the connection ends. Esc twice in a row leaves (the proper surrender is later).
See docs/GAME_DESIGN.md (network play).
"""

from __future__ import annotations

import math

import pygame as pg

from game.config import GRAB_RADIUS_M, NOTICE_S, PX_PER_M
from game.i18n import t
from game.net import protocol as p
from game.net import session as net_session
from game.physics import Shot
from game.render import draw, hud
from game.render import palette as C
from game.render.draw import blit_rrect
from game.render.layout import OUTER_W, OUTER_X, to_m, to_px
from game.render.view import View
from game.rules.eight_ball import LOST, PLAYING, RERACK, WON
from game.rules.two_player import MatchShot
from game.scenes.play import CALLOUT_AT, CALLOUTS, PlayScene
from game.tally import Tally

# group -> (what you are told when YOU were given it, what you are told when the other player was)
GROUP_NOTICES = {
    "solid": ("notice.group_solid", "net.notice.group_them_solid"),
    "stripe": ("notice.group_stripe", "net.notice.group_them_stripe"),
}
COIN_S = 2.2  # the coin toss: it spins for COIN_FLIP_S, then says who breaks
COIN_FLIP_S = 1.5
COIN_R = 46.0
ESC_AGAIN_S = 3.0  # a second Esc within this long leaves the game


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
    RESULT_DEFAULT = "menu"  # the one button of the result card

    def _result_rects(self) -> dict[str, pg.Rect]:
        return {"menu": hud.NOTICE_BUTTON if self._ended_note else hud.NET_BUTTON}

    def __init__(self, app, session: net_session.Session) -> None:
        super().__init__(app)
        self.session = session
        self.world = session.world
        self.rules = NetRules(session, lambda: self._ended_note is not None)
        self._me, self._them = session.me, 1 - session.me
        self._seen_shots = session.shots_started
        self._started_at = self._clock  # the coin toss runs from here
        self._esc_at = -99.0
        self._net_notice: tuple[str, str] | None = None  # (kind, words)
        self._remote_alpha = 0.0  # the other player's cue fades in and out
        self._tallies: list[Tally] = []  # one per player, me first
        self._ended_note: tuple[str, str] | None = None  # (title key, words): the link ended
        self._result_shown = False

    # --- who is who ---
    def _name(self, player: int) -> str:
        return self.session.names[player] or t("net.default_name")

    def _toss_done(self) -> bool:
        return self._clock - self._started_at >= COIN_S

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
                return True
        elif e.type == pg.MOUSEMOTION and self.placing:
            self._place_ok = session.place_cue(*to_m(*e.pos))  # False: it stays on its last spot
        elif e.type == pg.MOUSEBUTTONUP and e.button == 1 and self.placing:
            self.placing = False
            session.release_cue()
            self.app.audio.play_click()
            return True
        return False

    def _key(self, key: int) -> None:
        if key != pg.K_ESCAPE:
            return  # no restart and no how-to-play card in the middle of a two-player game
        if self.drag.active:
            self.drag.cancel()
        elif self._clock - self._esc_at <= ESC_AGAIN_S:
            self.app.go_menu()
        else:
            self._esc_at = self._clock
            self._net_notice, self._notice_left = ("info", t("net.esc_again")), ESC_AGAIN_S

    def _result_event(self, e: pg.event.Event) -> None:
        button = self._result_rects()["menu"]
        if e.type == pg.MOUSEMOTION:
            hover = "menu" if button.collidepoint(e.pos) else None
            if hover is not None and hover != self._hover:
                self.app.audio.play_hover()
            self._hover = hover
        elif e.type == pg.MOUSEBUTTONDOWN and e.button == 1:
            if button.collidepoint(e.pos):
                self.app.audio.play_click()
                self.result_fx.press("menu", self._clock)
                self.app.go_menu()
        elif e.type == pg.KEYDOWN and e.key in (
            pg.K_RETURN, pg.K_KP_ENTER, pg.K_SPACE, pg.K_ESCAPE
        ):  # fmt: skip
            self.app.go_menu()

    # --- time ---
    def _step_world(self, dt: float) -> list:
        events = self.session.update(dt)
        if events:
            self._show_events(events)
        return events

    def update(self, dt: float) -> None:
        super().update(dt)
        s = self.session
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

    def _send_aim(self) -> None:
        s = self.session
        if self._can_aim() and self.drag.has_direction:
            s.set_aim(p.AIM_PULLING, self.drag.angle, self.drag.bar_length)
        elif self._can_aim() and self._cue_alpha > 0.05:
            s.set_aim(p.AIM_RESTING, self.knob.angle)
        else:
            s.set_aim(p.AIM_HIDDEN)

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
        if res.timed_out or res.outcome in (WON, LOST):
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
            lines.append((t("net.turn_you"), C.TEXT))
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
                turn=m.turn == player and not m.over and s.playing,
            )  # fmt: skip
        vs_at = (OUTER_X + OUTER_W / 2, hud.PLATE_Y + 31)
        hud.text(canvas, v, "VS", 20, C.VIOLET, vs_at, bold=True, center=True)

    def _draw_overlays(self, canvas: pg.Surface, v: View, over: bool) -> None:
        super()._draw_overlays(canvas, v, over)
        self._draw_toss(canvas, v)

    def _draw_toss(self, canvas: pg.Surface, v: View) -> None:
        """The coin that says who breaks: it spins, slows, and lands on the breaker's name."""
        age = self._clock - self._started_at
        if age >= COIN_S:
            return
        k = min(1.0, age / COIN_FLIP_S)
        end = math.pi * (6 + self.session.breaker)  # lands face-on, showing the breaker's name
        theta = end * (1 - (1 - k) ** 3)
        face = round(theta / math.pi) % 2
        squash = abs(math.cos(theta))
        cx, cy = CALLOUT_AT
        w = max(6.0, 2 * COIN_R * squash)
        colour = C.MAGENTA if face == 1 else C.CYAN
        radius = min(w, 2 * COIN_R) / 2
        blit_rrect(canvas, v, cx - w / 2, cy - COIN_R, w, 2 * COIN_R, radius, C.PANEL_HOT, 2.0,
                   colour, 0.9)  # fmt: skip
        if squash > 0.45:
            hud.text(canvas, v, self._name(face), 14, C.WHITE, (cx, cy), bold=True, center=True)
        if age < COIN_FLIP_S:
            hud.text(
                canvas, v, t("net.coin"), 17, C.TEXT, (cx, cy + COIN_R + 26), bold=True, center=True
            )
        else:
            who = t("net.breaks", name=self._name(self.session.breaker))
            hud.text(canvas, v, who, 18, C.WHITE, (cx, cy + COIN_R + 26), bold=True, center=True)

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
        key = "net.won_early" if last.reason.endswith("early") else "net.won_foul"
        return t(key, name=self._name(last.shooter)), won

    def _names_row(self) -> tuple[tuple[str, str], tuple[bool, bool]]:
        won = self.session.match.winner == self._me
        return (self._name(self._me), self._name(self._them)), (won, not won)

    def _draw_result_frame(self, canvas: pg.Surface, v: View) -> None:
        if self._ended_note is not None:
            title, line = self._ended_note
            hud.draw_notice_frame(canvas, v, t(title), line)
            return
        reason, won = self._result_words()
        names, won_by = self._names_row()
        rows = (t("result.score"), t("hud.shots"), t("hud.fouls"))
        hud.draw_net_result_frame(canvas, v, won=won, reason=reason, names=names, won_by=won_by,
                                  row_names=rows)  # fmt: skip

    def _draw_result_live(self, canvas: pg.Surface, v: View) -> None:
        if self._ended_note is not None:
            hud.draw_notice_live(canvas, v, self.result_fx, self._clock)
            return
        values, flashes = self._result_numbers()
        hud.draw_net_result_live(canvas, v, values=values, flashes=flashes, fx=self.result_fx,
                                 clock=self._clock)  # fmt: skip

    def _draw_result(self, canvas: pg.Surface, v: View) -> None:
        age = self._clock - self._ended_at
        if self._ended_note is not None:
            title, line = self._ended_note
            hud.draw_notice(canvas, v, t(title), line, age, self.result_fx, self._clock)
            return
        reason, won = self._result_words()
        names, won_by = self._names_row()
        values, flashes = self._result_numbers()
        hud.draw_net_result(canvas, v, won=won, reason=reason, names=names, won_by=won_by,
                            row_names=(t("result.score"), t("hud.shots"), t("hud.fouls")),
                            values=values, flashes=flashes, age=age, fx=self.result_fx,
                            clock=self._clock)  # fmt: skip
