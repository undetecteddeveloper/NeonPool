"""The settings panel: a lit panel that slides up over the menu (the menu keeps moving behind).

Language, volume, music volume, screen shake and the FPS counter. Mouse: click a row (or drag a
volume bar); keys: up/down choose a row, left/right change it, Enter switches, Esc closes. Every
change is applied at once and saved (App.change_settings), so it is still there next time.
"""

from __future__ import annotations

import pygame as pg

from game.config import VOLUME_STEP
from game.i18n import t
from game.render import hud
from game.render import palette as C
from game.render.draw import Aa, blit_dot, blit_rrect
from game.render.view import View

ROWS = ("lang", "volume", "music", "shake", "fps", "done")
BARS = ("volume", "music")  # the rows that are a level meter
PANEL = pg.Rect(400, 160, 480, 440)
ROW_X, ROW_W, ROW_H = 424, 432, 44
FIRST_ROW_Y, ROW_STEP = 242, 54
DONE = pg.Rect(560, 526, 160, 44)
TRACK = (642, 790)  # the level meters, left and right ends (logical x)
SWITCH_W, SWITCH_H = 52, 24
OPEN_S, CLOSE_S = 0.22, 0.16  # the panel slides up in / back down in this long
SLIDE_PX = 46  # ... from this far below


def row_rect(i: int) -> pg.Rect:
    if ROWS[i] == "done":
        return DONE
    return pg.Rect(ROW_X, FIRST_ROW_Y + i * ROW_STEP - ROW_H // 2, ROW_W, ROW_H)


class SettingsPanel:
    def __init__(self, app) -> None:
        self.app = app
        self.is_open = False
        self.sel = 0
        self.k = 0.0  # 0 closed .. 1 fully open
        self._closing = False
        self._dragging: str | None = None  # the level meter being dragged
        self._clock = 0.0
        self.fx = hud.ButtonFx()

    # --- opening and closing -------------------------------------------------------------
    def open(self) -> None:
        self.is_open, self._closing, self.sel = True, False, 0

    def close(self) -> None:
        self._closing, self._dragging = True, None
        self.app.audio.play_click()

    # --- changing values --------------------------------------------------------------------
    def _change(self, row: str, direction: int = 1) -> None:
        s = self.app.settings
        if row == "lang":
            self.app.change_settings(lang="en" if s.lang == "vi" else "vi")
        elif row in BARS:
            steps = round(getattr(s, row) / VOLUME_STEP) + direction
            self._set_level(row, steps * VOLUME_STEP)
            return
        elif row == "shake":
            self.app.change_settings(shake=not s.shake)
        elif row == "fps":
            self.app.change_settings(show_fps=not s.show_fps)
        elif row == "done":
            self.close()
            return
        self.app.audio.play_click()

    def _set_level(self, row: str, level: float) -> None:
        """Set the effects volume or the music volume (the music itself shows the new level)."""
        level = round(min(1.0, max(0.0, level)) / VOLUME_STEP) * VOLUME_STEP
        if abs(level - getattr(self.app.settings, row)) > 1e-6:
            self.app.change_settings(**{row: round(level, 2)})
            if row == "volume":
                self.app.audio.play_hover()  # a beep at the new volume

    def _level_at(self, row: str, x: float) -> None:
        self._set_level(row, (x - TRACK[0]) / (TRACK[1] - TRACK[0]))

    # --- input --------------------------------------------------------------------------------
    def handle_event(self, e: pg.event.Event) -> None:
        if e.type == pg.KEYDOWN:
            if e.key == pg.K_ESCAPE:
                self.close()
            elif e.key in (pg.K_UP, pg.K_w):
                self._choose((self.sel - 1) % len(ROWS))
            elif e.key in (pg.K_DOWN, pg.K_s):
                self._choose((self.sel + 1) % len(ROWS))
            elif e.key in (pg.K_LEFT, pg.K_a):
                self._change(ROWS[self.sel], -1)
            elif e.key in (pg.K_RIGHT, pg.K_d):
                self._change(ROWS[self.sel], 1)
            elif e.key in (pg.K_RETURN, pg.K_KP_ENTER, pg.K_SPACE):
                self.fx.press(ROWS[self.sel], self._clock)
                self._change(ROWS[self.sel], 1)
        elif e.type == pg.MOUSEMOTION:
            if self._dragging:
                self._level_at(self._dragging, e.pos[0])
            hit = self._row_at(e.pos)
            if hit is not None:
                self._choose(hit)
        elif e.type == pg.MOUSEBUTTONDOWN and e.button == 1:
            hit = self._row_at(e.pos)
            if hit is None:
                if not PANEL.collidepoint(e.pos):
                    self.close()  # a click outside the panel closes it
                return
            self.sel = hit
            self.fx.press(ROWS[hit], self._clock)
            if ROWS[hit] in BARS:
                self._dragging = ROWS[hit]
                self._level_at(ROWS[hit], e.pos[0])
            else:
                self._change(ROWS[hit], 1)
        elif e.type == pg.MOUSEBUTTONUP and e.button == 1:
            self._dragging = None

    def _row_at(self, pos) -> int | None:
        return next((i for i in range(len(ROWS)) if row_rect(i).collidepoint(pos)), None)

    def _choose(self, i: int) -> None:
        if i != self.sel:
            self.sel = i
            self.app.audio.play_hover()

    def update(self, dt: float) -> None:
        self._clock += dt
        if self._closing:
            self.k = max(0.0, self.k - dt / CLOSE_S)
            if self.k == 0.0:
                self.is_open, self._closing = False, False
        elif self.is_open:
            self.k = min(1.0, self.k + dt / OPEN_S)
        rects = {r: row_rect(i) for i, r in enumerate(ROWS)}
        self.fx.update(dt, ROWS[self.sel], rects, self._clock)

    # --- drawing -------------------------------------------------------------------------------
    def draw(self, canvas: pg.Surface, v: View) -> None:
        if not self.is_open:
            return
        e = 1 - (1 - self.k) ** 3
        dim = pg.Surface(canvas.get_size(), pg.SRCALPHA)
        dim.fill((*C.OUTLINE, round(205 * e)))
        canvas.blit(dim, (0, 0))
        pv = View(v.s, v.ox, v.oy + round((1 - e) * SLIDE_PX * v.s), v.cw, v.ch)  # sliding up
        blit_rrect(canvas, pv, PANEL.x, PANEL.y, PANEL.w, PANEL.h, 10, C.PANEL, 1.8, C.VIOLET, e)
        hud.glow_text(canvas, pv, t("settings.title"), 36, C.WHITE, C.MAGENTA,
                      (PANEL.centerx, PANEL.y + 42), face="display", strength=e)  # fmt: skip
        frame = self.fx.frame
        if frame is not None and ROWS[self.sel] != "done":
            blit_rrect(canvas, pv, *frame, 6, C.PANEL_HOT, 1.4, C.CYAN, 0.6)
        s = self.app.settings
        for i, row in enumerate(ROWS[:-1]):
            r = row_rect(i)
            lit = self.fx.lit.get(row, 0.0)
            colour = C.lerp(C.TEXT_DIM, C.WHITE, lit)
            hud.text(canvas, pv, t(f"settings.{row}"), 17, colour, (r.x + 18, r.centery - 6))
            if row == "lang":
                self._chooser(canvas, pv, r, t("lang.name"), lit)
            elif row in BARS:
                self._volume_bar(canvas, pv, r, getattr(s, row), lit)
            else:
                self._switch(canvas, pv, r, s.shake if row == "shake" else s.show_fps, lit)
        hud.live_button(canvas, pv, DONE, t("settings.done"), self.fx, "done", self._clock)
        hud.text(canvas, pv, t("settings.hint"), 13, C.TEXT_DIM, (PANEL.centerx, DONE.bottom + 16),
                 center=True)  # fmt: skip

    @staticmethod
    def _chooser(canvas, v: View, r: pg.Rect, value: str, lit: float) -> None:
        """< value >: the current choice between two small arrows."""
        cx, cy = (TRACK[0] + r.right - 14) / 2, r.centery
        hud.text(canvas, v, value, 17, C.WHITE, (cx, cy), bold=True, center=True)
        colour = C.lerp(C.PANEL_EDGE, C.CYAN, 0.4 + 0.6 * lit)
        half = 76
        _triangle(canvas, v, (cx - half, cy), -1, colour)
        _triangle(canvas, v, (cx + half, cy), 1, colour)

    @staticmethod
    def _volume_bar(canvas, v: View, r: pg.Rect, volume: float, lit: float) -> None:
        """Ten lit steps (like an arcade level meter) and the percentage."""
        steps = round(1 / VOLUME_STEP)
        on = round(volume / VOLUME_STEP)
        x0, x1, cy = TRACK[0], TRACK[1], r.centery
        w = (x1 - x0) / steps
        for i in range(steps):
            colour = C.lerp(C.CYAN, C.MAGENTA, i / (steps - 1)) if i < on else C.PANEL_EDGE
            hgt = 8 + 10 * (i + 1) / steps  # the steps grow taller, like a volume wedge
            glow = 0.5 * lit if i < on else 0.0
            x = x0 + i * w + 1.5
            blit_rrect(canvas, v, x, cy + 9 - hgt, w - 3, hgt, 1.5, colour, 0, colour, glow)
        pct = f"{round(volume * 100)}%"
        hud.text(canvas, v, pct, 15, C.WHITE, (r.right - 14, cy - 5), bold=True, align="right")

    @staticmethod
    def _switch(canvas, v: View, r: pg.Rect, on: bool, lit: float) -> None:
        """An on/off switch: a lit pill with its knob on the right when on."""
        x, cy = r.right - 14 - SWITCH_W, r.centery
        fill = C.lerp(C.PANEL_HOT, C.MAGENTA, 0.55) if on else C.BG
        edge = C.MAGENTA if on else C.lerp(C.PANEL_EDGE, C.CYAN, lit)
        blit_rrect(canvas, v, x, cy - SWITCH_H / 2, SWITCH_W, SWITCH_H, SWITCH_H / 2, fill, 1.4,
                   edge, 0.8 if on else 0.0)  # fmt: skip
        knob_x = x + (SWITCH_W - SWITCH_H / 2) if on else x + SWITCH_H / 2
        blit_dot(canvas, v, (knob_x, cy), SWITCH_H / 2 - 4, C.WHITE if on else C.TEXT_DIM,
                 0.6 if on else 0.0)  # fmt: skip
        word = t("settings.on") if on else t("settings.off")
        hud.text(canvas, v, word, 14, C.WHITE if on else C.TEXT_DIM, (x - 12, cy - 5), bold=True,
                 align="right")  # fmt: skip


def _triangle(canvas, v: View, c, direction: int, colour, size: float = 6) -> None:
    layer = Aa(canvas, v, v.rect(c[0] - size - 3, c[1] - size - 3, 2 * size + 6, 2 * size + 6), 3)
    d = direction
    pts = [(c[0] - d * size * 0.6, c[1] - size), (c[0] + d * size * 0.8, c[1]),
           (c[0] - d * size * 0.6, c[1] + size)]  # fmt: skip
    pg.draw.polygon(layer.surf, colour, [layer.pt(p) for p in pts])
    layer.done()
