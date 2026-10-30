"""The seven pictures of the how-to-play screen: REAL game frames with marks drawn on top.

Each picture is made by posing the balls in a real `PlayScene` (the game's own table, balls, aim
line, pull bar, rings, result card and side panel), letting the game draw one frame, cropping it
and adding the marks of `render/guide_art.py`. Nothing here is redrawn by hand, so the pictures
always match the game, at any window size and in the current language.
"""

from __future__ import annotations

from types import SimpleNamespace

import pygame as pg

from game.i18n import t
from game.render import hud
from game.render import palette as C
from game.render.draw import RIM, BallSprites
from game.render.guide_art import Annot
from game.render.layout import OUTER_W, OUTER_X, PANEL_W, PANEL_X, to_px
from game.render.view import View
from game.rules.eight_ball import LOST, LOST_EARLY, WON, ShotResult
from game.scenes.play import PlayScene

ART_W, ART_H = 620, 340  # size of every picture, in logical units
CELL_W, CELL_H, CELL_GAP = 305, 165, 10  # the four small pictures of the "fouls" page
KEYS_ZOOM = 1.5  # the spin dial and key list are photographed this much bigger (rendered)

Point = tuple[float, float]


class _QuietAudio:
    """The studio scene makes no sound."""

    muted = False

    def __getattr__(self, name: str):
        return lambda *args, **kwargs: None


_STUDIOS: dict[float, PlayScene] = {}


def _studio(v: View) -> PlayScene:
    key = round(v.s, 4)
    if key not in _STUDIOS:
        if len(_STUDIOS) >= 3:
            _STUDIOS.clear()
        _STUDIOS[key] = PlayScene(SimpleNamespace(view=v, audio=_QuietAudio()))
    return _STUDIOS[key]


def _pose(
    v: View,
    balls: dict[int, Point],
    pull: Point | None = None,
    in_hand: bool = False,
) -> PlayScene:
    """Put exactly `balls` (number -> table metres) on the table. `pull` is where the pointer is
    relative to the cue ball while aiming, in logical px (the shot goes the opposite way)."""
    scene = _studio(v)
    scene.new_game()
    for b in scene.world.balls:
        b.in_play, b.vx, b.vy = False, 0.0, 0.0
    for number, (x, y) in balls.items():
        scene.world.place(number, x, y)
    scene.rules.cue_in_hand = in_hand
    scene._clock = 0.0  # a fixed pulse for the ring
    if pull is not None:
        cx, cy = to_px(scene.world.balls[0].x, scene.world.balls[0].y)
        scene.drag.begin((cx, cy))  # the shot goes away from the pull
        scene.drag.move((cx + pull[0], cy + pull[1]))
    return scene


def _photo(scene: PlayScene, v: View, crop: pg.Rect) -> pg.Surface:
    """One frame of the game, cropped to `crop` (logical units)."""
    canvas = pg.Surface(v.size)
    scene.draw(canvas)
    return canvas.subsurface(v.rect(*crop)).copy()


def _blank(v: View) -> pg.Surface:
    surf = pg.Surface(v.rect(0, 0, ART_W, ART_H).size)
    surf.fill(C.PANEL)
    return surf


def _m(x: float, y: float) -> Point:
    """Table metres -> game logical px."""
    return to_px(x, y)


# --- 1 how to take a shot ---------------------------------------------------------------
def picture_cue(v: View) -> pg.Surface:
    cue, target = (0.62, 0.64), (1.18, 0.64)
    balls = {
        0: cue,
        3: target,
        14: (0.95, 0.30),
        11: (1.58, 0.28),
        6: (1.52, 0.98),
        9: (0.40, 0.98),
    }
    scene = _pose(v, balls, pull=(-150, 0))
    crop = pg.Rect(60, 190, ART_W, ART_H)
    pic = _photo(scene, v, crop)
    a = Annot(pic, v, crop.topleft)
    cx, cy = _m(*cue)
    a.arc_arrow((cx, cy), 26, -150, -30)  # 1: go round the ball to turn the cue
    a.cursor((cx - 150, cy))
    a.step(1, (cx, cy - 46))
    a.step(2, (cx - 85, cy - 46))
    a.step(3, (cx + 115, cy - 46))
    return pic


# --- 2 goal and groups ------------------------------------------------------------------
def picture_groups(v: View) -> pg.Surface:
    balls = {
        0: (0.55, 0.62),
        3: (1.00, 0.36),
        6: (1.32, 0.88),
        1: (0.85, 0.95),
        11: (1.18, 0.62),
        13: (1.62, 0.40),
        9: (0.78, 0.28),
        12: (1.55, 0.98),
        8: (1.90, 0.66),
    }
    scene = _pose(v, balls)
    crop = pg.Rect(200, 190, ART_W, ART_H)
    pic = _photo(scene, v, crop)
    a = Annot(pic, v, crop.topleft)
    a.tag(t("group.solid"), (_m(1.00, 0.36)[0], 222), _m(1.00, 0.36))
    a.tag(t("group.stripe"), (_m(1.18, 0.62)[0] + 30, 418), _m(1.18, 0.62))
    a.tag(t("guide.eight"), (_m(1.90, 0.66)[0] - 10, 316), _m(1.90, 0.66))
    a.tag(t("guide.cue"), (_m(0.55, 0.62)[0] + 22, 418), _m(0.55, 0.62))
    return pic


# --- 3 the four fouls --------------------------------------------------------------------
def _cell(v: View, balls: dict[int, Point], pull: Point, origin: Point, number: int):
    scene = _pose(v, balls, pull=pull)
    crop = pg.Rect(*origin, CELL_W, CELL_H)
    pic = _photo(scene, v, crop)
    a = Annot(pic, v, crop.topleft)
    a.step(number, (origin[0] + 26, origin[1] + 26))
    return pic, a


def picture_fouls(v: View) -> pg.Surface:
    cells = []
    # 1 the white ball runs into the pocket in the corner
    pic, a = _cell(v, {0: (0.38, 0.26)}, (58, 40), (50, 98), 1)
    a.mark((128, 176), False)
    cells.append(pic)
    # 2 it touches nothing: the line passes between two balls
    two = {0: (1.05, 0.78), 3: (1.42, 0.60), 11: (1.42, 0.97)}
    pic, a = _cell(v, two, (-70, 0), (420, 340), 2)
    a.mark((690, 411), False)
    cells.append(pic)
    # 3 the first ball it touches is of the other group (a stripe, when your group is solids)
    pic, a = _cell(v, {0: (1.00, 0.78), 11: (1.30, 0.78), 3: (1.62, 0.78)}, (-70, 0), (420, 340), 3)
    a.mark((_m(1.30, 0.78)[0] + 18, _m(1.30, 0.78)[1] - 28), False)
    cells.append(pic)
    # 4 after the hit nothing goes in and nothing reaches a cushion: the ball just stops
    pic, a = _cell(v, {0: (1.00, 0.78), 5: (1.30, 0.78)}, (-70, 0), (420, 340), 4)
    hit = _m(1.30, 0.78)
    a.dashed((hit[0] + RIM + 34, hit[1]), (hit[0] + 100, hit[1]), 4, C.ACCENT)
    a.line((hit[0] + 112, hit[1] - 18), (hit[0] + 112, hit[1] + 18), 5, C.ERROR)
    a.mark((hit[0] + 112, hit[1] - 34), False)
    cells.append(pic)
    out = _blank(v)
    for i, pic in enumerate(cells):
        x, y = (i % 2) * (CELL_W + CELL_GAP), (i // 2) * (CELL_H + CELL_GAP)
        out.blit(pic, v.ipt((x, y)))
    return out


# --- 4 cue ball in hand ------------------------------------------------------------------
def picture_hand(v: View) -> pg.Surface:
    cue = (0.62, 0.64)
    balls = {0: cue, 5: (1.15, 0.66), 9: (1.62, 0.42), 2: (1.45, 0.98), 12: (0.45, 0.98)}
    scene = _pose(v, balls, in_hand=True)
    crop = pg.Rect(60, 250, ART_W, ART_H)
    pic = _photo(scene, v, crop)
    a = Annot(pic, v, crop.topleft)
    cx, cy = _m(*cue)
    good = _m(0.82, 0.40)
    ball = _m(1.15, 0.66)
    pocket = _m(1.27, 1.27)
    for spot in ((ball[0] + 9, ball[1] + 8), (pocket[0], pocket[1] - 22)):
        a.ring(spot, RIM + 2, C.ERROR, 3)
        a.mark((spot[0] + 17, spot[1] - 17), False, 9)
    a.ring(good, RIM + 2, C.OK, 3)
    a.mark((good[0] + 17, good[1] - 17), True, 9)
    dx, dy = good[0] - cx, good[1] - cy
    n = (dx * dx + dy * dy) ** 0.5
    a.arrow(
        (cx + dx / n * 24, cy + dy / n * 24),
        (good[0] - dx / n * 22, good[1] - dy / n * 22),
        C.WHITE,
        True,
    )
    a.cursor((cx - 2, cy - 1))
    a.step(1, (cx - 34, cy + 28))
    a.step(2, (cx + dx / 2 + 26, cy + dy / 2 - 4))
    a.step(3, (good[0] - 6, good[1] - 40))
    return pic


# --- 5 winning and losing ----------------------------------------------------------------
def _card(v: View, won: bool) -> pg.Surface:
    scene = _pose(v, {0: (0.62, 0.64), 3: (1.18, 0.64), 8: (1.58, 0.30)})
    scene.rules.phase = WON if won else LOST
    scene.rules.shots, scene.rules.fouls = 18, 2
    scene.rules.last = ShotResult(outcome=WON if won else LOST, reason=None if won else LOST_EARLY)
    return _photo(scene, v, hud.RESULT_CARD.inflate(16, 16))


def picture_end(v: View) -> pg.Surface:
    out = _blank(v)
    a = Annot(out, v)
    w = 270.0  # the cards are taller than they were: two of them still fit above the captions
    for i, (won, caption) in enumerate(((True, "guide.end_clear"), (False, "guide.end_left"))):
        card = _card(v, won)
        scale = v.i(w) / card.get_width()
        small = pg.transform.smoothscale(card, (v.i(w), round(card.get_height() * scale)))
        x = (ART_W - 2 * w - 20) / 2 + i * (w + 20)
        out.blit(small, v.ipt((x, 12)))
        a.mark((x + w - 18, 30), won)
        a.text(t(caption), (x + w / 2, 296), 15, C.TEXT, bold=True, center=True)
    return out


# --- 6 keys ----------------------------------------------------------------------------------
def picture_keys(v: View) -> pg.Surface:
    big = v.scaled(KEYS_ZOOM)  # the panel is rendered 2x bigger, so it stays sharp
    canvas = pg.Surface(big.size)
    canvas.fill(C.BG)
    hud.draw_panel(  # the game's own side panel (no table needed for this picture)
        canvas,
        big,
        shots=0,
        fouls=0,
        pocketed=set(),
        group=None,
        eight_next=False,
        muted=False,
        moving=False,
        sprites=BallSprites(big),
        spin=0.5,  # the dot sits a little high, so the picture shows what the dial is for
    )
    count = len(hud.PANEL_KEYS)
    top = hud.SPIN_C[1] - hud.SPIN_R - 28  # from the dial's name down to the last key
    crop = pg.Rect(PANEL_X + 4, top, PANEL_W - 8, hud.KEYS_Y + count * hud.KEY_STEP + 10 - top)
    pic = canvas.subsurface(big.rect(*crop)).copy()
    row = [what for _, what in hud.PANEL_KEYS].index("hud.key_help")
    a = Annot(pic, big, crop.topleft)
    y = hud.KEYS_Y + row * hud.KEY_STEP + 8
    a.arrow((PANEL_X + 176, y), (PANEL_X + 132, y), C.ACCENT)
    out = _blank(v)
    out.fill(C.BG)  # a darker backdrop, so the side panel stands out as it does in the game
    x, y0 = (out.get_width() - pic.get_width()) // 2, (out.get_height() - pic.get_height()) // 2
    out.blit(pic, (x, y0))
    return out


# --- 7 two players -----------------------------------------------------------------------
def picture_duo(v: View) -> pg.Surface:
    """The game's own name plates, clock bar, score, reaction buttons and Esc card, arranged on
    one page (nothing is drawn by hand: these are the functions the two-player game calls)."""
    out = _blank(v)
    a = Annot(out, v)
    wide = pg.Surface(v.size)
    wide.fill(C.PANEL)
    mine = pg.Rect(OUTER_X, hud.PLATE_Y, hud.PLATE_W, hud.PLATE_H)
    theirs = pg.Rect(OUTER_X + OUTER_W - hud.PLATE_W, hud.PLATE_Y, hud.PLATE_W, hud.PLATE_H)
    hud.name_plate(wide, v, mine, t("guide.duo_me"), t("group.solid"), 5, turn=True)
    hud.name_plate(wide, v, theirs, t("guide.duo_them"), t("group.stripe"), 7, turn=False)
    hud.versus(wide, v, OUTER_X + OUTER_W / 2, (2, 1))
    hud.turn_bar(wide, v, mine, 0.6, warn=False, blink_on=True)
    hud.emote_bubble(wide, v, theirs, False, t("net.emote.2"), 0.5)
    crop = pg.Rect(OUTER_X - 10, 16, OUTER_W + 20, 82)
    strip = wide.subsurface(v.rect(*crop)).copy()
    k = (ART_W - 20) / crop.w
    strip = pg.transform.smoothscale(strip, (v.i(ART_W - 20), v.i(crop.h * k)))
    out.blit(strip, v.ipt((10, 10)))
    bar = (10 + (mine.x + mine.w * 0.3 - crop.x) * k, 10 + (mine.bottom + 6 - crop.y) * k)
    a.arrow((bar[0] + 40, 92), (bar[0] + 8, bar[1] + 6), C.ACCENT)
    a.text(t("guide.duo_clock"), (bar[0] + 46, 88), 13, C.TEXT, bold=True)
    # the three reaction buttons, as the game draws them
    first = hud.emote_rects()[0]
    dx, dy = 26 - first.x, 176 - first.y
    fx = hud.ButtonFx()
    for i, rect in enumerate(hud.emote_rects()):
        hud.emote_chip(out, v, rect.move(dx, dy), t(f"net.emote.{i}"), str(i + 1), fx, i, 0.0)
    a.text(t("guide.duo_emote"), (26 + 94, 152), 14, C.TEXT, bold=True, center=True)
    # the Esc card, smaller
    card = pg.Surface(v.size)
    card.fill(C.PANEL)
    hud.draw_notice_frame(card, v, t("net.card.esc_title"), t("net.card.esc_line"), C.CYAN)
    buttons = (
        ("resume", t("net.card.resume"), True),
        ("surrender", t("net.card.surrender"), False),
    )
    hud.draw_notice_live(card, v, None, 0.0, buttons)
    pic = card.subsurface(v.rect(*hud.NOTICE_CARD.inflate(16, 16))).copy()
    width = 236
    pic = pg.transform.smoothscale(
        pic, (v.i(width), round(pic.get_height() * v.i(width) / pic.get_width()))
    )
    out.blit(pic, v.ipt((ART_W - width - 22, 122)))
    a.text(t("guide.duo_esc"), (ART_W - width / 2 - 22, 300), 14, C.TEXT, bold=True, center=True)
    return out


PICTURES = (
    picture_cue,
    picture_groups,
    picture_fouls,
    picture_hand,
    picture_end,
    picture_keys,
    picture_duo,
)


def build(index: int, v: View) -> pg.Surface:
    """Picture number `index` for this view and the current language (a surface of its own, so
    the frame offset of the window plays no part)."""
    return PICTURES[index](v.framed())
