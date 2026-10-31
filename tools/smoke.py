"""Smoke headless: bật App, đo ms/khung lúc bi đứng yên rồi lúc cú phá full lực.

Hợp đồng App: docs/ARCHITECTURE.md. Exit: 0 = chạy xong và trung bình mỗi giai đoạn trong
ngân sách 60 FPS; 1 = ngoại lệ hoặc vượt ngân sách; 3 = chưa có game/app.py.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("NEONPOOL_NO_MUSIC", "1")  # no background thread while measuring

ROOT = Path(__file__).resolve().parent.parent
# the default settings, never the player's own file
os.environ.setdefault("NEONPOOL_SETTINGS", str(ROOT / "tools" / "_out" / "tool-settings.json"))
sys.path.insert(0, str(ROOT))

FRAME_BUDGET_MS = 1000 / 60


def measure(app, frames: int, dt: float = 1 / 60) -> list[float]:
    times: list[float] = []
    for _ in range(frames):
        t0 = time.perf_counter()
        app.update(dt)
        app.draw()
        times.append((time.perf_counter() - t0) * 1000)
    return times


def report(name: str, times: list[float]) -> bool:
    mean = sum(times) / len(times)
    ok = mean <= FRAME_BUDGET_MS
    print(
        f"smoke {name}: {len(times)} khung, TB {mean:.2f} ms, tệ nhất {max(times):.2f} ms "
        f"(ngân sách {FRAME_BUDGET_MS:.1f} ms) {'OK' if ok else 'VƯỢT NGÂN SÁCH'}"
    )
    return ok


def net_smoke(size: tuple[int, int]) -> bool:
    """Hai game thật (hai App) gặp nhau qua ổ cắm trên 127.0.0.1 bằng chính bảng Chơi, đánh vài cú
    thật (có cú phá) rồi một ván kịch bản tới thắng/thua; báo ms/khung của từng giai đoạn."""
    import math
    import socket

    import pygame as pg

    from game.app import App
    from game.net.relay import WsTransport
    from game.physics import Shot
    from game.render import hud
    from game.rules.eight_ball import LOST, WON
    from server.local_relay import Relay

    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        os.environ["NEONPOOL_NET_PORT"] = str(probe.getsockname()[1])
    relay_server = Relay()  # the relay on this machine, as the real one would be on the internet
    os.environ["NEONPOOL_RELAY_URL"] = relay_server.url
    screen = pg.display.set_mode(size)
    host, guest = App(screen), App(screen)
    for a in (host, guest):
        a.skip_transition()
        a.menu.play_panel.prewarm(a.view)  # the real game does this once, before the first frame
        hud.prewarm_net(a.view)
    apps, times = (host, guest), {}

    def step(done, seconds, stage) -> bool:
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            for a in apps:
                t0 = time.perf_counter()
                a.update(1 / 60)
                a.draw()
                times.setdefault(stage, []).append((time.perf_counter() - t0) * 1000)
            if done():
                return True
            time.sleep(0.001)  # the sockets work in threads: give them the floor
        return False

    def on_turn():
        return host.net if host.net.session.my_turn else guest.net

    def settled():
        return all(a.net.session.settled for a in apps)

    def caught_up():
        return settled() and host.net.session.checkpoints == guest.net.session.checkpoints

    hp, gp = host.menu.play_panel, guest.menu.play_panel
    hp.open()
    hp.name = "Hoa"
    hp._start_hosting()
    ok = step(lambda: hp.room.code != "", 15, "tạo phòng")
    if hp.room.door is not None:
        hp.room.door.close()  # (one machine is one network: shut the straight way, use the relay)
    gp.open()
    gp.name, gp.code = "Nam", hp.room.code
    gp._start_joining()
    ok = ok and step(lambda: host.net is not None and guest.net is not None, 15, "phòng chờ")
    if ok and not isinstance(guest.net.session.transport, WsTransport):
        print("smoke ván hai máy: khách KHÔNG đi qua máy trung chuyển")
        ok = False
    ok = ok and step(lambda: all(a.net._toss_done() for a in apps) and settled(), 15, "tung xu")
    for turn in range(3):  # a real break, then two more shots at the nearest object ball
        if not ok:
            break
        who = on_turn()
        if who.session.can_place:
            who.session.place_cue(0.9, 0.6)
            who.session.release_cue()
            step(lambda w=who: w.session.can_shoot, 5, "đặt bi trắng")
        cue = who.world.balls[0]
        near = min((b for b in who.world.in_play() if b.number), key=lambda b: math.dist(
            (b.x, b.y), (cue.x, cue.y)))  # fmt: skip
        count = host.net.session.checkpoints + 1
        who.fire(Shot(math.atan2(near.y - cue.y, near.x - cue.x), 0.9 if turn == 0 else 0.5, 0.0))
        ok = step(lambda c=count: host.net.session.checkpoints >= c and caught_up(), 90,
                  "cú phá" if turn == 0 else "đang chạy")  # fmt: skip
    for _ in range(3):  # the 8 sunk early: whoever is on turn loses (a break would only re-rack)
        if not ok or host.net.session.match.over:
            break
        balls = host.net.world.in_play()
        aside = {b.number: (0.35 + 0.09 * i, 1.15) for i, b in enumerate(balls) if b.number}
        aside.update({8: (0.2, 0.2), 0: (0.6, 0.6)})
        host.net.session.reset_table(aside)
        step(caught_up, 10, "đặt bàn")
        who = on_turn()
        if who.session.can_place:
            who.session.release_cue()
            step(lambda w=who: w.session.can_shoot, 5, "đặt bi trắng")
        who.fire(Shot(-3 * math.pi / 4, 0.7, 0.0))
        step(lambda: host.net.session.match.over, 60, "đang chạy")
    ok = ok and step(lambda: host.net._result_shown and guest.net._result_shown, 30, "kết quả")
    if ok:
        step(lambda: False, 3.5, "thẻ kết quả đếm số")
        phases = {host.net.rules.phase, guest.net.rules.phase}
        ok = phases == {WON, LOST}
        if not ok:
            print(f"smoke hai máy: kết quả sai {phases}")
    print("smoke hai máy:", "ván chạy tới thắng/thua" if ok else "KHÔNG tới được thắng/thua")
    if ok:  # Rematch: both press it on the result card; the second game ends by a surrender
        old = (host.net, guest.net)
        for a in apps:
            a.handle_event(pg.event.Event(pg.KEYDOWN, key=pg.K_RETURN))
        both_new = lambda: (  # noqa: E731
            host.net is not old[0]
            and guest.net is not old[1]
            and host.net.session.game_no == guest.net.session.game_no == 2
        )
        ok = step(both_new, 15, "đấu lại")
        ok = ok and step(lambda: all(a.net._toss_done() for a in apps) and settled(), 15, "ván hai")
        if ok:
            guest.net.session.surrender()
            ok = step(
                lambda: host.net._result_shown and guest.net._result_shown, 15, "kết quả ván hai"
            )
        if ok:
            step(lambda: False, 1.0, "thẻ kết quả ván hai")
            wins = (host.net.session.wins, guest.net.session.wins)
            ok = (host.net.rules.phase, guest.net.rules.phase) == (WON, LOST) and (
                wins[0] == wins[1] and sum(wins[0]) == 2
            )
        print(
            "smoke hai máy:", "Đấu lại → ván hai → thắng/thua, tỉ số khớp" if ok else "ĐẤU LẠI HỎNG"
        )
    good = ok
    for stage, values in times.items():
        mean = sum(values) / len(values)
        within = mean <= FRAME_BUDGET_MS
        good = good and within
        print(
            f"smoke hai máy {stage}: {len(values)} khung (mỗi game), TB {mean:.2f} ms, tệ nhất "
            f"{max(values):.2f} ms {'OK' if within else 'VƯỢT NGÂN SÁCH'}"
        )
    for a in apps:
        a.go_menu()
    relay_server.close()
    return good


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--frames", type=int, default=300, help="frames in the break phase")
    parser.add_argument("--size", default="1280x720", help="window size of the two-player run")
    args = parser.parse_args()

    if not (ROOT / "game" / "app.py").exists():
        print("CHƯA CÓ game/app.py — không có gì để chạy smoke.")
        return 3

    import pygame as pg

    from game import config
    from game.app import App
    from game.render.layout import to_px
    from game.rules.eight_ball import LOST
    from game.scenes.help import TOPICS

    pg.init()
    screen = pg.display.set_mode(config.LOGICAL_SIZE)
    app = App(screen)
    app.go_play()  # the app opens on the menu

    idle = measure(app, 60)

    # aiming: the glow line, pull bar and ghost ball are redrawn smoothly every frame
    cx, cy = (round(v) for v in to_px(*config.HEAD_SPOT))
    app.handle_event(pg.event.Event(pg.MOUSEBUTTONDOWN, pos=(cx, cy), button=1))
    app.handle_event(
        pg.event.Event(pg.MOUSEMOTION, pos=(cx - 120, cy + 8), rel=(0, 0), buttons=(1, 0, 0))
    )
    aiming = measure(app, 60)

    # full-power break: pull MAX_DRAG_PX to the left of the (still pressed) cue ball, release
    pull = (cx - config.MAX_DRAG_PX, cy)
    app.handle_event(pg.event.Event(pg.MOUSEMOTION, pos=pull, rel=(0, 0), buttons=(1, 0, 0)))
    app.handle_event(pg.event.Event(pg.MOUSEBUTTONUP, pos=pull, button=1))
    if app.scene.rules.shots != 1:  # never report OK for a break that did not happen
        print("smoke: cú phá KHÔNG xảy ra (kéo thả không tạo cú đánh) — đo vô nghĩa")
        return 1
    breaking = measure(app, args.frames)

    # after a foul: the pulsing ring and the notice; at the end of a game: the dimmed result card
    app.play.new_game()
    app.play.rules.cue_in_hand = True
    in_hand = measure(app, 60)
    app.play.new_game()
    app.play.rules.phase = LOST
    card = measure(app, 60)
    # the how-to-play card over the menu: the first frame of each page also makes its picture
    # (ms, one-off); then the card opening out of its line and a page turning, then at rest
    app.go_menu()
    app.skip_transition()
    app.open_help()
    for page in range(len(TOPICS)):
        app.help.page = page
        t0 = time.perf_counter()
        app.update(1 / 60)
        app.draw()
        first = (time.perf_counter() - t0) * 1000
        print(f"smoke hướng dẫn trang {page + 1}: khung đầu (làm hình) {first:.0f} ms")
    app.help.k = 0.0
    opening = measure(app, 18)
    app.help.page = 2
    app.help.go(3)
    turning = measure(app, 18)
    guide = measure(app, 60)
    # the opening screen halfway through its typing, and the credits: pieces falling and floating
    # on the ribbons (their splash and weight move the water the menu draws every frame)
    app.help.is_open = False
    app.go_menu()
    app.skip_transition()
    app.start_splash()
    app.splash.t = 3.0
    splash = measure(app, 60)
    from game.scenes.loading import LoadingScene

    loading_scene = LoadingScene(screen)  # the boot log, with most of its lines there
    for key in (
        "loading.start",
        "loading.help",
        "loading.panels",
        "loading.cards",
        "loading.music",
    ):
        loading_scene.begin(key)
    loading_times = []
    for _ in range(60):
        t0 = time.perf_counter()
        loading_scene.draw(screen)
        loading_times.append((time.perf_counter() - t0) * 1000)
    app.draw()
    app.go_menu()
    app.skip_transition()
    app.menu.start_intro()  # the beam draws the menu, top to bottom
    intro = measure(app, 90)
    app.menu.mode = "menu"
    app.handle_event(pg.event.Event(pg.KEYDOWN, key=pg.K_c))
    measure(app, 90)  # the words dim away, the first pieces fall
    credits = measure(app, 120)
    net_ok = net_smoke(tuple(int(v) for v in args.size.lower().split("x")))
    pg.quit()

    ok = (
        report("đứng yên", idle)
        & report("đang ngắm", aiming)
        & report("cú phá", breaking)
        & report("bi trắng trong tay", in_hand)
        & report("bảng kết quả", card)
        & report("hướng dẫn (đang mở ra)", opening)
        & report("hướng dẫn (đang lật trang)", turning)
        & report("hướng dẫn", guide)
        & report("màn mở đầu (đang gõ công cụ, kính lồi)", splash)
        & report("màn loading (nhật ký khởi động)", loading_times)
        & report("menu được tia quét vẽ ra", intro)
        & report("credit (chữ rơi và nổi trên sóng)", credits)
        & net_ok
    )
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
