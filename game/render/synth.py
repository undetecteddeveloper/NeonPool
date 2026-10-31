"""The synthwave night behind the menu and the how-to-play screen.

A sky with twinkling stars, a striped sun sinking into the horizon, a floor grid rolling towards
you, and ribbons of light along the horizon that are ALIVE: each strand is a chain of points tied
by springs (a string, as in a wave-on-a-string simulation), stepped every frame. The strands
breathe on their own, lean towards the pointer, carry a pulse of light when a button is chosen
and jump when you click, like water when a stone goes in. Time-driven, no randomness.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import pygame as pg

from game.render import crt
from game.render import palette as C
from game.render.draw import RING_PX, SpinBalls
from game.render.layout import BALL_PX
from game.render.view import View

# --- the strands -------------------------------------------------------------------------------
STRANDS = 6
POINT_STEP = 12.0  # logical px between the points of a strand
TENSION = 1800.0  # how hard neighbours pull (1/s^2): a ripple runs ~POINT_STEP*sqrt(T) = 500 px/s
SPRING = 26.0  # how hard a point is pulled back to its resting wave (1/s^2)
DAMPING = 2.4  # 1/s: a splash dies down in a couple of seconds
SUBSTEP = 1 / 120  # fixed physics step of the strands (stable: TENSION * SUBSTEP^2 < 1)
LEAN_PX = 110.0  # the strands lean at most this far towards the pointer
LEAN_SIGMA = 120.0  # ... over this width around it
PULSE_SPEED = 820.0  # a pulse of light runs along the strands this fast (logical px/s)
PULSE_S = 1.6
SUN_STRIPE_S = 2.4  # a stripe of the sun takes this long to slide down one step
BAND_UP, BAND_DOWN = 110.0, 190.0  # the strands' band: this far above / below the horizon
GRID_ROWS = 14  # cross lines of the floor grid on screen at once
# balls that float up out of the floor and drift away on the ribbons (menu)
FLOAT_ORDER = (*range(1, 16), 0)  # which ball comes up next: 1 to 15, then the cue ball
FLOAT_EVERY_S = 2.4  # a new ball comes up this often ...
FLOAT_MAX = 5  # ... while fewer than this many are on screen
FLOAT_SCALE = 1.43  # the balls are this many times their size on the table (2.2 less 35%)
FLOAT_RISE = 150.0  # rising speed far from the surface (logical px/s); it slows on arrival
FLOAT_SLANT = 0.36  # far from the ribbons the current carries a ball 0.36 px sideways per px it
#                     rises: a slant of about 20 degrees off the vertical
FLOAT_DRIFT = 70.0  # at the ribbons the current is stronger: the drifting speed (logical px/s)
FLOAT_NEAR = 160.0  # the current reaches its full strength this close to the ribbons (px)
FLOAT_FLOW_EASE = 3.0  # 1/s: a ball follows a change of the current this fast (no jerks)
FLOAT_SINK = 0.35  # a floating ball sits this much of its radius below the surface
# depth: how many of the STRANDS run behind a ball (the others cross in front of it). It wanders
# between the strands, never behind all of them or in front of all of them
FLOAT_DEPTH_MID = 3.0
FLOAT_DEPTH_SWING = 1.9
FLOAT_DEPTH_RATE = (0.45, 0.9)  # rad/s: a ball's own pace, from ... to
# turning: the number and the stripe turn back and forth, wide while rising, less while drifting
FLOAT_SPIN_RISE = 90.0  # degrees each way
FLOAT_SPIN_DRIFT = 35.0
FLOAT_SPIN_RATE = (0.9, 1.7)  # rad/s while rising
FLOAT_SPIN_SLOW = 0.55  # ... and this fraction of it while drifting
FLOAT_CALM_EASE = 1.5  # 1/s: rising turns into drifting this fast
GRID_LEVELS = 8  # brightness steps of a cross line (made once, then only placed)

Point = tuple[float, float]


def _gauss(x: np.ndarray, centre: float, sigma: float) -> np.ndarray:
    return np.exp(-(((x - centre) / sigma) ** 2))


def _hash(i: int, salt: float) -> float:
    """Repeatable pseudo-random number in [0, 1) (stars must not change between runs)."""
    return abs(math.sin(i * 12.9898 + salt * 78.233) * 43758.5453) % 1.0


class Strands:
    """The living ribbons: STRANDS strings of points across the whole canvas width."""

    def __init__(self, left: float, right: float, base_y: float, amplitude: float = 26.0) -> None:
        n = max(8, math.ceil((right - left) / POINT_STEP) + 1)
        self.x = np.linspace(left, right, n)
        self.base_y, self.amp = base_y, amplitude
        self.y = np.zeros((STRANDS, n))  # displacement from the horizon
        self.vy = np.zeros((STRANDS, n))
        self.lean = 0.0  # current lean (eased towards the pointer)
        self.lean_x = (left + right) / 2
        self.target_lean = 0.0
        self.pulses: list[tuple[float, float, tuple[int, int, int]]] = []  # (x, birth, colour)
        self._acc = 0.0
        self._t = 0.0
        self.y[:] = self._rest(0.0)

    def _rest(self, t: float) -> np.ndarray:
        """The resting shape at time t: two waves running opposite ways plus a slow swell, each
        strand a little out of step, so the ribbon braids and breathes."""
        i = np.arange(STRANDS)[:, None]
        x = self.x[None, :]
        a = self.amp
        return (
            a * np.sin(x * 0.011 - t * 1.3 + i * 0.55)
            + 0.5 * a * np.sin(x * 0.023 + t * 0.9 + i * 1.1)
            + 0.45 * a * np.sin(x * 0.004 + t * 0.35) * np.sin(t * 0.5 + i * 0.8)
        )

    def point_to(self, pos: Point | None) -> None:
        """Lean towards the pointer (None: settle back)."""
        if pos is None:
            self.target_lean = 0.0
            return
        self.lean_x = pos[0]
        self.target_lean = max(-LEAN_PX, min(LEAN_PX, (pos[1] - self.base_y) * 0.55))

    def pulse(self, x: float, clock: float, colour=C.MAGENTA) -> None:
        """A pulse of light that runs both ways along the strands from x, with a small kick."""
        self.pulses = [p for p in self.pulses if clock - p[1] < PULSE_S][-5:]
        self.pulses.append((x, clock, colour))
        self.vy -= 160.0 * _gauss(self.x, x, 50.0)[None, :]

    def splash(self, x: float, strength: float = 1.0) -> None:
        """A stone in the water: the strands near x jump, each a little differently."""
        sign = np.where(np.arange(STRANDS) % 2 == 0, 1.0, -0.7)[:, None]
        self.vy += strength * 900.0 * sign * _gauss(self.x, x, 38.0)[None, :]

    def press(self, x: float, sigma: float, force: float, dt: float) -> None:
        """Something heavy floats on the ribbons at x: they sink under it (`force` px/s^2 down)."""
        self.vy += force * dt * _gauss(self.x, x, sigma)[None, :]

    def surface(self, x: float) -> float:
        """The logical y of the ribbon (the middle of its strands) at x."""
        return self.base_y + float(np.interp(x, self.x, self.y.mean(axis=0)))

    def update(self, dt: float) -> None:
        self._acc += min(dt, 0.05)
        while self._acc >= SUBSTEP:
            self._acc -= SUBSTEP
            self._t += SUBSTEP
            self.lean += (self.target_lean - self.lean) * min(1.0, SUBSTEP * 5.0)
            target = self._rest(self._t) + self.lean * _gauss(self.x, self.lean_x, LEAN_SIGMA)
            y = self.y
            lap = np.zeros_like(y)
            lap[:, 1:-1] = y[:, :-2] + y[:, 2:] - 2 * y[:, 1:-1]
            acc = TENSION * lap + SPRING * (target - y)
            acc -= DAMPING * self.vy
            self.vy += acc * SUBSTEP
            self.y += self.vy * SUBSTEP
            self.y[:, 0], self.y[:, -1] = self.y[:, 1], self.y[:, -2]  # loose ends

    def glow_at(self, clock: float) -> np.ndarray:
        """Extra light along the strands from the running pulses and the motion (0..~1.5)."""
        light = np.clip(np.abs(self.vy).mean(axis=0) / 220.0, 0.0, 0.8)
        for x0, born, _ in self.pulses:
            age = clock - born
            if 0 <= age < PULSE_S:
                fade = (1 - age / PULSE_S) ** 1.5
                d = PULSE_SPEED * age
                light = light + fade * (_gauss(self.x, x0 - d, 55) + _gauss(self.x, x0 + d, 55))
        return light


def front_weights(depth: float) -> list[float]:
    """How much of each strand crosses IN FRONT of a ball at this depth (0 behind it, 1 in front;
    in between, a strand is passing through the ball's depth and fades from one to the other)."""
    return [min(1.0, max(0.0, i + 1 - depth)) for i in range(STRANDS)]


@dataclass
class FloatBall:
    number: int
    x: float
    y: float
    floating: bool = False
    vx: float = 0.0  # sideways speed (logical px/s): the current carries the ball
    calm: float = 0.0  # 0 while rising .. 1 once it drifts on the ribbons
    depth_phase: float = 0.0
    depth_rate: float = FLOAT_DEPTH_RATE[0]
    spin_phase: float = 0.0
    spin_rate: float = FLOAT_SPIN_RATE[0]

    def depth(self) -> float:
        """How many strands run behind the ball now."""
        return FLOAT_DEPTH_MID + FLOAT_DEPTH_SWING * math.sin(self.depth_phase)

    def turn(self) -> float:
        """How far the number and the stripe are turned now, in degrees (back and forth)."""
        amp = FLOAT_SPIN_RISE + (FLOAT_SPIN_DRIFT - FLOAT_SPIN_RISE) * self.calm
        return amp * math.sin(self.spin_phase)


class Floaters:
    """Balls rising out of the floor one after another, carried up and to the right by the
    current, turning back and forth as they come. Arriving at the ribbons each slows down, then
    bobs on them and drifts away with the waves until it leaves the screen. They weave between
    the strands (see FloatBall.depth) and never touch the ribbons' motion: the ribbons are the
    same with or without them."""

    def __init__(self, v: View, strands: Strands, left: float, right: float, bottom: float) -> None:
        self.v, self.strands = v, strands
        self.left, self.right, self.bottom = left, right, bottom
        self.sprites = SpinBalls(v.scaled(FLOAT_SCALE))
        self.r = BALL_PX * FLOAT_SCALE  # logical radius
        self.disc = self._make_disc()
        self.balls: list[FloatBall] = []
        self._spawned = 0
        self._next = 0.6  # the first ball comes up soon after the menu opens
        self._t = 0.0

    def _make_disc(self) -> pg.Surface:
        """White inside a ball (its ring included), black outside, smooth edge: where the strands
        in front of a ball may show."""
        size, k = self.sprites.size, 4
        sv = self.sprites.v
        ring = max(2.0 / k, RING_PX * C.LOOK.line * sv.s)
        big = pg.Surface((size * k, size * k))
        pg.draw.circle(big, (255, 255, 255), (size * k / 2, size * k / 2),
                       (BALL_PX * sv.s + ring / 2) * k)  # fmt: skip
        return pg.transform.smoothscale(big, (size, size))

    def update(self, dt: float, spawn: bool = True) -> None:
        """`spawn` False: no new ball comes up (the ones afloat drift away)."""
        self._t += dt
        if spawn and self._t >= self._next:
            self._next = self._t + FLOAT_EVERY_S
            if len(self.balls) < FLOAT_MAX:
                self.balls.append(self._spawn())
        for ball in self.balls:
            self._move(ball, dt)
        self.balls = [b for b in self.balls if b.x - self.r * 2 < self.right]

    def _spawn(self) -> FloatBall:
        i = self._spawned
        self._spawned += 1
        span = self.right - self.left
        x = self.left + span * (0.06 + 0.7 * _hash(i, 7))  # drifts right: start leftish
        lo, hi = FLOAT_DEPTH_RATE
        s_lo, s_hi = FLOAT_SPIN_RATE
        return FloatBall(
            number=FLOAT_ORDER[i % len(FLOAT_ORDER)],
            x=x,
            y=self.bottom + self.r,
            vx=FLOAT_SLANT * FLOAT_RISE,  # carried sideways from the very first moment
            depth_phase=6.28 * _hash(i, 11),
            depth_rate=lo + (hi - lo) * _hash(i, 13),
            spin_phase=6.28 * _hash(i, 17),
            spin_rate=s_lo + (s_hi - s_lo) * _hash(i, 19),
        )

    def _move(self, b: FloatBall, dt: float) -> None:
        surface = self.strands.surface(b.x) + self.r * FLOAT_SINK
        near = 1.0
        if not b.floating:
            gap = b.y - surface
            near = max(0.0, 1.0 - gap / FLOAT_NEAR)
            b.y -= (35.0 + (FLOAT_RISE - 35.0) * min(1.0, gap / 120.0)) * dt  # slows on arrival
            b.floating = b.y <= surface
        # the current: weak and slanting far away, stronger near the ribbons; the ball follows it
        far = FLOAT_SLANT * FLOAT_RISE
        flow = far + (FLOAT_DRIFT - far) * near
        b.vx += (flow - b.vx) * min(1.0, dt * FLOAT_FLOW_EASE)
        b.x += b.vx * dt
        if b.floating:
            b.y = self.strands.surface(b.x) + self.r * FLOAT_SINK
        b.calm += ((1.0 if b.floating else 0.0) - b.calm) * min(1.0, dt * FLOAT_CALM_EASE)
        b.depth_phase += b.depth_rate * dt
        b.spin_phase += b.spin_rate * (1.0 - (1.0 - FLOAT_SPIN_SLOW) * b.calm) * dt

    def draw(self, canvas: pg.Surface, front=None) -> None:
        """Draw the balls; `front(canvas, ball, spot)` then draws what passes in front of each."""
        size = self.sprites.size
        half = size / 2
        for b in self.balls:
            px, py = self.v.pt((b.x, b.y))
            spot = pg.Rect(round(px - half), round(py - half), size, size)
            canvas.blit(self.sprites.spun(b.number, b.turn()), spot.topleft,
                        special_flags=pg.BLEND_PREMULTIPLIED)  # fmt: skip
            if front is not None:
                front(canvas, b, spot)


class Synthwave:
    """The whole backdrop for one view. `horizon` is a logical y; `sun` False hides the sun."""

    def __init__(
        self,
        v: View,
        horizon: float,
        *,
        sun: bool = True,
        sun_r: float = 150.0,
        dim: float = 1.0,
        floaters: bool = False,
    ) -> None:
        self.v, self.horizon, self.has_sun, self.sun_r, self.dim = v, horizon, sun, sun_r, dim
        left, top, right, bottom = v.logical_bounds()
        self.left, self.top, self.right, self.bottom = left, top, right, bottom
        self.cx = 640.0
        self.strands = Strands(left - 20, right + 20, horizon)
        self.floaters = Floaters(v, self.strands, left, right, bottom) if floaters else None
        self.bg = self._bake_sky()
        self.sun = self._bake_sun() if sun else None
        self.stars = [
            (left + _hash(i, 1) * (right - left), top + _hash(i, 2) * (horizon - top - 40),
             0.5 + _hash(i, 3), _hash(i, 4) * 6.28, 0.6 + 1.6 * _hash(i, 5))
            for i in range(90)
        ]  # fmt: skip
        cw, ch = v.canvas
        # the strands live in a band round the horizon: only that band is redrawn every frame
        self.layer_top = max(0, v.i(horizon - BAND_UP) + v.oy)
        bottom_px = min(ch, v.i(horizon + BAND_DOWN) + v.oy)
        self.layer = pg.Surface((cw, max(1, bottom_px - self.layer_top)))
        self._rungs = self._bake_rungs()
        self._geo: tuple[np.ndarray, np.ndarray, np.ndarray] | None = None  # see _geometry
        self._front = (  # where the strands in front of a ball are drawn before they are added
            pg.Surface((self.floaters.sprites.size,) * 2) if self.floaters is not None else None
        )

    # --- baking ---------------------------------------------------------------------------
    def _bake_sky(self) -> pg.Surface:
        """Sky and floor gradients and the sun's soft glow, at the canvas size (opaque)."""
        v = self.v
        cw, ch = v.canvas
        w, h = 96, 54
        ys = (np.arange(h) + 0.5) / h * ch
        xs = (np.arange(w) + 0.5) / w * cw
        hy = v.pt((0, self.horizon))[1]
        rgb = np.zeros((h, w, 3))
        sky_t = np.clip((ys - 0) / max(1.0, hy), 0, 1) ** 1.6
        floor_t = np.clip((ys - hy) / max(1.0, ch - hy), 0, 1) ** 0.7
        for c in range(3):
            sky = C.SKY_TOP[c] + (C.SKY_LOW[c] - C.SKY_TOP[c]) * sky_t
            floor = C.FLOOR_FAR[c] + (C.FLOOR_NEAR[c] - C.FLOOR_FAR[c]) * floor_t
            rgb[:, :, c] = np.where(ys < hy, sky, floor)[:, None]
        if self.has_sun:  # the sun lights the sky round it
            sx, sy = v.pt((self.cx, self.horizon))
            r = v.n(self.sun_r)
            d = np.sqrt((xs[None, :] - sx) ** 2 + ((ys[:, None] - sy) * 1.25) ** 2) / (r * 2.6)
            halo = np.clip(1 - d, 0, 1) ** 2 * (ys[:, None] < hy)
            for c, k in zip(range(3), (110, 28, 90), strict=True):
                rgb[:, :, c] += halo * k
        rgb *= self.dim
        rgb = np.clip(rgb, 0, 255).astype(np.uint8)
        small = pg.surfarray.make_surface(rgb.transpose(1, 0, 2))
        out = pg.transform.smoothscale(small, (cw, ch))
        # the horizon: a thin bright line with a soft glow above and below
        line = pg.Surface((cw, max(1, v.i(24))))
        line.fill((0, 0, 0))
        mid = line.get_height() // 2
        for width, k in ((v.i(16), 0.12), (v.i(7), 0.3), (max(1, v.i(1.6)), 1.0)):
            pg.draw.line(line, C.scale(C.MAGENTA, k * self.dim), (0, mid), (cw, mid), max(1, width))
        out.blit(line, (0, round(hy) - mid), special_flags=pg.BLEND_RGB_ADD)
        self._bake_grid_lines(out, hy)
        crt.darken_corners(out)
        return out

    def _bake_grid_lines(self, out: pg.Surface, hy: float) -> None:
        """The floor lines running to the vanishing point never move: drawn once, into the sky."""
        v = self.v
        cw, ch = out.get_size()
        depth = ch - hy
        if depth <= 4:
            return
        layer = pg.Surface((cw, max(1, ch - round(hy))))
        layer.fill((0, 0, 0))
        vx = v.pt((self.cx, 0))[0]
        spread = v.n(120)
        n = int(cw / (spread * 0.18)) + 2
        for j in range(-n, n + 1):
            top, bottom = (vx + j * spread * 0.18, 0), (vx + j * spread * 3.2, depth * 1.35)
            for width, k in ((max(1, v.i(4)), 0.12), (max(1, v.i(1.3)), 0.55)):
                pg.draw.line(layer, C.scale(C.GRID, k * self.dim), top, bottom, width)
        out.blit(layer, (0, round(hy)), special_flags=pg.BLEND_RGB_ADD)

    def _bake_rungs(self) -> list[pg.Surface]:
        """One cross line of the grid (a lit line with its glow) at GRID_LEVELS brightnesses."""
        v = self.v
        cw = v.canvas[0]
        h = max(3, v.i(6))
        out = []
        for level in range(GRID_LEVELS):
            k = (level + 1) / GRID_LEVELS
            rung = pg.Surface((cw, h))
            rung.fill((0, 0, 0))
            for width, kk in ((max(1, v.i(4)), 0.22), (max(1, v.i(1.3)), 1.0)):
                colour = C.scale(C.GRID, k * kk * self.dim)
                pg.draw.line(rung, colour, (0, h // 2), (cw, h // 2), width)
            out.append(rung)
        return out

    def _bake_sun(self) -> pg.Surface:
        """The upper half of the sun: a disc from yellow (top) through orange to pink."""
        v = self.v.framed()
        r = v.n(self.sun_r)
        k = 3
        size = (math.ceil(2 * r) + 2, math.ceil(r) + 2)
        big = pg.Surface((size[0] * k, size[1] * k), pg.SRCALPHA)
        rows = big.get_height()
        for yy in range(rows):
            t = yy / max(1, rows - 1)
            col = (
                C.lerp(C.SUN_TOP, C.SUN_MID, t / 0.55)
                if t < 0.55
                else C.lerp(C.SUN_MID, C.SUN_LOW, (t - 0.55) / 0.45)
            )
            pg.draw.line(big, (*C.scale(col, self.dim), 255), (0, yy), (big.get_width(), yy))
        mask = pg.Surface(big.get_size(), pg.SRCALPHA)
        pg.draw.circle(mask, (255, 255, 255, 255), (big.get_width() / 2, rows), r * k)
        big.blit(mask, (0, 0), special_flags=pg.BLEND_RGBA_MIN)
        return pg.transform.smoothscale(big.premul_alpha(), size)  # its glow is in the sky

    # --- input -------------------------------------------------------------------------------
    def point_to(self, pos: Point | None) -> None:
        self.strands.point_to(pos)

    def pulse(self, x: float, clock: float, colour=C.MAGENTA) -> None:
        self.strands.pulse(x, clock, colour)

    def splash(self, x: float, strength: float = 1.0) -> None:
        self.strands.splash(x, strength)

    def update(self, dt: float, balls: bool = True) -> None:
        """`balls` False: the menu's balls stop coming up (the credits are on the water)."""
        self.strands.update(dt)
        if self.floaters is not None:
            self.floaters.update(dt, balls)

    # --- drawing -----------------------------------------------------------------------------
    def draw(self, canvas: pg.Surface, clock: float) -> None:
        canvas.blit(self.bg, (0, 0))
        self._draw_stars(canvas, clock)
        if self.sun is not None:
            self._draw_sun(canvas, clock)
        self._draw_grid(canvas, clock)
        self._geometry(clock)
        layer = self.layer
        layer.fill((0, 0, 0))
        self._draw_strands(layer, clock)
        canvas.blit(layer, (0, self.layer_top), special_flags=pg.BLEND_RGB_ADD)
        if self.floaters is not None:  # the balls hide the strands behind them; the strands in
            self.floaters.draw(canvas, self._draw_front)  # front of a ball cross over its face

    def _draw_stars(self, canvas: pg.Surface, clock: float) -> None:
        v = self.v
        for x, y, size, phase, speed in self.stars:
            k = 0.35 + 0.65 * (0.5 + 0.5 * math.sin(clock * speed + phase)) ** 3
            c = C.scale(C.lerp(C.CYAN, C.WHITE, 0.6), k * self.dim)
            px, py = v.ipt((x, y))
            s = max(1, v.i(size))
            canvas.fill(c, (px, py, s, s))

    def _draw_sun(self, canvas: pg.Surface, clock: float) -> None:
        """The sun, with dark stripes cut through its lower part that slide slowly down."""
        v = self.v
        sx, hy = v.pt((self.cx, self.horizon))
        r = v.n(self.sun_r)
        top = round(hy - self.sun.get_height() + 2)
        left = round(sx - self.sun.get_width() / 2)
        canvas.blit(self.sun, (left, top), special_flags=pg.BLEND_PREMULTIPLIED)
        step = r * 0.16
        phase = (clock / SUN_STRIPE_S) % 1.0
        y = hy - r * 0.62 + phase * step
        while y < hy:
            depth = (y - (hy - r * 0.62)) / (r * 0.62)  # 0 at the first stripe .. 1 at the horizon
            thick = max(1.0, step * (0.12 + 0.55 * depth))
            band = pg.Rect(left, round(y), self.sun.get_width(), max(1, round(thick)))
            canvas.blit(self.bg, band.topleft, area=band)  # the sky shows through the stripe
            y += step

    def _draw_grid(self, canvas: pg.Surface, clock: float) -> None:
        """The cross lines of the floor grid, rolling towards the viewer (brighter when near)."""
        v = self.v
        ch = v.canvas[1]
        hy = v.pt((0, self.horizon))[1]
        depth = ch - hy
        if depth <= 4:
            return
        roll = (clock * 0.55) % 1.0
        half = self._rungs[0].get_height() // 2
        for i in range(GRID_ROWS):
            z = (i + 1 - roll) / GRID_ROWS  # 0 near the horizon .. 1 at the bottom
            y = hy + depth * z**2.2
            level = min(GRID_LEVELS - 1, int((0.08 + 0.55 * z) / 0.63 * GRID_LEVELS))
            canvas.blit(self._rungs[level], (0, round(y) - half), special_flags=pg.BLEND_RGB_ADD)

    def _geometry(self, clock: float) -> None:
        """Where every strand is on the canvas (device px) and how much light runs along it."""
        v, st = self.v, self.strands
        u = np.arange(STRANDS) / (STRANDS - 1)
        spread = (np.arange(STRANDS) - (STRANDS - 1) / 2) * 3.0  # side by side, then they braid
        ys = (st.base_y + spread[:, None] + st.y * (0.7 + 0.3 * u)[:, None]) * v.s + v.oy
        self._geo = (st.x * v.s + v.ox, ys, st.glow_at(clock))

    def _draw_strands(self, layer: pg.Surface, clock: float) -> None:
        v = self.v
        top = self.layer_top
        xs, ys, light = self._geo
        chunks = 9
        n = len(xs)
        edges = np.linspace(0, n - 1, chunks + 1).astype(int)
        glow_w, mid_w, core_w = v.i(7 * C.LOOK.reach), max(1, v.i(3)), max(1, v.i(1.4))
        for i in range(STRANDS):
            base = C.lerp(C.CYAN, C.MAGENTA, i / (STRANDS - 1))
            pts = np.column_stack((xs, ys[i] - top)).tolist()
            # the wide soft glow in one go; the bright parts carry the light of pulses and motion
            pg.draw.lines(layer, C.scale(base, 0.12 * self.dim), False, pts, max(1, glow_w))
            for c in range(chunks):
                a, b = edges[c], edges[c + 1] + 1
                seg = pts[a:b]
                k = float(light[a:b].mean())
                col = C.lerp(base, C.WHITE, min(0.8, k * 0.6))
                bright = (0.8 + 0.5 * min(1.5, k)) * self.dim
                pg.draw.lines(layer, C.scale(col, bright * 0.35), False, seg, mid_w)
                pg.draw.lines(layer, C.scale(col, bright), False, seg, core_w)

    def _draw_front(self, canvas: pg.Surface, ball: FloatBall, spot: pg.Rect) -> None:
        """The strands that run in FRONT of this ball cross over its face (sharp lines, drawn only
        inside the ball: the ribbons round it are already on the canvas)."""
        v = self.v
        xs, ys, light = self._geo
        a = max(0, int(np.searchsorted(xs, spot.left)) - 1)
        b = min(len(xs), int(np.searchsorted(xs, spot.right)) + 1)
        if b - a < 2:
            return
        near = (ys[:, a:b] > spot.top - 3) & (ys[:, a:b] < spot.bottom + 3)
        if not near.any():  # still rising below the ribbons
            return
        tmp = self._front
        tmp.fill((0, 0, 0))
        mid_w, core_w = max(1, v.i(3)), max(1, v.i(1.4))
        k = float(light[a:b].mean())
        for i, w in enumerate(front_weights(ball.depth())):
            if w <= 0.0:
                continue
            pts = np.column_stack((xs[a:b] - spot.left, ys[i, a:b] - spot.top)).tolist()
            col = C.lerp(C.lerp(C.CYAN, C.MAGENTA, i / (STRANDS - 1)), C.WHITE, min(0.8, k * 0.6))
            bright = (0.8 + 0.5 * min(1.5, k)) * self.dim * w
            pg.draw.lines(tmp, C.scale(col, bright * 0.35), False, pts, mid_w)
            pg.draw.lines(tmp, C.scale(col, bright), False, pts, core_w)
        tmp.blit(self.floaters.disc, (0, 0), special_flags=pg.BLEND_RGB_MULT)
        canvas.blit(tmp, spot.topleft, special_flags=pg.BLEND_RGB_ADD)
