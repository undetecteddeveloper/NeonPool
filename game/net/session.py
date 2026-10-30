"""One machine's side of a two-player game: handshake, coin toss, turns, checkpoints. Pure.

Both machines run the same simulation (same seed, same quantised shots), so a shot is sent as a
few bytes, never as ball positions. The HOST (player 0) is the referee: it alone judges a shot,
and sends the table and the verdict as a checkpoint; the guest (player 1) shoots at once on its
own copy (the simulation is deterministic) and sends the shot as a request the host may refuse.
Whatever the guest has simulated is replaced by the checkpoint, and a ball more than
`NET_DESYNC_M` off is counted in `desyncs`. docs/ARCHITECTURE.md, section on network play.

Everything that changes the table (a shot ordered by the host, a checkpoint, a ball placed) waits
in the inbox until this machine's own balls have stopped, so the order of events is the same on
both machines however late a packet is.
"""

from __future__ import annotations

import logging
import math
import random
import secrets
from collections import deque

from game import config
from game.net import protocol as p
from game.net.remote_cue import RemoteCue
from game.net.transport import Transport
from game.physics import Event, Shot, World
from game.physics.world import CUE
from game.rules.eight_ball import RERACK
from game.rules.two_player import Match, MatchShot

log = logging.getLogger("neonpool")

HANDSHAKE, PLAYING, CLOSED = "handshake", "playing", "closed"  # Session.phase
HOST, GUEST = 0, 1  # the two players; the host is the referee
# Session.close_reason
CLOSE_VERSION = "version"  # the two builds differ: one must update
CLOSE_BUSY = "busy"  # the room was full
CLOSE_LEFT = "left"  # the other player went away on purpose
CLOSE_SELF = "self"  # this player went away
CLOSE_LOST = "lost"  # the connection broke
CLOSE_TIMEOUT = "timeout"  # the other side said nothing in time
PING_EVERY_S = 1.0


def capture_balls(world: World) -> tuple[p.BallPos, ...]:
    return tuple(
        p.BallPos(b.in_play, -1 if b.pocket is None else b.pocket, b.x, b.y) for b in world.balls
    )


def paste_balls(
    world: World, balls: tuple[p.BallPos, ...], skip: frozenset[int] = frozenset()
) -> float:
    """Put every ball (stopped) where the referee has it. Returns the farthest any ball had to
    move (infinity if a ball was on the table here and not there, or the other way round); the
    balls in `skip` are put right but not measured (the referee moved them by the rules)."""
    worst = 0.0
    for n, (ball, pos) in enumerate(zip(world.balls, balls, strict=True)):
        if n in skip:
            pass
        elif ball.in_play != pos.in_play:
            worst = math.inf
        elif pos.in_play:
            worst = max(worst, math.hypot(ball.x - pos.x, ball.y - pos.y))
        ball.x, ball.y, ball.in_play = pos.x, pos.y, pos.in_play
        ball.vx = ball.vy = ball.qx = ball.qy = 0.0
        ball.pocket = None if pos.pocket < 0 else pos.pocket
    return worst


class Session:
    def __init__(
        self,
        transport: Transport,
        host: bool,
        name: str,
        *,
        rng: random.Random | None = None,
        feel: str = config.DEFAULT_FEEL,
        spin: str = config.DEFAULT_SPIN,
        build: str = config.GAME_VERSION,
        fingerprint: int | None = None,
    ) -> None:
        self.transport = transport
        self.me = HOST if host else GUEST
        self.name = p.clean_name(name)
        self.names = ["", ""]
        self.names[self.me] = self.name
        self.phase = HANDSHAKE
        self.close_reason: str | None = None
        self.world: World | None = None
        self.match: Match | None = None
        self.breaker: int | None = None  # who breaks: the coin toss, told to both
        self.token = 0  # the key to this room, made by the host and given to the guest in WELCOME
        self.seq = 0  # the number of the last shot started
        self.remote_cue = RemoteCue()
        self.emotes: list[int] = []
        # what is worth knowing about how the game is going (the screens and the tests read these)
        self.desyncs = 0  # checkpoints whose table differed from the local one by > NET_DESYNC_M
        self.max_desync_m = 0.0  # ... and the worst difference seen (m)
        self.checkpoints = 0  # judged shots/turns taken from the referee (guest) or sent (host)
        self.bad_frames = 0  # frames that were not messages of this protocol
        self.rejected_shots = 0  # shots refused (host: requests it refused; guest: its own)
        self.rtt_s: float | None = None
        self.shots_started = 0  # shots begun on this machine's table (either player's)
        self.last_shot: Shot | None = None  # the latest, as simulated
        self.last_shooter: int | None = None
        self.time = 0.0
        self._rng, self._feel, self._spin = rng, feel, spin
        self._build = build
        self._fingerprint = p.physics_fingerprint() if fingerprint is None else fingerprint
        self._acc = 0.0
        self._silent = 0.0
        self._toss_left = 0.0  # the coin is still in the air: no clock yet
        self._turn_used = 0.0  # seconds of the clock spent on the shot being waited for
        self._timeout_sent = False  # (guest) our clock ran out and the host has been told
        self._live = False  # a shot is rolling here
        self._inbox: deque = deque()
        self._judged: list[MatchShot] = []
        self._resync_due = False
        self._aim_want = self._aim_sent = (p.AIM_HIDDEN, 0, 0)
        self._aim_n = 0
        self._aim_at = -1.0
        self._place_want: tuple[int, int] | None = None
        self._place_at = -1.0
        self._ping_at = 0.0
        self._ping_token = 0
        self._ping_sent: dict[int, float] = {}
        if not host:
            hello = p.Hello(p.PROTOCOL_VERSION, self._build, self._fingerprint, self.name)
            self._send(hello)

    # --- what the screens ask ---
    @property
    def playing(self) -> bool:
        return self.phase == PLAYING

    @property
    def my_turn(self) -> bool:
        return self.playing and self.match.turn == self.me and not self.match.over

    @property
    def settled(self) -> bool:
        """Nothing is rolling or waiting here: every ball has stopped and the inbox is empty."""
        return self.playing and self.world.at_rest() and not self._live and not self._inbox

    @property
    def can_shoot(self) -> bool:
        return (
            self.my_turn and self.settled and not self._timeout_sent and not self.match.cue_in_hand
        )

    @property
    def can_place(self) -> bool:
        return self.my_turn and self.settled and not self._timeout_sent and self.match.cue_in_hand

    @property
    def clock_running(self) -> bool:
        """The clock of the player on turn is counting: the toss is over and every ball is still."""
        return self.playing and not self.match.over and self._toss_left <= 0 and self.settled

    @property
    def turn_left_s(self) -> float:
        """Seconds the player on turn has left for this shot."""
        return max(0.0, config.NET_TURN_S - self._turn_used)

    def take_judged(self) -> list[MatchShot]:
        """The shots (and lost turns) judged since the last call, in order."""
        out, self._judged = self._judged, []
        return out

    # --- what the player does ---
    def shoot(self, shot: Shot) -> Shot | None:
        """Take a shot on turn. Returns the shot as it is simulated on both machines (the one the
        screen should show), or None if a shot is not allowed now."""
        if not self.can_shoot:
            return None
        msg = p.ShotMsg.from_shot((self.seq + 1) & 0xFFFF, shot)
        self._send(msg)  # guest to host: a request; host to guest: the order to play it
        self._start_shot(msg)
        return msg.to_shot()

    def set_aim(self, state: int, angle: float = 0.0, pull_px: float = 0.0) -> None:
        """Where my cue is now (called every frame; sent at most NET_AIM_HZ times a second)."""
        if state == p.AIM_HIDDEN or not self.can_shoot:
            self._aim_want = (p.AIM_HIDDEN, 0, 0)
        else:
            pull = p.quantize_pull(pull_px) if state == p.AIM_PULLING else 0
            self._aim_want = (state, p.quantize_angle(angle), pull)

    def place_cue(self, x: float, y: float) -> bool:
        """Move the cue ball in hand to (x, y) metres (millimetres on the wire). False: not
        allowed there, the ball stays where it was."""
        if not self.can_place:
            return False
        mm = (round(x * 1000), round(y * 1000))
        if not 0 <= mm[0] < 65536 or not 0 <= mm[1] < 65536:
            return False
        if not self.world.place_cue(mm[0] / 1000, mm[1] / 1000):
            return False
        self._place_want = mm
        return True

    def release_cue(self) -> None:
        """Let go of the cue ball in hand: it stays where it is, and the game goes on."""
        if not self.can_place:
            return
        cue = self.world.balls[CUE]
        self._send(p.Place(round(cue.x * 1000), round(cue.y * 1000), True))
        self._place_want = None
        self.match.cue_placed()

    def timeout_turn(self) -> bool:
        """(Referee) the clock of the player on turn ran out: the turn passes."""
        if self.me != HOST or not self.settled or self.match.over:
            return False
        self._judged.append(self.match.timeout())
        self._send_checkpoint(p.CHECK_TIMEOUT)
        return True

    def reset_table(self, where: dict[int, tuple[float, float]]) -> None:
        """(Referee) put some balls by hand, stopped, and tell the other machine. For set-ups
        (the scripted games of the tests and of the smoke run), not for play."""
        if self.me != HOST or not self.settled:
            raise ValueError("only the referee, with every ball stopped, may set the table")
        for number, (x, y) in where.items():
            self.world.place(number, x, y)
        self._send_checkpoint(p.CHECK_RESYNC)

    def send_emote(self, code: int) -> None:
        if self.playing:
            self._send(p.Emote(code))

    def leave(self) -> None:
        if self.phase != CLOSED:
            self._send(p.Bye(p.BYE_LEAVE))
            self._close(CLOSE_SELF)

    # --- one frame of time ---
    def update(self, dt: float) -> list[Event]:
        """Read the network, run the simulation by `dt`, send what is due. Returns the physics
        events of this step (for sound and light). Never waits."""
        self.time += dt
        if self.phase == CLOSED:
            return []
        self._pump()
        if self.phase != CLOSED and not self.transport.connected:
            self._close(CLOSE_LOST)
        if self.phase == CLOSED:
            return []
        self._silent += dt
        if self.phase == HANDSHAKE:
            if self._silent > config.NET_HANDSHAKE_TIMEOUT_S:
                self._close(CLOSE_TIMEOUT)
            return []
        self._drain_inbox()
        events = self._advance_world(dt)
        self._drain_inbox()
        self._tick_clock(dt)
        self.remote_cue.update(dt)
        self._send_due()
        return events

    def _tick_clock(self, dt: float) -> None:
        if self._toss_left > 0:
            self._toss_left -= dt
        elif self.clock_running:
            self._turn_used += dt
            if self.me == HOST:  # the referee calls time (the guest gets a moment longer: its shot
                late = (
                    config.NET_TURN_GRACE_S if self.match.turn == GUEST else 0.0
                )  # is in the post)
                if self._turn_used >= config.NET_TURN_S + late:
                    self.timeout_turn()
            elif (
                self.match.turn == GUEST
                and self._turn_used >= config.NET_TURN_S
                and not self._timeout_sent
            ):
                self._timeout_sent = True  # our clock ran out: say so; the host decides
                self._send(p.TurnTimeout(GUEST))

    def _restart_clock(self) -> None:
        self._turn_used, self._timeout_sent = 0.0, False

    # --- receiving ---
    def _pump(self) -> None:
        for frame in self.transport.poll():
            try:
                msg = p.decode(frame)
            except p.ProtocolError as exc:
                self.bad_frames += 1
                log.warning("net: dropped a frame (%s)", exc)
                continue
            self._silent = 0.0
            self._handle(msg)
            if self.phase == CLOSED:
                break

    def _handle(self, msg: p.Message) -> None:
        if isinstance(msg, p.Bye):
            self._close(CLOSE_LEFT)
        elif isinstance(msg, p.Ping):
            self._send(p.Pong(msg.token))
        elif isinstance(msg, p.Pong):
            sent = self._ping_sent.pop(msg.token, None)
            if sent is not None:
                rtt = self.time - sent
                self.rtt_s = rtt if self.rtt_s is None else self.rtt_s * 0.7 + rtt * 0.3
        elif self.phase == HANDSHAKE:
            self._handle_handshake(msg)
        elif isinstance(msg, p.Aim):
            if self.match.turn != self.me:  # only the player on turn has a cue to show
                self.remote_cue.receive(msg)
        elif isinstance(msg, p.ShotMsg):
            if self.me == HOST:
                self._host_receives_shot(msg)
            else:
                self._inbox.append(msg)
        elif isinstance(msg, p.Checkpoint | p.Place):
            if self.me == GUEST or isinstance(msg, p.Place):
                self._inbox.append(msg)
        elif isinstance(msg, p.ShotReject):
            self.rejected_shots += 1
        elif isinstance(msg, p.TurnTimeout):
            if self.me == HOST and msg.player == self.match.turn == GUEST:
                self.timeout_turn()
        elif isinstance(msg, p.Emote):
            self.emotes.append(msg.code)

    def _handle_handshake(self, msg: p.Message) -> None:
        if self.me == HOST and isinstance(msg, p.Hello):
            ours = (p.PROTOCOL_VERSION, self._build, self._fingerprint)
            if (msg.proto, msg.build, msg.fingerprint) != ours:
                self._send(p.Reject(p.REJECT_VERSION))
                self._close(CLOSE_VERSION)
                return
            self.names[GUEST] = p.clean_name(msg.name)
            seed = self._rng.getrandbits(32) if self._rng else secrets.randbits(32)
            breaker = self._rng.randrange(2) if self._rng else secrets.randbelow(2)
            self.token = self._rng.getrandbits(32) if self._rng else secrets.randbits(32)
            self._send(p.Welcome(self.name, self.token))
            self._send(p.Start(seed, breaker, self._feel, self._spin))
            self._begin(seed, breaker, self._feel, self._spin)
        elif self.me == GUEST and isinstance(msg, p.Welcome):
            self.names[HOST], self.token = p.clean_name(msg.name), msg.token
        elif self.me == GUEST and isinstance(msg, p.Reject):
            self._close(CLOSE_BUSY if msg.reason == p.REJECT_BUSY else CLOSE_VERSION)
        elif self.me == GUEST and isinstance(msg, p.Start):
            if msg.feel not in config.FEEL_SETS or msg.spin not in config.SPIN_SETS:
                self._send(p.Bye(p.BYE_VERSION))
                self._close(CLOSE_VERSION)
                return
            self._begin(msg.seed, msg.breaker, msg.feel, msg.spin)

    def _begin(self, seed: int, breaker: int, feel: str, spin: str) -> None:
        self.world = World(seed, config.FEEL_SETS[feel], True, config.SPIN_SETS[spin])
        self.match = Match(breaker)
        self.breaker = breaker
        self.phase = PLAYING
        self._toss_left = config.NET_COIN_S
        self._restart_clock()

    # --- the shot ---
    def _host_receives_shot(self, msg: p.ShotMsg) -> None:
        """(Referee) the guest asks to shoot: accept it, or say why not."""
        if self.match.over or self.match.turn != GUEST:
            reason = p.SHOT_NOT_YOUR_TURN
        elif msg.seq != (self.seq + 1) & 0xFFFF:
            reason = p.SHOT_BAD_SEQ
        elif self.match.cue_in_hand or not self.settled:
            reason = p.SHOT_NOT_READY
        else:
            self._start_shot(msg)
            return
        self.rejected_shots += 1
        self._send(p.ShotReject(msg.seq, reason))
        self._resync_due = True  # the guest has played the shot on its own copy: take it back

    def _start_shot(self, msg: p.ShotMsg) -> None:
        self.seq = msg.seq
        self.last_shot, self.last_shooter = msg.to_shot(), self.match.turn
        self.shots_started += 1
        self._restart_clock()
        self.world.apply(self.last_shot)
        self.match.on_shot()
        self._live = True
        self._acc = 0.0
        self._aim_want = (p.AIM_HIDDEN, 0, 0)
        self.remote_cue.state = p.AIM_HIDDEN

    def _advance_world(self, dt: float) -> list[Event]:
        events: list[Event] = []
        self._acc += min(dt, config.MAX_FRAME_DT)
        while self._acc >= config.PHYSICS_DT:
            self._acc -= config.PHYSICS_DT
            if self.world.at_rest():
                self._acc = 0.0
                break
            step = self.world.step()
            if step:
                self.match.on_events(step)
                events += step
        if self._live and self.me == HOST and self.world.at_rest():
            self._judge_shot()
        return events

    def _judge_shot(self) -> None:
        """(Referee) every ball has stopped: judge the shot and tell the other machine."""
        self._live = False
        res = self.match.finish_shot()
        if res.outcome == RERACK:
            self.world.rack()
            self.match.rerack()
        elif res.outcome is None and not self.world.balls[CUE].in_play:
            self.world.respawn_cue()  # the cue ball went in: it is back on the table, to be placed
        self._judged.append(res)
        self._send_checkpoint(p.CHECK_AFTER_SHOT)

    def _send_checkpoint(self, kind: int) -> None:
        cp = p.Checkpoint(self.seq, kind, capture_balls(self.world), self.match.snapshot())
        self._send(cp)
        self._resync_due = False
        self.checkpoints += 1
        self._restart_clock()

    def _drain_inbox(self) -> None:
        """Apply what is waiting, in order, while this machine's balls are still."""
        while self._inbox:
            msg = self._inbox[0]
            forced = isinstance(msg, p.Checkpoint) and msg.kind == p.CHECK_RESYNC
            if not (forced or self.world.at_rest()):
                break
            self._inbox.popleft()
            if isinstance(msg, p.ShotMsg):
                self._start_shot(msg)
            elif isinstance(msg, p.Checkpoint):
                self._take_checkpoint(msg)
            else:
                self._take_place(msg)

    def _take_checkpoint(self, cp: p.Checkpoint) -> None:
        """(Guest) the referee's table and verdict replace what was simulated here."""
        last = cp.state.last
        if last is not None and last.outcome == RERACK:  # the referee racked the balls again
            skip = frozenset(range(len(cp.balls)))
        elif not self.world.balls[CUE].in_play:  # ... or put the pocketed cue ball back
            skip = frozenset({CUE})
        else:
            skip = frozenset()
        off = paste_balls(self.world, cp.balls, skip)
        if cp.kind == p.CHECK_AFTER_SHOT:
            if off > config.NET_DESYNC_M:
                self.desyncs += 1
            self.max_desync_m = max(
                self.max_desync_m, off if math.isfinite(off) else config.TABLE_L
            )
        self.match.load(cp.state)
        self.seq = cp.seq
        self._live = False
        self._acc = 0.0
        self.checkpoints += 1
        self._restart_clock()
        if cp.kind != p.CHECK_RESYNC and cp.state.last is not None:
            self._judged.append(cp.state.last)

    def _take_place(self, msg: p.Place) -> None:
        """The other player moves, or lets go of, the cue ball they have in hand."""
        if self.match.turn == self.me or not self.match.cue_in_hand:
            return
        placed = self.world.place_cue(msg.x_mm / 1000, msg.y_mm / 1000)
        if msg.final:
            if placed:
                self.match.cue_placed()
            elif self.me == HOST:
                self._resync_due = True  # an illegal spot: the guest takes the table back

    # --- sending ---
    def _send(self, msg: p.Message, reliable: bool = True) -> None:
        self.transport.send(p.encode(msg), reliable)

    def _send_due(self) -> None:
        interval = 1.0 / config.NET_AIM_HZ
        if self._aim_want != self._aim_sent and self.time - self._aim_at >= interval:
            state, angle, pull = self._aim_want
            self._aim_n = (self._aim_n + 1) & 0xFF
            self._send(p.Aim(self._aim_n, state, angle, pull), reliable=False)
            self._aim_sent, self._aim_at = self._aim_want, self.time
        if self._place_want is not None and self.time - self._place_at >= interval:
            self._send(p.Place(*self._place_want, False), reliable=False)
            self._place_want, self._place_at = None, self.time
        if self._resync_due and self.settled:
            self._send_checkpoint(p.CHECK_RESYNC)
        if self.time - self._ping_at >= PING_EVERY_S:
            self._ping_at = self.time
            self._ping_token = (self._ping_token + 1) & 0xFFFFFFFF
            self._ping_sent = {self._ping_token: self.time}
            self._send(p.Ping(self._ping_token), reliable=False)

    def _close(self, reason: str) -> None:
        self.phase = CLOSED
        self.close_reason = reason
        self.transport.close()
