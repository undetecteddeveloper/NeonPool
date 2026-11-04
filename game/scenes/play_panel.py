"""The Play panel: a lit panel over the menu with two big choices, Solo and Two players. Solo goes
on to Free play or Practice, and Practice to its three runs (Beat the Ghost, Call the Pocket,
Sprint). Two players goes on in the same panel: your name, then Create a room (a four-letter
code from the relay to give your friend, and a wait) or Join a room (type the code). Everything
is one panel changing steps. On the same network the guest goes straight to the host
(`net/relay.py`).

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

CHOOSE, MODE, PRACTICE, LEVEL, SETUP, HOSTING, JOINING, CONNECTING = (
    "choose", "mode", "practice", "level", "setup", "hosting", "joining", "connecting",
)  # fmt: skip
ITEMS = {
    CHOOSE: ("solo", "duo", "back"),
    MODE: ("free", "practice", "back"),  # Solo, no game in progress: Free play / Practice
    PRACTICE: (*config.PRACTICE_MODES, "back"),  # Practice: one button per kind of run
    LEVEL: ("level", "start", "back"),  # after a run: its level, what that means, then Start
    SETUP: ("name", "create", "join", "back"),
    HOSTING: ("cancel",),
    JOINING: ("code", "go", "back"),
    CONNECTING: ("cancel",),
}
PANEL = pg.Rect(400, 150, 480, 440)  # the column and the centre; the height is the step's
X, W = PANEL.x + 44, PANEL.w - 88  # the column everything sits in
# each step is only as tall as what it holds; the frame sits centred and glides between heights
HEIGHT = {
    CHOOSE: 344,
    MODE: 344,
    PRACTICE: 432,
    LEVEL: 326,  # with a one-line caption; the real height comes from the words (see `_level`)
    SETUP: 412,
    HOSTING: 404,
    JOINING: 342,
    CONNECTING: 230,
}
TOP = {step: PANEL.centery - h // 2 for step, h in HEIGHT.items()}  # where each step's frame starts


# the Level step: the Level row, a caption under it saying what the level means, Start and Back
LEVEL_ROW_Y, LEVEL_ROW_H = 92, 44
CAPTION_SIZE, CAPTION_STEP, CAPTION_PAD = 14, 18, 16  # text size, line step, side room
CAPTION_GAP, START_GAP, START_H = 14, 20, 50  # row -> caption, caption -> Start, Start's height


def _at(step: str, y: int, h: int) -> pg.Rect:
    return pg.Rect(X, TOP[step] + y, W, h)


def _back(step: str) -> pg.Rect:
    return pg.Rect(PANEL.centerx - 80, TOP[step] + HEIGHT[step] - 62, 160, 44)


RECTS = {
    CHOOSE: {"solo": _at(CHOOSE, 92, 76), "duo": _at(CHOOSE, 180, 76), "back": _back(CHOOSE)},
    MODE: {"free": _at(MODE, 92, 76), "practice": _at(MODE, 180, 76), "back": _back(MODE)},
    PRACTICE: {
        "ghost": _at(PRACTICE, 92, 76),
        "call": _at(PRACTICE, 180, 76),
        "sprint": _at(PRACTICE, 268, 76),
        "back": _back(PRACTICE),
    },
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
BACK_BELOW = 26  # the space between the last choice and Back
BACK_H, BACK_MARGIN = 44, 18  # Back is this tall, with this much frame under it
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
        self.mode = config.PRACTICE_MODES[0]  # the run chosen on the Practice step
        self.level = app.settings.practice_level  # the level on the Level step (saved on Start)
        self._level_cache: dict[tuple, tuple] = {}  # (view scale, caption) -> see `_level`
        self.room: relay.HostRoom | None = None
        self.join: relay.Join | None = None
        self.session: net_session.Session | None = None
        self._clock = 0.0

    def title(self) -> str:
        if self.step == LEVEL:
            return t(f"practice.mode.{self.mode}")  # the run just chosen
        return t("play.title") if self.step in (CHOOSE, MODE, PRACTICE) else t("net.title")

    # --- what the rest of the game asks ---
    @property
    def typing(self) -> bool:
        """A field has the keyboard (the game's own single-key shortcuts must keep out of it)."""
        return self.is_open and self._item() in FIELDS

    def _item(self) -> str:
        return ITEMS[self.step][self.sel]

    def _level(self, level: str | None = None) -> tuple[int, dict[str, pg.Rect], list[str], int]:
        """The Level step made from its words, for `level` (default: the one shown): its caption
        broken into lines that fit (at this window's scale, in this language), the frame as tall
        as the row, those lines, Start and Back, and nothing left empty. Returns (frame height,
        the rects, the caption lines, where they start)."""
        v = self._v or View(1.0)
        sub = t(f"practice.level.{level or self.level}_sub")
        hit = self._level_cache.get((v.s, sub))
        if hit is None:
            lines = hud.wrap(v, sub, CAPTION_SIZE, W - 2 * CAPTION_PAD) or [sub]
            caption_y = LEVEL_ROW_Y + LEVEL_ROW_H + CAPTION_GAP
            start_y = caption_y + len(lines) * CAPTION_STEP + START_GAP
            h = start_y + START_H + BACK_BELOW + BACK_H + BACK_MARGIN
            top = PANEL.centery - h // 2
            rects = {
                "level": pg.Rect(X, top + LEVEL_ROW_Y, W, LEVEL_ROW_H),
                "start": pg.Rect(X, top + start_y, W, START_H),
                "back": pg.Rect(PANEL.centerx - 80, top + h - BACK_H - BACK_MARGIN, 160, BACK_H),
            }
            hit = (h, rects, lines, top + caption_y)
            self._level_cache = {**self._level_cache, (v.s, sub): hit}
        return hit

    def _height(self, step: str) -> int:
        return self._level()[0] if step == LEVEL else HEIGHT[step]

    def _rects(self) -> dict[str, pg.Rect]:
        return self._level()[1] if self.step == LEVEL else RECTS[self.step]

    def fit_h(self) -> float:
        return self._height(self.step)

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
        self._morph_begin(self._height(step))  # (a picture of the step we leave, while it is here)
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
            self.error = None
            self._goto(MODE)
        elif item == "free":
            self.dismiss()
            self.app.go_play()
        elif item == "practice":
            self._goto(PRACTICE)
        elif item in config.PRACTICE_MODES:
            self.mode = item
            self.level = self.app.settings.practice_level  # (the one played last is shown)
            self._goto(LEVEL, ITEMS[LEVEL].index("start"))
        elif item == "level":
            self._step_level(1)  # (Enter on the row changes it, as on Settings' rows)
        elif item == "start":
            self.dismiss()
            self.app.change_settings(practice_level=self.level)
            self.app.go_practice(self.mode, self.level)
        elif item == "duo":
            self.error = None
            self._goto(SETUP)
        elif item == "back":
            if self.step == CHOOSE:
                self.close()
            elif self.step == MODE:
                self._goto(CHOOSE)
            elif self.step == PRACTICE:
                self._goto(MODE, ITEMS[MODE].index("practice"))
            elif self.step == LEVEL:
                self._goto(PRACTICE, ITEMS[PRACTICE].index(self.mode))
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

    def _step_level(self, direction: int) -> None:
        """Easy <-> Hard. A caption of another length means another height: the frame glides."""
        levels = config.PRACTICE_LEVELS
        new = levels[(levels.index(self.level) + direction) % len(levels)]
        if self._level(new)[0] != self.fit_h():
            self._morph_begin(self._level(new)[0])  # (a picture of the step as it is, to fade out)
        self.level = new

    def _nudge_level(self, direction: int) -> None:
        self.app.audio.play_click()
        self.fx.press("level", self._clock)
        self._step_level(direction)

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
                rect = self._rects()[item]
                if rect.collidepoint(e.pos):
                    self._choose(i)
                    if item == "level":  # the arrow the player pressed: back or on
                        left = e.pos[0] < rect.right - hud.CHOOSER_FROM_RIGHT
                        self._nudge_level(-1 if left else 1)
                    else:
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
        elif self._item() == "level" and key in (pg.K_LEFT, pg.K_a, pg.K_RIGHT, pg.K_d):
            self._nudge_level(1 if key in (pg.K_RIGHT, pg.K_d) else -1)
        elif key in (pg.K_RETURN, pg.K_KP_ENTER) or (key == pg.K_SPACE and not typing):
            self._activate(self._item())

    # --- time ---
    def update(self, dt: float) -> None:
        self._clock += dt
        self._animate(dt)
        if not self.is_open:
            return
        if self.step == LEVEL and self._morph is None:
            self._h = None  # the height follows the words, whatever the window is now
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
        cx, top = PANEL.centerx, TOP.get(step, 0)  # (the Level step is placed by `_level`)
        item = self._item()

        def button(key: str, label: str, sub: str | None = None) -> None:
            hud.live_button(canvas, pv, rects[key], label, self.fx, key, self._clock, sub=sub)

        if step == CHOOSE:
            button("solo", t("play.solo"), t("play.solo_sub"))
            button("duo", t("play.duo"), t("play.duo_sub"))
            button("back", t("play.back"))
        elif step == MODE:
            button("free", t("play.free"), t("play.free_sub"))
            button("practice", t("play.practice"), t("play.practice_sub"))
            button("back", t("play.back"))
        elif step == PRACTICE:
            for mode in config.PRACTICE_MODES:
                button(mode, t(f"practice.mode.{mode}"), t(f"practice.mode.{mode}_sub"))
            button("back", t("play.back"))
        elif step == LEVEL:
            _, _, lines, y = self._level()
            word = t(f"practice.level.{self.level}")
            hud.chooser_row(canvas, pv, rects["level"], t("practice.level"), word, self.fx,
                            "level", self._clock)  # fmt: skip
            for i, line in enumerate(lines):
                hud.text(canvas, pv, line, CAPTION_SIZE, C.TEXT_DIM,
                         (cx, y + CAPTION_STEP * (i + 0.5)), center=True)  # fmt: skip
            button("start", t("practice.start"))
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
