"""Every state of the game a developer may want to look at, by name, in groups.

A state is a function of the `Harness`: it puts the game there and returns (a script it starts may
go on for a few seconds). They are written to be run from ANY other state, one after another.
To add one, write a function and register it with `@state(group, name)`; `tools/dev.py --check`
(and tests/test_dev_tool.py) run every state and fail if one raises.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import pygame as pg

from game import config
from game.net import relay
from game.scenes import play_panel as pp
from tools.devkit.harness import LATENCIES, SPEEDS, Harness

STATES: list[State] = []
SIZES = ((1280, 720), (1050, 590), (1920, 1080), (2560, 1440))


@dataclass(frozen=True)
class State:
    group: str
    name: str
    run: Callable[[Harness], None]


def state(group: str, name: str):
    def register(fn: Callable[[Harness], None]):
        STATES.append(State(group, name, fn))
        return fn

    return register


def by_name(name: str) -> State | None:
    name = name.strip().lower()
    return next((s for s in STATES if s.name.lower() == name), None) or next(
        (s for s in STATES if name in s.name.lower()), None
    )


# ---------------------------------------------------------------------------- menu and panels
MENU = "Menu và bảng"


@state(MENU, "Menu")
def _menu(h: Harness) -> None:
    h.reset()


class _ShownRoom:
    """A room as the panel sees it, without a relay: a code, nobody coming."""

    def __init__(self, code: str) -> None:
        self.code, self.error = code, None
        self.state = relay.READY if code else relay.CONNECTING

    def accept(self):
        return None

    def close(self) -> None:
        pass


def _panel(h: Harness, step: str, *, name: str = "", code: str = "", error: str | None = None,
           room: str = "KXQM"):  # fmt: skip
    h.reset()
    panel = h.app.menu.play_panel
    panel.open()
    panel.name = name
    if step != pp.CHOOSE:
        panel._goto(step)
    panel.code = code
    panel.error = error
    if step == pp.HOSTING:
        panel.room = _ShownRoom(room)
    panel.k = 1.0


@state(MENU, "Bảng Chơi: chọn Chơi đơn / Chơi đôi")
def _play_choose(h: Harness) -> None:
    _panel(h, pp.CHOOSE)


@state(MENU, "Bảng Chơi: nhập tên (trống)")
def _play_setup_empty(h: Harness) -> None:
    _panel(h, pp.SETUP)


@state(MENU, "Bảng Chơi: nhập tên (không có internet)")
def _play_setup_error(h: Harness) -> None:
    _panel(h, pp.SETUP, name="Dev", error="net.err.offline")


@state(MENU, "Bảng Chơi: đang tạo phòng")
def _play_making(h: Harness) -> None:
    _panel(h, pp.HOSTING, name="Dev", room="")


@state(MENU, "Bảng Chơi: chờ bạn vào (mã giả)")
def _play_hosting(h: Harness) -> None:
    _panel(h, pp.HOSTING, name="Dev")


@state(MENU, "Bảng Chơi: nhập mã (đang gõ)")
def _play_joining(h: Harness) -> None:
    _panel(h, pp.JOINING, name="Dev", code="KX")


@state(MENU, "Bảng Chơi: mã lỗi (không có phòng)")
def _play_joining_error(h: Harness) -> None:
    _panel(h, pp.JOINING, name="Dev", code="KXQM", error="net.err.no_room")


@state(MENU, "Bảng Chơi: hai bản game khác nhau")
def _play_version_error(h: Harness) -> None:
    _panel(h, pp.JOINING, name="Dev", code="KXQM", error="net.err.version")


@state(MENU, "Bảng Chơi: đang kết nối")
def _play_connecting(h: Harness) -> None:
    _panel(h, pp.CONNECTING, name="Dev", code="KXQM")


@state(MENU, "Cài đặt")
def _settings(h: Harness) -> None:
    h.reset()
    h.app.menu.settings.open()
    h.app.menu.settings.k = 1.0


for _page in range(7):

    @state("Hướng dẫn", f"Hướng dẫn trang {_page + 1}")
    def _help(h: Harness, page: int = _page) -> None:
        h.reset()
        h.app.open_help()
        h.app.help.page = page
        h.app.help.k = 1.0


# ---------------------------------------------------------------------------- solo
SOLO = "Chơi đơn"


@state(SOLO, "Ván mới")
def _solo_new(h: Harness) -> None:
    h.reset()
    h.app.go_play()
    h.app.skip_transition()


@state(SOLO, "Cú phá đang chạy")
def _solo_break(h: Harness) -> None:
    from game.physics import Shot

    _solo_new(h)
    h.app.play.fire(Shot(0.0, 0.95, 0.0))


@state(SOLO, "Lỗi: bi trắng trong tay")
def _solo_foul(h: Harness) -> None:
    h.solo_foul()


@state(SOLO, "Thẻ THẮNG (đếm số)")
def _solo_win(h: Harness) -> None:
    h.solo_finish(True)


@state(SOLO, "Thẻ THUA (đếm số)")
def _solo_lose(h: Harness) -> None:
    h.solo_finish(False)


@state(MENU, "Bảng Chơi: chọn Tự do / Luyện tập")
def _play_mode(h: Harness) -> None:
    _panel(h, pp.MODE)


@state(MENU, "Bảng Chơi: chọn Luyện tập (Đấu Ma / Gọi Lỗ / Nước Rút)")
def _play_practice(h: Harness) -> None:
    _panel(h, pp.PRACTICE)


# ---------------------------------------------------------------------------- solo: practice
# One group of states per run. The first (Beat the Ghost) keeps its old names.
PRACTICE = "Luyện tập: Đấu Ma"
PRACTICE_CALL = "Luyện tập: Gọi Lỗ"
PRACTICE_SPRINT = "Luyện tập: Nước Rút"


@state(PRACTICE, "Luyện tập: ván mới (đang đếm ngược 7 s)")
def _practice_new(h: Harness) -> None:
    h.practice_new()


@state(PRACTICE, "Luyện tập: hết đếm ngược, tới lượt đánh")
def _practice_ready(h: Harness) -> None:
    h.practice_ready()


@state(PRACTICE, "Luyện tập: cú phá đang chạy")
def _practice_break(h: Harness) -> None:
    h.practice_break()


@state(PRACTICE, "Giữa chuỗi (đã qua 5 bi)")
def _practice_streak(h: Harness) -> None:
    h.practice_streak(5)


@state(PRACTICE, "Thua (hết mạng)")
def _practice_lost(h: Harness) -> None:
    h.practice_lost()


@state(PRACTICE, "Thắng (chạy hết 15 bi, đếm số)")
def _practice_won(h: Harness) -> None:
    h.practice_won()


def _mode_states(group: str, mode: str, name: str, lost: str) -> None:
    """The same six states for Call the Pocket and Sprint (`lost`: how a run of that kind ends)."""

    @state(group, f"{name}: ván mới (đang đếm ngược 7 s)")
    def _new(h: Harness) -> None:
        h.practice_new(mode)

    @state(group, f"{name}: hết đếm ngược, tới lượt đánh")
    def _ready(h: Harness) -> None:
        h.practice_ready(mode)

    @state(group, f"{name}: cú phá đang chạy")
    def _break(h: Harness) -> None:
        h.practice_break(mode)

    @state(group, f"{name}: giữa chuỗi (đã qua 5 bi)")
    def _streak(h: Harness) -> None:
        h.practice_streak(5, mode)

    @state(group, f"{name}: thua ({lost})")
    def _lost(h: Harness) -> None:
        h.practice_lost(mode)

    @state(group, f"{name}: thắng (chạy hết 15 bi, đếm số)")
    def _won(h: Harness) -> None:
        h.practice_won(mode)


_mode_states(PRACTICE_CALL, "call", "Gọi Lỗ", "hết mạng")
_mode_states(PRACTICE_SPRINT, "sprint", "Nước Rút", "hết giờ")


# ---------------------------------------------------------------------------- two players: start
NET = "Chơi đôi: vào ván"


@state(NET, "Tôi là chủ phòng, tôi phá")
def _net_host_me(h: Harness) -> None:
    h.start_net(me_host=True, breaker="me")


@state(NET, "Tôi là chủ phòng, bot phá")
def _net_host_bot(h: Harness) -> None:
    h.start_net(me_host=True, breaker="bot")


@state(NET, "Tôi là khách, tôi phá")
def _net_guest_me(h: Harness) -> None:
    h.start_net(me_host=False, breaker="me")


@state(NET, "Tôi là khách, bot phá")
def _net_guest_bot(h: Harness) -> None:
    h.start_net(me_host=False, breaker="bot")


@state(NET, "Sau tung xu, tới lượt tôi")
def _net_my_turn(h: Harness) -> None:
    h.start_net(breaker="me")
    h.skip_toss()


@state(NET, "Xem lại đoạn mở ván (tung xu) từ đầu")
def _net_replay_toss(h: Harness) -> None:
    h.replay_toss()


@state(NET, "Độ trễ giả: đổi vòng 0 / 60 / 200 ms")
def _net_latency(h: Harness) -> None:
    h.set_latency(LATENCIES[(LATENCIES.index(h.latency) + 1) % len(LATENCIES)])


# ---------------------------------------------------------------------------- two players: bot
BOT = "Chơi đôi: đối thủ giả"


@state(BOT, "Bot tự chơi: bật / tắt")
def _bot_auto(h: Harness) -> None:
    h.ensure_net()
    h.bot.auto = not h.bot.auto


@state(BOT, "Bot đánh một cú ngay")
def _bot_once(h: Harness) -> None:
    h.ensure_net()
    h.bot.play_once()


@state(BOT, "Bot biểu cảm: Hay!")
def _bot_emote0(h: Harness) -> None:
    _emote(h, 0)


@state(BOT, "Bot biểu cảm: Tiếc quá")
def _bot_emote1(h: Harness) -> None:
    _emote(h, 1)


@state(BOT, "Bot biểu cảm: GG")
def _bot_emote2(h: Harness) -> None:
    _emote(h, 2)


def _emote(h: Harness, code: int) -> None:
    h.ensure_net()
    h.skip_toss()
    h.fake._emote_at = -config.NET_EMOTE_GAP_S  # (the tool is not rationed)
    h.fake.send_emote(code)


@state(BOT, "Cho tôi tới lượt (đối thủ hết giờ)")
def _turn_me(h: Harness) -> None:
    h.ensure_net()
    h.skip_toss()
    h.run_script(h.give_turn_to("me"))


@state(BOT, "Cho bot tới lượt (tôi hết giờ)")
def _turn_bot(h: Harness) -> None:
    h.ensure_net()
    h.skip_toss()
    h.run_script(h.give_turn_to("bot"))


@state(BOT, "Bot đang chỉnh xoáy (giữ nguyên)")
def _bot_dial(h: Harness) -> None:
    h.ensure_net()
    h.skip_toss()
    h.bot.dial = True
    h.run_script(h.give_turn_to("bot"))


@state(BOT, "Bot thôi chỉnh xoáy")
def _bot_undial(h: Harness) -> None:
    h.bot.dial = False


@state(BOT, "Tỉ số phòng 2 : 1 (từ ván thứ ba)")
def _score(h: Harness) -> None:
    h.ensure_net()
    h.set_wins(2, 1)


# ---------------------------------------------------------------------------- two players: clock
CLOCK = "Chơi đôi: đồng hồ và tiếng"


def _clock(h: Harness, seconds: float, who: str = "me") -> None:
    h.ensure_net()
    h.run_script(_clock_script(h, seconds, who))


def _clock_script(h: Harness, seconds: float, who: str):
    yield from h.give_turn_to(who)
    h.set_clock(seconds)


@state(CLOCK, "Đồng hồ của tôi còn 12 giây (sắp tích)")
def _clock12(h: Harness) -> None:
    _clock(h, 12.0)


@state(CLOCK, "Đồng hồ của tôi còn 5 giây (tích nhanh)")
def _clock5(h: Harness) -> None:
    _clock(h, 5.0)


@state(CLOCK, "Đồng hồ của tôi còn 1 giây (hết giờ ngay)")
def _clock1(h: Harness) -> None:
    _clock(h, 1.0)


@state(CLOCK, "Đồng hồ của bot còn 12 giây (tôi không nghe tích)")
def _clock_bot(h: Harness) -> None:
    _clock(h, 12.0, "bot")


# ---------------------------------------------------------------------------- two players: rules
RULES = "Chơi đôi: lỗi và kết quả"


def _fresh(h: Harness) -> None:
    """A new game (same side as before): these states need a game at a known point."""
    h.start_net(me_host=h.me_host)


@state(RULES, "Tôi phạm lỗi (bot được đặt bi trắng)")
def _foul_me(h: Harness) -> None:
    _fresh(h)
    h.skip_toss()
    h.run_script(h.script_foul("me"))


@state(RULES, "Bot phạm lỗi (tôi được đặt bi trắng)")
def _foul_bot(h: Harness) -> None:
    _fresh(h)
    h.skip_toss()
    h.run_script(h.script_foul("bot"))


@state(RULES, "Tôi THẮNG: bot bỏ bi 8 sớm")
def _win_8(h: Harness) -> None:
    _fresh(h)
    h.skip_toss()
    h.run_script(h.script_eight_early("bot"))


@state(RULES, "Tôi THUA: tôi bỏ bi 8 sớm")
def _lose_8(h: Harness) -> None:
    _fresh(h)
    h.skip_toss()
    h.run_script(h.script_eight_early("me"))


@state(RULES, "Tôi THẮNG: bot đầu hàng")
def _win_surrender(h: Harness) -> None:
    _fresh(h)
    h.fake.surrender()


@state(RULES, "Tôi THUA: tôi đầu hàng")
def _lose_surrender(h: Harness) -> None:
    _fresh(h)
    h.mine.surrender()


@state(RULES, "Tôi THẮNG rồi bot rời phòng (Đấu lại tắt)")
def _win_then_left(h: Harness) -> None:
    _fresh(h)
    h.fake.surrender()
    h.run_script(_then(h, lambda: h.mine.match.over, lambda: h.fake.leave()))


@state(RULES, "Thẻ kết quả: bot đã bấm Đấu lại trước")
def _bot_rematch_first(h: Harness) -> None:
    _fresh(h)
    h.mine.surrender()
    h.run_script(_then(h, lambda: h.fake.match.over, lambda: h.fake.ask_rematch()))


@state(RULES, "Thẻ kết quả: tôi đã bấm Đấu lại, đang chờ")
def _me_rematch_first(h: Harness) -> None:
    _fresh(h)
    h.mine.surrender()
    h.run_script(_then(h, lambda: h.mine.match.over, lambda: h.mine.ask_rematch()))


@state(RULES, "Đấu lại: cả hai đã bấm (ván mới, tỉ số cộng dồn)")
def _rematch_both(h: Harness) -> None:
    _fresh(h)
    h.mine.surrender()
    h.run_script(
        _then(h, lambda: h.mine.match.over, lambda: (h.mine.ask_rematch(), h.fake.ask_rematch()))
    )


def _then(h: Harness, cond, action):
    yield from h.wait(cond)
    action()


# ---------------------------------------------------------------------------- two players: link
LINK = "Chơi đôi: mạng và thẻ"


@state(LINK, "Cắt mạng (thẻ Mất kết nối sau 1 giây)")
def _cut(h: Harness) -> None:
    h.ensure_net()
    h.room.cut()


@state(LINK, "Nối mạng lại (bàn dán lại, chơi tiếp)")
def _reconnect(h: Harness) -> None:
    h.ensure_net()
    h.room.reconnect()


@state(LINK, "Mạng câm: không gói nào qua, ~8 giây tự rớt")
def _mute(h: Harness) -> None:
    h.ensure_net()
    h.room.mute()


@state(LINK, "Rớt mạng còn 3 giây tới hết hạn")
def _drop_3(h: Harness) -> None:
    _fresh(h)
    h.run_script(h.script_dropped_for_good(3.0))


@state(LINK, "Thẻ Esc: Ván đang chạy")
def _card_esc(h: Harness) -> None:
    h.ensure_net()
    h.skip_toss()
    h.app.net._open_card("esc")


@state(LINK, "Thẻ Đầu hàng? (hỏi lại)")
def _card_sure(h: Harness) -> None:
    h.ensure_net()
    h.skip_toss()
    h.app.net._open_card("sure")


# ---------------------------------------------------------------------------- display
VIEW = "Hiển thị"


@state(VIEW, "Ngôn ngữ: đổi vi / en")
def _lang(h: Harness) -> None:
    h.app.change_settings(lang="en" if h.app.settings.lang == "vi" else "vi")


for _size in SIZES:

    @state(VIEW, f"Cỡ cửa sổ {_size[0]}×{_size[1]}")
    def _size_state(h: Harness, size: tuple[int, int] = _size) -> None:
        pg.display.set_mode(size, pg.RESIZABLE)
        h.app.sync_view(force=True)


@state(VIEW, "Tốc độ: đổi vòng ×0,25 / ×1 / ×4")
def _speed(h: Harness) -> None:
    h.speed = SPEEDS[(SPEEDS.index(h.speed) + 1) % len(SPEEDS)]


@state(VIEW, "Hiện / ẩn đồng hồ FPS")
def _fps(h: Harness) -> None:
    h.app.change_settings(show_fps=not h.app.settings.show_fps)
