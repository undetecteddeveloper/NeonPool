"""The synthwave night behind the menu and the how-to-play screen.

A sky with twinkling stars, a striped sun sinking into the horizon, a floor grid rolling towards
you, and ribbons of light along the horizon that are ALIVE: each strand is a chain of points tied
by springs (a string, as in a wave-on-a-string simulation), stepped every frame. The strands
breathe on their own, lean towards the pointer, carry a pulse of light when a button is chosen
and jump when you click, like water when a stone goes in. Time-driven, no randomness.
"""

from __future__ import annotations

import math

import numpy as np
import pygame as pg

from game.render import crt
from game.render import palette as C
from game.render.draw import BallSprites
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
FLOAT_DRIFT = 34.0  # drifting speed along the ribbons, the way the waves run (logical px/s)
FLOAT_SINK = 0.35  # a floating ball sits this much of its radius below the surface
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


class Floaters:
    """Balls rising out of the floor one after another; arriving at the ribbon each slows down,
    then bobs on it and drifts away with the waves until it leaves the screen. They never touch
    the ribbons' motion: the ribbons are the same with or without them."""

    def __init__(self, v: View, strands: Strands, left: float, right: float, bottom: float) -> None:
        self.v, self.strands = v, strands
        self.left, self.right, self.bottom = left, right, bottom
        self.sprites = BallSprites(v.scaled(FLOAT_SCALE))
        self.r = BALL_PX * FLOAT_SCALE  # logical radius
        self.balls: list[list] = []  # [number, x, y, floating]
        self._spawned = 0
        self._next = 0.6  # the first ball comes up soon after the menu opens
        self._t = 0.0

    def update(self, dt: float) -> None:
        self._t += dt
        if self._t >= self._next:
            self._next = self._t + FLOAT_EVERY_S
            if len(self.balls) < FLOAT_MAX:
                i = self._spawned
                number = FLOAT_ORDER[i % len(FLOAT_ORDER)]
                span = self.right - self.left
                x = self.left + span * (0.06 + 0.7 * _hash(i, 7))  # drifts right: start leftish
                self.balls.append([number, x, self.bottom + self.r, False])
                self._spawned += 1
        for ball in self.balls:
            number, x, y, floating = ball
            surface = self.strands.surface(x) + self.r * FLOAT_SINK
            if not floating:
                gap = y - surface
                y -= (35.0 + (FLOAT_RISE - 35.0) * min(1.0, gap / 120.0)) * dt  # slows on arrival
                floating = y <= surface
            if floating:
                x += FLOAT_DRIFT * dt
                y = self.strands.surface(x) + self.r * FLOAT_SINK
            ball[1:] = [x, y, floating]
        self.balls = [b for b in self.balls if b[1] - self.r * 2 < self.right]

    def draw(self, canvas: pg.Surface) -> None:
        half = self.sprites.size / 2
        for number, x, y, _ in self.balls:
            px, py = self.v.pt((x, y))
            canvas.blit(self.sprites.get(number), (round(px - half), round(py - half)),
                        special_flags=pg.BLEND_PREMULTIPLIED)  # fmt: skip


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

    def update(self, dt: float) -> None:
        self.strands.update(dt)
        if self.floaters is not None:
            self.floaters.update(dt)

    # --- drawing -----------------------------------------------------------------------------
    def draw(self, canvas: pg.Surface, clock: float) -> None:
        canvas.blit(self.bg, (0, 0))
        self._draw_stars(canvas, clock)
        if self.sun is not None:
            self._draw_sun(canvas, clock)
        self._draw_grid(canvas, clock)
        layer = self.layer
        layer.fill((0, 0, 0))
        self._draw_strands(layer, clock)
        canvas.blit(layer, (0, self.layer_top), special_flags=pg.BLEND_RGB_ADD)
        if self.floaters is not None:  # over the ribbons: their light added over a ball dims it
            self.floaters.draw(canvas)

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

    def _draw_strands(self, layer: pg.Surface, clock: float) -> None:
        v, st = self.v, self.strands
        top = self.layer_top
        xs = st.x * v.s + v.ox
        light = st.glow_at(clock)
        chunks = 9
        n = len(xs)
        edges = np.linspace(0, n - 1, chunks + 1).astype(int)
        glow_w, mid_w, core_w = v.i(7 * C.LOOK.reach), max(1, v.i(3)), max(1, v.i(1.4))
        for i in range(STRANDS):
            u = i / (STRANDS - 1)
            base = C.lerp(C.CYAN, C.MAGENTA, u)
            spread = (i - (STRANDS - 1) / 2) * 3.0  # the strands lie side by side, then braid
            ys = (st.base_y + spread + st.y[i] * (0.7 + 0.3 * u)) * v.s + v.oy - top
            pts = np.column_stack((xs, ys)).tolist()
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
