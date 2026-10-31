"""The developer's panel drawn over the game: a list of states, picked with the keys or the mouse.

F1 opens and closes it. While it is open it takes every key and click, so the game underneath
cannot be disturbed; closed, it takes only the F-keys of `HOTKEYS` and a small status line.
"""

from __future__ import annotations

import logging

import pygame as pg

from game.config import LOGICAL_SIZE
from game.render import hud
from game.render import palette as C
from game.render.draw import blit_rrect
from game.render.view import View
from game.render.viewport import window_to_logical
from tools.devkit.harness import Harness
from tools.devkit.states import STATES, State

log = logging.getLogger("neonpool.dev")
X, Y, W, H = 16, 16, 460, 688  # the panel (logical px)
ROW_H = 22
HEAD_H = 50  # title and status
FOOT_H = 78  # the keys and the last result
HOTKEYS = (
    (pg.K_F2, "F2", "chạy lại trạng thái vừa chọn"),
    (pg.K_F3, "F3", "bot tự chơi bật / tắt"),
    (pg.K_F4, "F4", "cắt mạng / nối lại"),
    (pg.K_F5, "F5", "bot đánh một cú"),
    (pg.K_F6, "F6", "đồng hồ của tôi còn 10 giây"),
)


class DevPanel:
    def __init__(self, harness: Harness, states: list[State] | None = None) -> None:
        self.h = harness
        self.states = states if states is not None else STATES
        self.is_open = False
        self.sel = 0
        self.top = 0  # first visible row
        self.last: int | None = None
        self.message = ""
        self.ok = True
        self.rows: list[tuple[str, str | int]] = []  # ("head", group) or ("item", state index)
        group = None
        for i, st in enumerate(self.states):
            if st.group != group:
                group = st.group
                self.rows.append(("head", group))
            self.rows.append(("item", i))

    # ------------------------------------------------------------------ doing things
    def run(self, index: int) -> bool:
        """Put the game in state `index`. A state that fails is reported, never fatal."""
        st = self.states[index]
        self.last = index
        try:
            self.h.last_error = None
            st.run(self.h)
        except Exception as exc:
            log.exception("state %r failed", st.name)
            self.message, self.ok = f"LỖI: {st.name}: {exc}", False
            return False
        self.message, self.ok = f"đã vào: {st.name}", True
        return True

    def hotkey(self, key: int) -> bool:
        h = self.h
        if key == pg.K_F2 and self.last is not None:
            self.run(self.last)
        elif key == pg.K_F3:
            h.ensure_net()
            h.bot.auto = not h.bot.auto
        elif key == pg.K_F4 and h.room is not None:
            h.room.reconnect() if h.mine.link_down_s is not None else h.room.cut()
        elif key == pg.K_F5:
            h.ensure_net()
            h.bot.play_once()
        elif key == pg.K_F6:
            h.ensure_net()
            h.set_clock(10.0)
        else:
            return False
        return True

    # ------------------------------------------------------------------ events
    def _row_of(self, index: int) -> int:
        return next(r for r, (kind, v) in enumerate(self.rows) if kind == "item" and v == index)

    def _visible(self) -> int:
        return (H - HEAD_H - FOOT_H) // ROW_H

    def _show(self, index: int) -> None:
        """Scroll so that the chosen state (and the heading above it, if it has one) is in view."""
        row = self._row_of(index)
        first = row - 1 if row and self.rows[row - 1][0] == "head" else row
        if first < self.top:
            self.top = first
        elif row >= self.top + self._visible():
            self.top = row - self._visible() + 1

    def handle_event(self, e: pg.event.Event, window: tuple[int, int]) -> bool:
        """True if the panel used the event (always, while it is open)."""
        if e.type == pg.KEYDOWN:
            if e.key == pg.K_F1:
                self.is_open = not self.is_open
                return True
            if not self.is_open:
                return self.hotkey(e.key)
            n = len(self.states)
            if e.key == pg.K_ESCAPE:
                self.is_open = False
            elif e.key in (pg.K_UP, pg.K_k):
                self.sel = (self.sel - 1) % n
            elif e.key in (pg.K_DOWN, pg.K_j):
                self.sel = (self.sel + 1) % n
            elif e.key == pg.K_PAGEUP:
                self.sel = max(0, self.sel - self._visible() + 1)
            elif e.key == pg.K_PAGEDOWN:
                self.sel = min(n - 1, self.sel + self._visible() - 1)
            elif e.key == pg.K_HOME:
                self.sel = 0
            elif e.key == pg.K_END:
                self.sel = n - 1
            elif e.key in (pg.K_RETURN, pg.K_KP_ENTER, pg.K_SPACE):
                self.is_open = not self.run(self.sel)  # (a state that failed leaves the panel up)
            self._show(self.sel)
            return True
        if not self.is_open:
            return False
        if e.type == pg.MOUSEWHEEL:
            limit = max(0, len(self.rows) - self._visible())
            self.top = max(0, min(limit, self.top - e.y * 3))
        elif e.type in (pg.MOUSEMOTION, pg.MOUSEBUTTONDOWN):
            x, y = window_to_logical(e.pos, window, LOGICAL_SIZE)
            row = self.top + int((y - (Y + HEAD_H)) // ROW_H)
            if X < x < X + W and Y + HEAD_H <= y < Y + H - FOOT_H and 0 <= row < len(self.rows):
                kind, value = self.rows[row]
                if kind == "item":
                    self.sel = value
                    if e.type == pg.MOUSEBUTTONDOWN and e.button == 1:
                        self.is_open = not self.run(value)
        return True

    # ------------------------------------------------------------------ drawing
    def draw(self, screen: pg.Surface) -> None:
        v = View.for_window(screen.get_size())
        status = self.h.status()
        hud.text(
            screen, v, f"DEV · {status} · F1 mở bảng", 11, C.TEXT_DIM, (1270, 706), align="right"
        )
        if not self.is_open:
            return
        blit_rrect(screen, v, X, Y, W, H, 10, C.PANEL, 1.6, C.VIOLET, 0.5)
        hud.text(screen, v, "BẢNG DEV — chọn trạng thái", 16, C.WHITE, (X + 18, Y + 20), bold=True)
        hud.text(screen, v, status, 11, C.TEXT_DIM, (X + 18, Y + 38))
        y0 = Y + HEAD_H + 8
        for r in range(self.top, min(len(self.rows), self.top + self._visible())):
            kind, value = self.rows[r]
            y = y0 + (r - self.top) * ROW_H
            if kind == "head":
                hud.text(screen, v, str(value).upper(), 11, C.CYAN, (X + 18, y + 4), bold=True)
                continue
            if value == self.sel:
                blit_rrect(
                    screen, v, X + 8, y - 4, W - 16, ROW_H, 5, C.PANEL_HOT, 1.2, C.MAGENTA, 0.5
                )
            colour = C.WHITE if value == self.sel else C.TEXT
            mark = ">" if value == self.last else " "
            hud.text(screen, v, f"{mark} {self.states[value].name}", 13, colour, (X + 22, y + 2))
        fy = Y + H - FOOT_H + 4
        hud.text(
            screen,
            v,
            "Lên/Xuống, PgUp, PgDn: chọn · Enter: chạy · Esc hoặc F1: đóng",
            11,
            C.TEXT_DIM,
            (X + 18, fy),
        )
        keys = "  ".join(f"{k} {what}" for _, k, what in HOTKEYS[:3])
        keys2 = "  ".join(f"{k} {what}" for _, k, what in HOTKEYS[3:])
        hud.text(screen, v, keys, 10, C.TEXT_DIM, (X + 18, fy + 16))
        hud.text(screen, v, keys2, 10, C.TEXT_DIM, (X + 18, fy + 30))
        if self.message:
            hud.text(
                screen, v, self.message[:70], 11, C.OK if self.ok else C.ERROR, (X + 18, fy + 50)
            )
