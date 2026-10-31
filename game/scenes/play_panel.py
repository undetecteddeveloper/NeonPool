"""The Play panel: a lit panel over the menu with two big choices, Solo and Two players. Two
players goes on in the same panel: your name, then Create a room (a four-letter code from the
relay to give your friend, and a wait) or Join a room (type the code). Everything is one panel
changing steps. On the same network the guest goes straight to the host (`net/relay.py`).

Keys: up/down (or Tab) choose, Enter does it, Esc goes back a step (and closes at the first one).
While a field has the keyboard, typed letters go into it (and M, W, S are just letters).
See docs/GAME_DESIGN.md (network play).
"""

from __future__ import annotations

import logging
import os

import pygame as pg

from game import config
from game.i18n import t
from game.net import protocol as p
from game.net import relay, tcp
from game.net import session as net_session
from game.render import hud
from game.render import palette as C
from game.render.floating import FloatPanel
from game.render.view import View

log = logging.getLogger("neonpool")

CHOOSE, SETUP, HOSTING, JOINING, CONNECTING = "choose", "setup", "hosting", "joining", "connecting"
ITEMS = {
    CHOOSE: ("solo", "duo", "back"),
    SETUP: ("name", "create", "join", "back"),
    HOSTING: ("cancel",),
    JOINING: ("code", "go", "back"),
    CONNECTING: ("cancel",),
}
PANEL = pg.Rect(400, 150, 480, 440)  # the column and the centre; the height is the step's
X, W = PANEL.x + 44, PANEL.w - 88  # the column everything sits in
# each step is only as tall as what it holds; the frame sits centred and glides between heights
HEIGHT = {CHOOSE: 344, SETUP: 412, HOSTING: 404, JOINING: 342, CONNECTING: 230}
TOP = {step: PANEL.centery - h // 2 for step, h in HEIGHT.items()}  # where each step's frame starts


def _at(step: str, y: int, h: int) -> pg.Rect:
    return pg.Rect(X, TOP[step] + y, W, h)


def _back(step: str) -> pg.Rect:
    return pg.Rect(PANEL.centerx - 80, TOP[step] + HEIGHT[step] - 62, 160, 44)


RECTS = {
    CHOOSE: {"solo": _at(CHOOSE, 92, 76), "duo": _at(CHOOSE, 180, 76), "back": _back(CHOOSE)},
    SETUP: {
        "name": _at(SETUP, 122, 46),
        "create": _at(SETUP, 192, 50),
        "join": _at(SETUP, 254, 50),
        "back": _back(SETUP),
    },
    HOSTING: {"cancel": _back(HOSTING)},
    JOINING: {"code": _at(JOINING, 122, 46), "go": _at(JOINING, 206, 50), "back": _back(JOINING)},
    CONNECTING: {"cancel": _back(CONNECTING)},
}
FIELDS = ("name", "code")
# why a session ended -> the words shown (net.err.*)
CLOSE_ERRORS = {
    net_session.CLOSE_VERSION: "net.err.version",
    net_session.CLOSE_BUSY: "net.err.busy",
    net_session.CLOSE_TIMEOUT: "net.err.timeout",
}
# why the relay or the room said no -> the words shown
RELAY_ERRORS = {
    relay.ERR_NO_SERVER: "net.err.no_server",
    relay.ERR_OFFLINE: "net.err.offline",
    relay.ERR_BUSY: "net.err.server_busy",
    relay.ERR_VERSION: "net.err.version",
    relay.ERR_BAD_CODE: "net.err.bad_code",
    relay.ERR_NO_ROOM: "net.err.no_room",
    relay.ERR_FULL: "net.err.busy",
    relay.ERR_AWAY: "net.err.away",
    relay.ERR_GONE: "net.err.room_closed",
    relay.ERR_IDLE: "net.err.room_closed",
}


def net_port() -> int:
    """The room's door on this network: NEONPOOL_NET_PORT for two games on one machine (tests,
    the smoke run). A port that is taken is no problem: the room takes any free one."""
    try:
        port = int(os.environ.get("NEONPOOL_NET_PORT", config.NET_PORT))
    except ValueError:
        return config.NET_PORT
    return port if 1 <= port <= 65535 else config.NET_PORT


def spin_key() -> str:
    """The spin set the host plays with (the player-testing switch of solo play, if it is set)."""
    key = os.environ.get("NEONPOOL_SPIN_SET", "")
    return key if key in config.SPIN_SETS else config.DEFAULT_SPIN


class PlayPanel(FloatPanel):
    RECT = PANEL
    RESIZES = True

    def __init__(self, app) -> None:
        super().__init__()
        self.app = app
        self.step = CHOOSE
        self.sel = 0
        self.fx = hud.ButtonFx()
        self.name = ""
        self.code = ""  # the code being typed
        self.error: str | None = None  # an i18n key
        self.room: relay.HostRoom | None = None
        self.join: relay.Join | None = None
        self.session: net_session.Session | None = None
        self._clock = 0.0

    def title(self) -> str:
        return t("play.title") if self.step == CHOOSE else t("net.title")

    # --- what the rest of the game asks ---
    @property
    def typing(self) -> bool:
        """A field has the keyboard (the game's own single-key shortcuts must keep out of it)."""
        return self.is_open and self._item() in FIELDS

    def _item(self) -> str:
        return ITEMS[self.step][self.sel]

    def _rects(self) -> dict[str, pg.Rect]:
        return RECTS[self.step]

    def fit_h(self) -> float:
        return HEIGHT[self.step]

    def prewarm(self, v: View) -> None:
        """Every step's sprites, not just the first one's: a step is then a plain change."""
        if self._warm == v.s:
            return
        step, sel = self.step, self.sel
        for each in ITEMS:
            self.step, self.sel, self._warm = each, 0, 0.0
            super().prewarm(v)
        self.step, self.sel = step, sel

    # --- opening, closing, steps ---
    def open(self) -> None:
        self.name = self.app.settings.player_name
        self.error = None
        self._goto(CHOOSE)
        self._open()

    def close(self) -> None:
        self._drop_connection()
        self._text_input(False)
        self._close()
        self.app.audio.play_click()

    def dismiss(self) -> None:
        """Gone at once (the game is moving on to another scene)."""
        self._drop_connection()
        self._text_input(False)
        self.is_open = self._closing = False
        self.k = 0.0
        self._h = self._morph = None
        self._frozen.clear()

    def _goto(self, step: str, sel: int | None = None) -> None:
        self._morph_begin(HEIGHT[step])  # (a picture of the step we leave, while it is still here)
        self.step = step
        if sel is None:
            sel = 1 if step == SETUP and self.name.strip() else 0
        self.sel = sel
        self.fx = hud.ButtonFx()
        self._frozen.rebake()  # the title may have changed
        self._text_input(self._item() in FIELDS)

    @staticmethod
    def _text_input(on: bool) -> None:
        try:
            (pg.key.start_text_input if on else pg.key.stop_text_input)()
        except pg.error:
            pass

    def _drop_connection(self) -> None:
        if self.room is not None:
            self.room.close()
        self.room = self.join = None
        if self.session is not None:
            self.session.leave()
        self.session = None

    def _choose(self, i: int) -> None:
        if i != self.sel:
            self.sel = i
            self.app.audio.play_hover()
            self._text_input(self._item() in FIELDS)

    # --- doing things ---
    def _activate(self, item: str) -> None:
        audio = self.app.audio
        audio.play_click()
        self.fx.press(item, self._clock)
        if item == "solo":
            self.dismiss()
            self.app.go_play()
        elif item == "duo":
            self.error = None
            self._goto(SETUP)
        elif item == "back":
            if self.step == CHOOSE:
                self.close()
            else:
                self.error = None
                self._goto(CHOOSE if self.step == SETUP else SETUP)
        elif item == "name":
            self._choose(1)
        elif item == "create":
            self._start_hosting()
        elif item == "join":
            self.error = None
            self._goto(JOINING)
        elif item == "code":
            self._choose(1)
        elif item == "go":
            self._start_joining()
        elif item == "cancel":
            self._drop_connection()
            self.error = None
            self._goto(SETUP if self.step == HOSTING else JOINING)

    def display_name(self) -> str:
        return p.clean_name(self.name) or t("net.default_name")

    def _save_name(self) -> None:
        name = p.clean_name(self.name)
        if name != self.app.settings.player_name:
            self.app.change_settings(player_name=name)

    def _start_hosting(self) -> None:
        self._save_name()
        self.error = None
        self.room = relay.HostRoom(port=net_port())
        self._goto(HOSTING)

    def _hosting_failed(self, error_key: str) -> None:
        self._drop_connection()
        self.error = error_key
        self._goto(SETUP)

    def _start_joining(self) -> None:
        if not relay.is_code(self.code):
            self.error = "net.err.bad_code"
            return
        self._save_name()
        self.error = None
        self.join = relay.Join(self.code)
        self._goto(CONNECTING)

    def _join_failed(self, error_key: str) -> None:
        self.join = None
        if self.session is not None:
            self.session = None
        self.error = error_key
        self._goto(JOINING)

    def _begin_match(self) -> None:
        session, self.session = self.session, None
        if self.room is not None:  # the room stays open: the guest may have to come back in
            session.set_relink(relay.HostRelink(self.room))
        elif self.join is not None:  # ... and the guest knows the way back
            session.set_relink(relay.GuestRelink(self.join))
        self.room = self.join = None
        self.dismiss()
        self.app.start_net(session)

    # --- input ---
    def _type(self, chars: str) -> None:
        item = self._item()
        if item == "name":
            keep = "".join(c for c in chars if c.isprintable())
            self.name = (self.name + keep)[: config.NET_NAME_MAX]
        elif item == "code":
            short = len(self.code) < config.NET_ROOM_LEN
            self.code = relay.clean_code(self.code + chars)
            self.error = None
            if short and relay.is_code(self.code):  # the last letter is in: off it goes
                self._activate("go")

    def handle_event(self, e: pg.event.Event) -> None:
        if e.type == pg.TEXTINPUT:
            self._type(e.text)
        elif e.type == pg.KEYDOWN:
            self._key(e.key)
        elif e.type == pg.MOUSEMOTION:
            for i, item in enumerate(ITEMS[self.step]):
                if self._rects()[item].collidepoint(e.pos):
                    self._choose(i)
        elif e.type == pg.MOUSEBUTTONDOWN and e.button == 1:
            for i, item in enumerate(ITEMS[self.step]):
                if self._rects()[item].collidepoint(e.pos):
                    self._choose(i)
                    self._activate(item)
                    return
            if self.step == CHOOSE and not self.rect().collidepoint(e.pos):
                self.close()  # a click outside the first step closes it, as in Settings

    def _key(self, key: int) -> None:
        n = len(ITEMS[self.step])
        typing = self._item() in FIELDS
        if key == pg.K_ESCAPE:
            self._activate("back" if "back" in ITEMS[self.step] else "cancel")
        elif key == pg.K_UP or (key == pg.K_w and not typing):
            self._choose((self.sel - 1) % n)
        elif key in (pg.K_DOWN, pg.K_TAB) or (key == pg.K_s and not typing):
            self._choose((self.sel + 1) % n)
        elif key == pg.K_BACKSPACE and typing:
            if self._item() == "name":
                self.name = self.name[:-1]
            else:
                self.code, self.error = self.code[:-1], None
        elif key in (pg.K_RETURN, pg.K_KP_ENTER) or (key == pg.K_SPACE and not typing):
            self._activate(self._item())

    # --- time ---
    def update(self, dt: float) -> None:
        self._clock += dt
        self._animate(dt)
        if not self.is_open:
            return
        self.fx.update(dt, self._item(), self._rects(), self._clock)
        if self.room is not None and self.session is None:
            transport = self.room.accept()
            if self.room.state == relay.FAILED:
                self._hosting_failed(RELAY_ERRORS.get(self.room.error, "net.err.offline"))
            elif transport is not None:
                feel = config.DEFAULT_FEEL
                self.session = net_session.Session(
                    transport, True, self.display_name(), feel=feel, spin=spin_key()
                )
        if self.join is not None and self.session is None:
            transport = self.join.result()
            if transport is not None:
                self.session = net_session.Session(transport, False, self.display_name())
            elif self.join.state == tcp.CONNECT_FAILED:
                self._join_failed(RELAY_ERRORS.get(self.join.error, "net.err.offline"))
        if self.session is not None:
            self.session.update(dt)
            if self.session.playing:
                self._begin_match()
            elif self.session.phase == net_session.CLOSED:
                key = CLOSE_ERRORS.get(self.session.close_reason, "net.err.timeout")
                if self.step == HOSTING:  # a guest who could not come in: keep the room open
                    self.session, self.error = None, key
                else:
                    self._join_failed(key)

    # --- drawing ---
    def _paint_live(self, canvas: pg.Surface, pv: View) -> None:
        step, rects = self.step, self._rects()
        cx, top = PANEL.centerx, TOP[step]
        item = self._item()

        def button(key: str, label: str, sub: str | None = None) -> None:
            hud.live_button(canvas, pv, rects[key], label, self.fx, key, self._clock, sub=sub)

        if step == CHOOSE:
            resume = self.app.game_in_progress()
            button("solo", t("play.resume" if resume else "play.solo"),
                   t("play.resume_sub" if resume else "play.solo_sub"))  # fmt: skip
            button("duo", t("play.duo"), t("play.duo_sub"))
            button("back", t("play.back"))
        elif step == SETUP:
            hud.label(canvas, pv, t("net.name"), (X, top + 104), C.TEXT_DIM, 13)
            hud.text_field(canvas, pv, rects["name"], self.name, focus=item == "name",
                           clock=self._clock, placeholder=t("net.name_hint"))  # fmt: skip
            button("create", t("net.create"))
            button("join", t("net.join"))
            if self.error:  # the line under the buttons is only for what went wrong
                hud.text(canvas, pv, t(self.error), 13, C.ERROR, (cx, top + 326), center=True)
            button("back", t("play.back"))
        elif step == HOSTING:
            hud.label(canvas, pv, t("net.code_title"), (cx, top + 106), C.TEXT_DIM, 13, center=True)
            code = self.room.code if self.room is not None else ""
            hud.code_tiles(canvas, pv, pg.Rect(X, top + 128, W, 74), code, clock=self._clock)
            hud.text(canvas, pv, t("net.code_howto"), 13, C.TEXT_DIM, (cx, top + 232), center=True)
            # one pulsing line, centred: the room is being made, then the wait for the friend
            status = t("net.waiting" if code else "net.making_room")
            hud.pulse_status(canvas, pv, status, (cx, top + 282), self._clock)
            if self.error:
                hud.text(canvas, pv, t(self.error), 13, C.ERROR, (cx, top + 314), center=True)
            button("cancel", t("net.cancel"))
        elif step == JOINING:
            hud.label(canvas, pv, t("net.type_code"), (X, top + 104), C.TEXT_DIM, 13)
            hud.code_tiles(canvas, pv, rects["code"], self.code, clock=self._clock,
                           focus=item == "code", error=bool(self.error))  # fmt: skip
            if self.error:
                hud.text(canvas, pv, t(self.error), 13, C.ERROR, (X, top + 184))
            button("go", t("net.go"))
            button("back", t("play.back"))
        else:  # CONNECTING
            hud.text(canvas, pv, t("net.connecting"), 20, C.AMBER, (cx, top + 124), bold=True,
                     center=True)  # fmt: skip
            button("cancel", t("net.cancel"))
