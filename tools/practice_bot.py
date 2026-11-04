"""Người chơi giả cho Luyện tập (Đấu Ma / Gọi Lỗ / Nước Rút): ước lượng THÔ độ cân bằng.

Không pygame, không cửa sổ. Bot ngắm kiểu bi ma: góc tới điểm sau bi mục tiêu một đường kính trên
đường tới lỗ, lực vừa đủ (tăng theo quãng đường), xoáy 0, cộng nhiễu góc Gauss sigma (độ). Ván chạy
bằng World + rules thật (cú phá, tới khi bi đứng yên thì `finish_shot`, cầm tay thì bot tự đặt bi
cái). Kết quả CHỈ là ước lượng bằng bot (không xoáy, không đánh băng, không đánh phối hợp), KHÔNG
phải cảm giác người chơi. Xác định theo hạt giống: nhiễu dùng random.Random của bot, phần của game
dùng World.rng.

Bot "hiệu chỉnh" (calibrate) chỉ để tách nguyên nhân ở sigma 0: nó thử cú đánh trên bản sao của bàn
và chỉnh góc cho tới khi bi mục tiêu đi đúng đường tới lỗ, tức là bù cả độ lệch do vật lý (xem
báo cáo). Người chơi thật không làm được, nên bảng chính dùng bot thường.

Mức độ (--level easy|hard, mặc định hard): bot đánh theo đúng tập đường mà luật của mức đó đã
dùng để chọn bi (`rules._ask_easy`), nên mức Dễ được đo bằng cách bot ngắm các đường Dễ.

Chạy: .venv/bin/python tools/practice_bot.py [--runs N] [--seed S] [--min-shots M] [--jobs J]
      [--level easy|hard]
"""

from __future__ import annotations

import argparse
import math
import os
import random
import sys
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from game.config import (  # noqa: E402
    BALL_R,
    CALL_MAX_CUT_DEG,
    EASY_MAX_CUT_DEG,
    EASY_MAX_POT_DIST_M,
    FOOT_SPOT,
    HEAD_SPOT,
    POCKETS,
    PRACTICE_LINE_MARGIN_M,
    PRACTICE_MAX_CUT_DEG,
    SPRINT_CAP_S,
    SPRINT_MISS_COST_S,
    SPRINT_POT_BONUS_S,
    SPRINT_SCRATCH_COST_S,
    SPRINT_START_S,
    TABLE_L,
    TABLE_W,
)
from game.physics.pot_lines import pot_pockets  # noqa: E402
from game.physics.shot import Shot  # noqa: E402
from game.physics.world import CUE, World  # noqa: E402
from game.rules.eight_ball import LOST, PLAYING, WON  # noqa: E402
from game.rules.practice import GhostRun, make_run  # noqa: E402

SIGMAS = (0.0, 0.3, 0.6, 1.0, 1.5)  # degrees of aiming noise
SPRINT_SIGMAS = (0.6, 1.0)
SPRINT_T_AIMS = (4.0, 7.0, 10.0)  # assumed seconds of aiming before each shot (balls rolling: free)
FEASIBLE_RATE = 0.85  # sigma 0 below this: list the failures
CUT_BINS = ((0.0, 15.0), (15.0, 30.0), (30.0, 45.0), (45.0, 60.1), (60.1, 90.0))

MAX_SHOT_STEPS = 240 * 90  # a shot that has not stopped after 90 s of table time is cut off
MAX_SHOTS_PER_RUN = 120  # safety: no run goes on for ever

# --- how the bot hits: all self-chosen, it is a stand-in for a player, not a design number -------
ARRIVE_SPEED = 0.6  # m/s the target should still have on reaching the pocket
POWER_MIN, POWER_MAX = 0.12, 0.85
COS_MIN = 0.3  # a cut thinner than ~72 degrees is not made any "harder" than this
BACK_TRIES = (0.35, 0.5, 0.7, 0.25, 1.0, 0.15, 1.3)  # distances behind the ghost spot to place at
BREAK_POWER = (0.75, 1.0)
BREAK_SIGMA_DEG = 1.0  # the break is never the same twice (the rack is symmetric)
PROBE_STEPS = 240 * 8  # a trial shot is watched this long for the target to move
PROBE_MAX_DEG = 25.0  # a target that leaves further than this from its line was not hit as planned
CAL_TRIES = 12  # trial shots the calibrating bot may spend on one aim
CAL_TOL_DEG = 0.15  # ... it stops once the target leaves this close to its line
CAL_PROBE_DEG = 0.05  # first nudge of the aim, to learn how the target's direction answers


@dataclass
class ShotRec:
    ball: int
    pocket: int | None  # the pocket the bot aimed at
    cut_deg: float  # angle between the cue ball's path and the line the target must take
    reach_m: float  # target to pocket
    run_m: float  # cue ball to the ghost spot
    power: float = 0.0
    lined: bool = True  # the rules named a pocket with a line (else: no line anywhere, a try)
    engine_deg: float | None = (
        None  # sigma 0 only: how far the engine sends the target off its line
    )
    potted: bool = False  # the target went down (any pocket, even with the cue ball)
    right: bool = False  # counted (res.hit): down, in the called pocket, no scratch
    scratch: bool = False
    why: str = ""  # for a failure: what happened


@dataclass
class RunStats:
    mode: str
    shots: list[ShotRec] = field(default_factory=list)
    score: int = 0  # balls potted as targets (rules.streak)
    won: bool = False
    timed_out: bool = False  # Sprint: the clock ran out
    breaks: int = 0


# --- aiming -----------------------------------------------------------------------------------
def _aim_point(index: int) -> tuple[float, float]:
    px, py, _r = POCKETS[index]
    return min(max(px, BALL_R), TABLE_L - BALL_R), min(max(py, BALL_R), TABLE_W - BALL_R)


def _line(ball, index: int) -> tuple[float, float, float, tuple[float, float]]:
    """(unit dx, dy, distance to the aim point, ghost spot) for the target going to pocket."""
    ax, ay = _aim_point(index)
    vx, vy = ax - ball.x, ay - ball.y
    dist = math.hypot(vx, vy)
    dx, dy = (vx / dist, vy / dist) if dist else (1.0, 0.0)
    return dx, dy, dist, (ball.x - 2 * BALL_R * dx, ball.y - 2 * BALL_R * dy)


def _cut_deg(cue, ghost, dx: float, dy: float) -> float:
    ux, uy = ghost[0] - cue.x, ghost[1] - cue.y
    run = math.hypot(ux, uy)
    if run == 0.0:
        return 0.0
    return math.degrees(math.acos(max(-1.0, min(1.0, (ux * dx + uy * dy) / run))))


def limits(mode: str, easy: bool) -> tuple[float, float | None]:
    """(thinnest cut in degrees, furthest target-to-pocket in metres or None) of the lines."""
    hard = CALL_MAX_CUT_DEG if mode == "call" else PRACTICE_MAX_CUT_DEG
    return (min(EASY_MAX_CUT_DEG, hard), EASY_MAX_POT_DIST_M) if easy else (hard, None)


def _lines(
    world: World, target: int, in_hand: bool, max_cut: float, max_dist: float | None = None
) -> list[int]:
    for margin in (PRACTICE_LINE_MARGIN_M, 0.0):
        got = pot_pockets(
            world.balls,
            target,
            cue_in_hand=in_hand,
            max_cut_deg=max_cut,
            margin=margin,
            max_pot_dist=max_dist,
        )
        if got:
            return got
    return []


def place_cue(
    world: World,
    target: int,
    pockets: list[int],
    max_cut: float,
    max_dist: float | None = None,
) -> None:
    """Cue ball in hand: put it behind the target for the best pocket on offer (the nearest one):
    straight behind if that is free with a clear path, else a little to the side (never a cut
    thinner than `max_cut` less a margin). None fits: it stays where it is."""
    ball = world.balls[target]
    cue = world.balls[CUE]
    best: tuple[float, float, float] | None = None
    turns = [0.0]
    for k in range(1, int((max_cut - 10.0) // 10.0) + 1):
        turns += [10.0 * k, -10.0 * k]
    for index in pockets:
        dx, dy, dist, ghost = _line(ball, index)
        found = None
        for turn in turns:
            c, s = math.cos(math.radians(turn)), math.sin(math.radians(turn))
            ux, uy = dx * c - dy * s, dx * s + dy * c
            for back in BACK_TRIES:
                x, y = ghost[0] - back * ux, ghost[1] - back * uy
                if not world.can_place_cue(x, y):
                    continue
                old = (cue.x, cue.y)
                world.place(CUE, x, y)
                ok = index in pot_pockets(
                    world.balls, target, max_cut_deg=max_cut, margin=0.0, max_pot_dist=max_dist
                )
                world.place(CUE, *old)
                if ok:
                    found = (dist, x, y)
                    break
            if found:
                break
        if found and (best is None or found[0] < best[0]):
            best = found
    if best is not None:
        world.place(CUE, best[1], best[2])


def _power(world: World, run_m: float, reach_m: float, cut_deg: float) -> float:
    """Just enough to roll the target into the pocket with ARRIVE_SPEED to spare."""
    a = world.feel.roll_decel
    v_target = math.sqrt(ARRIVE_SPEED**2 + 2 * a * reach_m)
    cos_cut = max(COS_MIN, math.cos(math.radians(cut_deg)))
    v_contact = v_target / (0.5 * (1 + world.feel.ball_e) * cos_cut)
    v0 = math.sqrt(v_contact**2 + 2 * a * run_m)
    return min(POWER_MAX, max(POWER_MIN, v0 / world.feel.v_max))


def choose_pocket(world: World, rules: GhostRun, mode: str) -> tuple[int | None, bool]:
    """(pocket, has a line). Call the Pocket: the pocket named. Beat the Ghost: the nearest one
    with a line. No line anywhere (the rules then name no pocket): the nearest pocket whose ghost
    spot is on the cloth, a try is a try."""
    target = world.balls[rules.target]
    called = getattr(rules, "pocket", None)
    if mode == "call" and called is not None:
        return called, True
    cut, dist_max = limits("ghost", rules._ask_easy)
    got = pot_pockets(world.balls, rules.target, max_cut_deg=cut, margin=0.0, max_pot_dist=dist_max)
    best = None
    for index in got or range(len(POCKETS)):
        _dx, _dy, dist, ghost = _line(target, index)
        on_cloth = BALL_R <= ghost[0] <= TABLE_L - BALL_R and BALL_R <= ghost[1] <= TABLE_W - BALL_R
        if on_cloth and (best is None or dist < best[0]):
            best = (dist, index)
    return (best[1] if best else None), bool(got) and mode == "ghost"


def _clone(world: World) -> World:
    """A copy of the table to try a shot on (balls only: the trial never needs the rng)."""
    sim = World(0, world.feel, rack=False, spin=world.spin)
    for a, b in zip(sim.balls, world.balls, strict=True):
        a.x, a.y, a.vx, a.vy, a.qx, a.qy = b.x, b.y, b.vx, b.vy, b.qx, b.qy
        a.in_play, a.pocket = b.in_play, b.pocket
    return sim


def probe(world: World, shot: Shot, target: int, want: float) -> float | None:
    """Try `shot` on a copy: how far (radians, signed) the target leaves from the direction `want`
    the moment it first moves. None if it does not move (or leaves far off: not hit as planned)."""
    sim = _clone(world)
    sim.apply(shot)
    ball = sim.balls[target]
    for _ in range(PROBE_STEPS):
        sim.step()
        if ball.vx or ball.vy:
            err = (math.atan2(ball.vy, ball.vx) - want + math.pi) % (2 * math.pi) - math.pi
            return err if abs(err) < math.radians(PROBE_MAX_DEG) else None
        if sim.at_rest():
            return None
    return None


def calibrate(world: World, target: int, want: float, angle: float, power: float) -> float:
    """The aim (radians) at which the target leaves closest to `want`. The target's direction
    answers an aim change about 20 to 80 times over, and the engine's contact error is a sawtooth
    on top: so one nudge finds the slope, then the root is bracketed and narrowed (secant and
    halving in turn); the best tried is kept."""
    tried: dict[float, float] = {}

    def trial(aim: float) -> float | None:
        err = probe(world, Shot(aim, power, 0.0), target, want)
        if err is not None:
            tried[aim] = err
        return err

    def best() -> float:
        return min(tried, key=lambda a: abs(tried[a])) if tried else angle

    e0 = trial(angle)
    if e0 is None or abs(e0) <= math.radians(CAL_TOL_DEG):
        return angle
    h = math.radians(CAL_PROBE_DEG)
    e1 = trial(angle + h)
    if e1 is None or e1 == e0:
        return best()
    aim = angle - e0 * h / (e1 - e0)  # Newton from the slope just found
    for k in range(CAL_TRIES):
        err = trial(aim)
        if err is not None and abs(err) <= math.radians(CAL_TOL_DEG):
            break
        pts = sorted(tried.items())
        brackets = [(a, b) for a, b in zip(pts, pts[1:], strict=False) if a[1] * b[1] < 0]
        if not brackets:  # no side change yet: step on from the best by the slope
            a_best = best()
            aim = a_best - tried[a_best] * h / (e1 - e0)
            if aim in tried:
                aim += h * (1 if k % 2 else -1)
            continue
        (a, ea), (b, eb) = min(brackets, key=lambda p: min(abs(p[0][1]), abs(p[1][1])))
        aim = a - ea * (b - a) / (eb - ea) if k % 2 == 0 else (a + b) / 2
        if aim in tried:
            aim = (a + b) / 2
    return best()


def plan_shot(
    world: World,
    rules: GhostRun,
    mode: str,
    rng: random.Random,
    sigma: float,
    *,
    calibrated: bool = False,
) -> tuple[Shot, ShotRec]:
    """The bot's shot at the current target (the cue ball is already where it will shoot from)."""
    cue = world.balls[CUE]
    target = world.balls[rules.target]
    index, lined = choose_pocket(world, rules, mode)
    noise = math.radians(rng.gauss(0.0, sigma)) if sigma else 0.0
    if index is None:
        angle = math.atan2(target.y - cue.y, target.x - cue.x)
        rec = ShotRec(rules.target, None, 0.0, 0.0, math.hypot(target.x - cue.x, target.y - cue.y))
        rec.lined = False
        return Shot(angle + noise, 0.4, 0.0), rec
    dx, dy, reach, ghost = _line(target, index)
    angle = math.atan2(ghost[1] - cue.y, ghost[0] - cue.x)
    run = math.hypot(ghost[0] - cue.x, ghost[1] - cue.y)
    cut = _cut_deg(cue, ghost, dx, dy)
    power = _power(world, run, reach, cut)
    rec = ShotRec(rules.target, index, cut, reach, run, power)
    rec.lined = lined
    want = math.atan2(dy, dx)
    if calibrated:
        angle = calibrate(world, rules.target, want, angle, power)
    if sigma == 0.0:  # (only there is the engine's own error told apart from the noise)
        err = probe(world, Shot(angle, power, 0.0), rules.target, want)
        rec.engine_deg = None if err is None else math.degrees(err)
    return Shot(angle + noise, power, 0.0), rec


def break_shot(rng: random.Random) -> Shot:
    angle = math.atan2(FOOT_SPOT[1] - HEAD_SPOT[1], FOOT_SPOT[0] - HEAD_SPOT[0])
    angle += math.radians(rng.gauss(0.0, BREAK_SIGMA_DEG))
    return Shot(angle, rng.uniform(*BREAK_POWER), 0.0)


# --- one shot and one run ---------------------------------------------------------------------
def play_out(world: World, rules: GhostRun) -> None:
    """Run the world to rest and feed the rules; a cue ball that went down is put back."""
    for _ in range(MAX_SHOT_STEPS):
        rules.on_events(world.step())
        if world.at_rest():
            break
    if not world.balls[CUE].in_play:
        world.respawn_cue()
    for b in world.balls:  # (a ball still rolling at the cut-off is judged where it stands)
        b.vx = b.vy = b.qx = b.qy = 0.0


def play_run(
    mode: str,
    sigma: float,
    seed: int,
    *,
    t_aim: float | None = None,
    calibrated: bool = False,
    max_shots: int = MAX_SHOTS_PER_RUN,
    level: str = "hard",
) -> RunStats:
    """One whole run of `mode` at `level` by the bot. `t_aim` (Sprint only): seconds the clock
    loses before every shot (the break included); the balls rolling cost nothing."""
    world = World(seed=seed)
    rules = make_run(mode, world.rng, level)
    rng = random.Random(seed * 7919 + 17)  # the bot's own stream: noise and the break
    stats = RunStats(mode)
    while rules.phase == PLAYING and rules.shots < max_shots:
        if t_aim is not None and rules.tick(t_aim):  # type: ignore[attr-defined]
            stats.timed_out = True
            break
        rec = None
        if rules.target is None:  # the break: nothing is called
            shot = break_shot(rng)
            stats.breaks += 1
        else:
            if rules.cue_in_hand:
                called = getattr(rules, "pocket", None) if mode == "call" else None
                max_cut, max_dist = limits(mode, rules._ask_easy)  # (as the rules chose the ball)
                pockets = (
                    [called]
                    if called is not None
                    else _lines(world, rules.target, True, max_cut, max_dist)
                )
                place_cue(world, rules.target, pockets, max_cut, max_dist)
                rules.cue_placed()
            shot, rec = plan_shot(world, rules, mode, rng, sigma, calibrated=calibrated)
        world.apply(shot)
        rules.on_shot()
        play_out(world, rules)
        fell_in = dict(rules._pocket_of)
        scratched = rules._cue_down
        res = rules.finish_shot(world.balls)
        if rec is not None:
            rec.potted = rec.ball in res.pocketed
            rec.right = res.hit
            rec.scratch = scratched
            if not rec.right:
                rec.why = _why(rec, fell_in)
            stats.shots.append(rec)
        if res.outcome == LOST and t_aim is not None:
            stats.timed_out = True
    stats.score = rules.streak
    stats.won = rules.phase == WON
    return stats


def _why(rec: ShotRec, fell_in: dict[int, int]) -> str:
    if rec.scratch:
        return "bi cái xuống lỗ"
    if rec.potted:
        return "vào lỗ khác"
    del fell_in
    return "không vào"


# --- cells and the report ---------------------------------------------------------------------
Cell = tuple  # (mode, sigma, t_aim or None, calibrated, level)


def run_cell(args: tuple) -> list[RunStats]:
    """All the runs of one table cell. Ghost/Call: until `runs` runs AND `min_shots` shots are
    done; Sprint: exactly `runs` runs. A run's seed does not depend on sigma: the same tables are
    dealt to every cell of a mode."""
    (mode, sigma, t_aim, calibrated, level), runs, min_shots, seed = args
    out: list[RunStats] = []
    shots = 0
    i = 0
    while i < runs or (t_aim is None and shots < min_shots):
        run_seed = seed * 1_000_003 + {"ghost": 1, "call": 2, "sprint": 3}[mode] * 100_000 + i
        out.append(play_run(mode, sigma, run_seed, t_aim=t_aim, calibrated=calibrated, level=level))
        shots += len(out[-1].shots)
        i += 1
    return out


def _pct(a: int, b: int) -> str:
    return f"{100 * a / b:.1f}%" if b else "-"


def _row(label: str, mode: str, runs: list[RunStats]) -> str:
    shots = [s for r in runs for s in r.shots]
    return (
        f"{label:>6} | {mode:<5} {len(shots):5d} "
        f"{_pct(sum(s.potted for s in shots), len(shots)):>7} "
        f"{_pct(sum(s.right for s in shots), len(shots)):>7} "
        f"{sum(r.score for r in runs) / len(runs):9.1f} "
        f"{_pct(sum(r.won for r in runs), len(runs)):>9}"
    )


def report_basic(results: dict) -> None:
    print(
        "\n== Đấu Ma và Gọi Lỗ (không tính cú phá); chuỗi = bi mục tiêu vào tới khi hết 3 mạng =="
    )
    print(
        f"{'sigma':>6} | {'chế độ':<5} {'cú':>5} {'vào bi':>7} {'đúng':>7} "
        f"{'chuỗi TB':>9} {'dọn 15':>9}"
    )
    for sigma in SIGMAS:
        for mode in ("ghost", "call"):
            print(_row(f"{sigma:.1f}°", mode, results[(mode, sigma, None, False)]))
    for mode in ("ghost", "call"):
        print(_row("0.0°*", mode, results[(mode, 0.0, None, True)]))
    print("  vào bi = bi mục tiêu xuống lỗ nào cũng tính; đúng = cú được tính điểm (Gọi Lỗ: đúng")
    print("  lỗ, bi cái không xuống lỗ). * = bot hiệu chỉnh góc trên bản sao bàn (xem dưới).")


def _failures(shots: list[ShotRec], title: str) -> None:
    lined = [s for s in shots if s.lined]
    free = [s for s in shots if not s.lined]
    right = sum(s.right for s in lined)
    rate = right / len(lined)
    print(f"\n  {title}: {_pct(right, len(lined))} đúng trên {len(lined)} cú có lỗ chỉ định")
    if free:
        print(
            f"    (+ {len(free)} cú mà bàn không còn đường nào, luật không chỉ lỗ: "
            f"{_pct(sum(s.right for s in free), len(free))} đúng; bỏ ra ngoài)"
        )
    if rate >= FEASIBLE_RATE:
        return
    print(
        f"    < {100 * FEASIBLE_RATE:.0f}%: 10 cú thất bại đầu tiên (bi, lỗ, góc cắt, khoảng cách):"
    )
    for s in [s for s in lined if not s.right][:10]:
        eng = "" if s.engine_deg is None else f", bi lệch đường {s.engine_deg:+.1f}°"
        print(
            f"     bi {s.ball:2d} -> lỗ {s.pocket}  cắt {s.cut_deg:4.1f}°  "
            f"bi-lỗ {s.reach_m:.2f} m  "
            f"cái-bi {s.run_m:.2f} m  lực {s.power:.2f}  ({s.why}{eng})"
        )


def _why_counts(shots: list[ShotRec]) -> str:
    why = Counter(s.why for s in shots if s.lined and not s.right)
    return ", ".join(f"{k} {v}" for k, v in why.most_common())


def feasibility(results: dict) -> None:
    print("\n== Phép thử khả thi: Gọi Lỗ, sigma 0° (bot không nhiễu) ==")
    raw = [s for r in results[("call", 0.0, None, False)] for s in r.shots]
    fixed = [s for r in results[("call", 0.0, None, True)] for s in r.shots]
    _failures(raw, "bot thường")
    print("    Lý do thất bại: " + _why_counts(raw))
    _failures(fixed, "bot hiệu chỉnh")
    print("    Lý do thất bại: " + _why_counts(fixed))
    print("\n  Độ lệch do vật lý (bot thường, sigma 0, cú có lỗ): hướng bi mục tiêu vừa bị đánh đi")
    print("  so với đường tới lỗ, đo trên bản sao bàn")
    print(f"  {'góc cắt':>9} | {'cú':>4} {'lệch TB':>8} {'lệch lớn nhất':>14} {'đúng':>7}")
    lined = [s for s in raw if s.lined]
    for lo, hi in CUT_BINS:
        part = [s for s in lined if lo <= s.cut_deg < hi]
        eng = [abs(s.engine_deg) for s in part if s.engine_deg is not None]
        if part:
            mean = f"{sum(eng) / len(eng):.2f}°" if eng else "-"
            top = f"{max(eng):.2f}°" if eng else "-"
            print(
                f"  {lo:3.0f}-{min(hi, 90):2.0f}° | {len(part):4d} {mean:>8} {top:>14} "
                f"{_pct(sum(s.right for s in part), len(part)):>7}"
            )


def report_sprint(results: dict) -> None:
    print(
        "\n== Nước Rút (bot thường): t_aim = giây ngắm giả định trước mỗi cú, bi lăn không tính =="
    )
    print(
        f"{'sigma':>6} {'t_aim':>6} | {'ván':>4} {'bi vào TB':>10} {'dọn 15':>8} {'hết giờ':>8} "
        f"{'cú/ván':>7}"
    )
    for sigma in SPRINT_SIGMAS:
        for t_aim in SPRINT_T_AIMS:
            runs = results[("sprint", sigma, t_aim, False)]
            shots = sum(len(r.shots) + r.breaks for r in runs) / len(runs)
            print(
                f"{sigma:5.1f}° {t_aim:5.0f}s | {len(runs):4d} "
                f"{sum(r.score for r in runs) / len(runs):10.1f} "
                f"{_pct(sum(r.won for r in runs), len(runs)):>8} "
                f"{_pct(sum(r.timed_out for r in runs), len(runs)):>8} {shots:7.1f}"
            )
    print(
        f"  (giờ: bắt đầu {SPRINT_START_S:.0f} s, trần {SPRINT_CAP_S:.0f} s, "
        f"vào +{SPRINT_POT_BONUS_S:.0f} s, trượt -{SPRINT_MISS_COST_S:.0f} s, "
        f"bi cái xuống lỗ -{SPRINT_SCRATCH_COST_S:.0f} s)"
    )
    gain, cost = SPRINT_POT_BONUS_S, SPRINT_MISS_COST_S
    row = ", ".join(f"{t:.0f} s -> {100 * (cost + t) / (gain + cost):.0f}%" for t in SPRINT_T_AIMS)
    print(f"  Tỉ lệ vào để giờ không tụt dần (hoà vốn, bỏ qua bi cái xuống lỗ): {row}")


def main() -> int:
    ap = argparse.ArgumentParser(description="Người chơi giả cho Luyện tập (ước lượng thô).")
    ap.add_argument("--runs", type=int, default=60, help="ván tối thiểu mỗi ô (mặc định 60)")
    ap.add_argument("--min-shots", type=int, default=300, help="cú tối thiểu mỗi ô Đấu Ma/Gọi Lỗ")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--level", choices=("easy", "hard"), default="hard", help="mức (mặc định hard)")
    ap.add_argument("--jobs", type=int, default=0, help="số tiến trình (0 = số lõi, tối đa 8)")
    args = ap.parse_args()

    lv = args.level
    cells: list[Cell] = [(m, s, None, False, lv) for s in SIGMAS for m in ("ghost", "call")]
    cells += [(m, 0.0, None, True, lv) for m in ("ghost", "call")]
    cells += [("sprint", s, t, False, lv) for s in SPRINT_SIGMAS for t in SPRINT_T_AIMS]
    jobs = [(cell, args.runs, args.min_shots, args.seed) for cell in cells]
    workers = args.jobs or min(8, os.cpu_count() or 1)
    print(
        "ƯỚC LƯỢNG THÔ bằng bot (ngắm kiểu bi ma, xoáy 0, không đánh băng) — "
        f"KHÔNG phải cảm giác người chơi. Mức: {lv}."
    )
    if workers > 1:
        with ProcessPoolExecutor(workers) as pool:
            done = list(pool.map(run_cell, jobs))
    else:
        done = [run_cell(j) for j in jobs]
    results = {c[:4]: r for c, r in zip(cells, done, strict=True)}  # (the level is one for all)
    report_basic(results)
    feasibility(results)
    report_sprint(results)
    return 0


if __name__ == "__main__":
    sys.exit(main())
