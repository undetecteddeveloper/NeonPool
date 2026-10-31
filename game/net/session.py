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
from game.net import toss
from game.net.remote_cue import RemoteCue
from game.net.transport import Relinker, Transport
from game.physics import Event, Shot, World
from game.physics.world import CUE
from game.rules.eight_ball import RERACK
from game.rules.two_player import LOST_DROPPED, LOST_SURRENDER, Match, MatchShot

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
EMOTE_QUEUE = 8  # reactions waiting for the screen: more than this are dropped


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
        relink: Relinker | None = None,
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
        self.game_no = 0  # which game of the room this is (1, 2, ...): a rematch makes a new one
        self.wins = [0, 0]  # games won in this room, by player (both machines count alike)
        self.prev_winner: int | None = None  # who won the game before this one (a rematch only)
        self.rematch = [False, False]  # who has asked for another game (once this one is over)
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
        self.link_down_s: float | None = None  # None: the link is fine; else how long it is down
        self.link_losses = 0  # times the link broke ...
        self.rejoins = 0  # ... and times it was made again
        self._relink = relink
        self._pending: Transport | None = (
            None  # (host) a new connection that has not said who it is
        )
        self._pending_silent = 0.0
        self._resuming = False  # (guest) a new connection is made and has told the host who we are
        self._counted = False  # this game's winner is in `wins`
        self._emotes: list[tuple[int, int]] = []  # (player, code) waiting for the screen
        self._emote_at = -config.NET_EMOTE_GAP_S
        self._toss_left = 0.0  # the coin is still in the air: no clock yet
        self._turn_used = 0.0  # seconds of the clock spent on the shot being waited for
        self._timeout_sent = False  # (guest) our clock ran out and the host has been told
        self._live = False  # a shot is rolling here
        self._inbox: deque = deque()
        self._judged: list[MatchShot] = []
        self._resync_due = False
        self._aim_want = self._aim_sent = (p.AIM_HIDDEN, 0, 0, False)
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
    def linked(self) -> bool:
        """The link works. (A game whose link broke waits for it: see `link_down_s`.)"""
        return self.link_down_s is None

    def set_relink(self, relink: Relinker | None) -> None:
        """Where a new connection comes from if the link breaks in the middle of the game."""
        self._relink = relink

    @property
    def _free(self) -> bool:
        """The player on turn may act: every ball is still, the link works, and the coin has
        landed (the screens wait for it too; this holds for every other way in, a bot included)."""
        return (
            self.my_turn and self.settled and self.linked and not self._timeout_sent
            and self._toss_left <= 0
        )  # fmt: skip

    @property
    def can_shoot(self) -> bool:
        return self._free and not self.match.cue_in_hand

    @property
    def can_place(self) -> bool:
        return self._free and self.match.cue_in_hand

    @property
    def clock_running(self) -> bool:
        """The clock of the player on turn is counting: the toss is over, every ball is still and
        the link works."""
        return (
            self.playing and not self.match.over and self._toss_left <= 0
            and self.settled and self.linked
        )  # fmt: skip

    @property
    def turn_left_s(self) -> float:
        """Seconds the player on turn has left for this shot."""
        return max(0.0, config.NET_TURN_S - self._turn_used)

    @property
    def counted(self) -> bool:
        """The result of this game is already in `wins`."""
        return self._counted

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

    def set_aim(
        self, state: int, angle: float = 0.0, pull_px: float = 0.0, dialing: bool = False
    ) -> None:
        """Where my cue is now and whether I am working on the spin dial (called every frame;
        sent at most NET_AIM_HZ times a second)."""
        dial = dialing and self.can_shoot
        if state == p.AIM_HIDDEN or not self.can_shoot:
            self._aim_want = (p.AIM_HIDDEN, 0, 0, dial)
        else:
            pull = p.quantize_pull(pull_px) if state == p.AIM_PULLING else 0
            self._aim_want = (state, p.quantize_angle(angle), pull, dial)

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

    def surrender(self) -> bool:
        """Give the game up: it is lost, and the other player wins. (The guest asks the referee;
        the result comes back as a checkpoint.)"""
        if not self.playing or self.match.over:
            return False
        if self.me == HOST:
            self._end_game(HOST, LOST_SURRENDER)
        else:
            self._send(p.Surrender())
        return True

    def ask_rematch(self) -> bool:
        """Once the game is over: "again?". The next game starts when both players have asked,
        and nobody is made to hurry (there is no time limit on the other one's answer)."""
        if not self.playing or not self.match.over or self.rematch[self.me]:
            return False
        self.rematch[self.me] = True
        self._send(p.Rematch())
        self._maybe_restart()
        return True

    def send_emote(self, code: int) -> bool:
        """A ready-made reaction (a code, shown in the other's language); at most one per
        `NET_EMOTE_GAP_S`. It is also queued for our own screen."""
        if not self.playing or not 0 <= code < config.NET_EMOTES:
            return False
        if self.time - self._emote_at < config.NET_EMOTE_GAP_S:
            return False
        self._emote_at = self.time
        self._send(p.Emote(code))
        self._emotes.append((self.me, code))
        return True

    @property
    def emote_ready(self) -> bool:
        """A reaction may be sent now (one per `NET_EMOTE_GAP_S`)."""
        return self.playing and self.time - self._emote_at >= config.NET_EMOTE_GAP_S

    def take_emotes(self) -> list[tuple[int, int]]:
        """The reactions (player, code) sent by either player since the last call."""
        out, self._emotes = self._emotes, []
        return out

    def leave(self) -> None:
        """Walk out of the room. Doing that in the middle of a game loses it."""
        if self.phase == CLOSED:
            return
        if self.playing and not self.match.over:
            if self.me == HOST:
                self._end_game(HOST, LOST_SURRENDER)
            else:
                self._send(p.Surrender())
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
            if self.linked and self.phase == PLAYING and self._relink is not None:
                self._link_lost()
            elif self.linked:
                self._close(CLOSE_LOST)
            else:
                self._resuming = False  # (the new connection died before it was let in)
        if self.phase == CLOSED:
            return []
        self._silent += dt
        if self.phase == HANDSHAKE:
            if self._silent > config.NET_HANDSHAKE_TIMEOUT_S:
                self._close(CLOSE_TIMEOUT)
            return []
        if self.linked and self._relink is not None and self._silent > config.NET_SILENT_S:
            self._link_lost()  # (a link can die without a word: a cable out, a wifi that stopped)
        if not self.linked:
            return self._update_down(dt)
        self._drain_inbox()
        events = self._advance_world(dt)
        self._drain_inbox()
        self._tick_clock(dt)
        self._count_result()
        self.remote_cue.update(dt)
        self._send_due()
        return events

    # --- a broken link, and getting it back ---
    def _link_lost(self) -> None:
        """The link broke in the middle of the game. Wait for it (up to NET_REJOIN_S): the guest
        goes on trying to reconnect, the host goes on listening."""
        self.link_down_s = 0.0
        self.link_losses += 1
        self._resuming = False
        self._aim_want = (p.AIM_HIDDEN, 0, 0, False)
        self.remote_cue.hide()
        self.transport.close()
        log.info("net: the link is down; waiting for it")

    def _update_down(self, dt: float) -> list[Event]:
        """A frame while the link is down: the balls still rolling run to a stop (both machines
        do the same sums), nobody may shoot, the clock waits, and a new connection is looked for."""
        self.link_down_s += dt
        self._look_for_the_other(dt)
        if not self.linked and self.link_down_s >= config.NET_REJOIN_S:
            self._give_up_waiting()
            return []
        if not self.linked:
            self._drain_inbox()
            events = self._advance_world(dt)
            self.remote_cue.update(dt)
            return events
        return []

    def _look_for_the_other(self, dt: float) -> None:
        if self._relink is None:
            return
        fresh = self._relink.poll()
        if self.me == GUEST:
            if fresh is not None and not self._resuming:
                self.transport, self._resuming, self._silent = fresh, True, 0.0
                self._send(p.Resume(p.PROTOCOL_VERSION, self._build, self._fingerprint, self.token))
            elif fresh is not None:
                fresh.close()  # one try is being heard out; a second line would only get in its way
            elif self._resuming and self._silent > config.NET_HANDSHAKE_TIMEOUT_S:
                self.transport.close()  # no answer: this try is over, the next one starts
                self._resuming = False
            return
        if fresh is not None:  # (host) someone knocks: the newest knock is the one that counts
            if self._pending is not None:
                self._pending.close()
            self._pending, self._pending_silent = fresh, 0.0
        if self._pending is None:
            return
        self._pending_silent += dt
        for frame in self._pending.poll():
            try:
                msg = p.decode(frame)
            except p.ProtocolError:
                self.bad_frames += 1
                continue
            if isinstance(msg, p.Resume):
                self._host_takes_back(msg)
                return
        if self._pending_silent > config.NET_HANDSHAKE_TIMEOUT_S or not self._pending.connected:
            self._pending.close()
            self._pending = None

    def _host_takes_back(self, msg: p.Resume) -> None:
        """(Host) a new connection says it is the guest: the same builds and the room's key."""
        newcomer, self._pending = self._pending, None
        ours = (p.PROTOCOL_VERSION, self._build, self._fingerprint, self.token)
        if (msg.proto, msg.build, msg.fingerprint, msg.token) != ours:
            newcomer.send(p.encode(p.Reject(p.REJECT_BUSY)))
            newcomer.close()
            return
        self.transport = newcomer
        self._send(p.Welcome(self.name, self.token))
        self._link_up()

    def _link_up(self) -> None:
        """The link is back. The host puts the table and the verdicts right on both machines by
        sending its own (`CHECK_RESYNC`); whatever was waiting from before the break is dropped,
        since that word says it all."""
        self.link_down_s = None
        self.rejoins += 1
        self._resuming = False
        self._silent = 0.0
        self._inbox.clear()
        self._ping_sent.clear()
        self._ping_at = self.time - PING_EVERY_S
        self._aim_sent = (-1, 0, 0, False)
        if self.rematch[self.me]:
            self._send(p.Rematch())
        if self.me == HOST:
            self._resync_due = True
        log.info("net: the link is back")

    def _give_up_waiting(self) -> None:
        """NET_REJOIN_S went by. The host wins the game (the one who was gone loses it); the
        guest can only say the connection was lost."""
        if self.me == HOST and not self.match.over:
            self._end_game(GUEST, LOST_DROPPED)
        self._close(CLOSE_LOST)

    def _tick_clock(self, dt: float) -> None:
        if self._toss_left > 0:
            self._toss_left -= dt
        elif self.clock_running:
            self._turn_used += dt
            if self.me == HOST:
                # the referee calls time; the guest gets a moment longer, its shot is in the post
                late = config.NET_TURN_GRACE_S if self.match.turn == GUEST else 0.0
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

    def _count_result(self) -> None:
        if self.match.over and not self._counted:
            self._counted = True
            self.wins[self.match.winner] += 1

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
            self._take_final_word()
            self._close(CLOSE_LEFT)
        elif isinstance(msg, p.Ping):
            self._send(p.Pong(msg.token))
        elif isinstance(msg, p.Pong):
            sent = self._ping_sent.pop(msg.token, None)
            if sent is not None:
                rtt = self.time - sent
                self.rtt_s = rtt if self.rtt_s is None else self.rtt_s * 0.7 + rtt * 0.3
        elif isinstance(msg, p.Welcome) and self._resuming:
            self._link_up()
        elif isinstance(msg, p.Reject) and self._resuming:
            self.transport.close()  # not let in (yet): the next try is made soon
            self._resuming = False
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
            if msg.code < config.NET_EMOTES and len(self._emotes) < EMOTE_QUEUE:
                self._emotes.append((1 - self.me, msg.code))
        elif isinstance(msg, p.Surrender):
            if self.me == HOST and not self.match.over:
                self._end_game(GUEST, LOST_SURRENDER)
        elif isinstance(msg, p.Rematch):
            if self.match.over:
                self.rematch[1 - self.me] = True
                self._maybe_restart()
        elif isinstance(msg, p.Start):
            if self.me == GUEST and self.match.over:  # the host's word for the next game
                self._accept_start(msg)

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
            self._accept_start(msg)

    def _accept_start(self, msg: p.Start) -> None:
        if msg.feel not in config.FEEL_SETS or msg.spin not in config.SPIN_SETS:
            self._send(p.Bye(p.BYE_VERSION))
            self._close(CLOSE_VERSION)
            return
        self._begin(msg.seed, msg.breaker, msg.feel, msg.spin)

    def _begin(self, seed: int, breaker: int, feel: str, spin: str) -> None:
        """A game begins (the first one, or a rematch): a new table, a new coin."""
        self.prev_winner = None
        if self.match is not None:
            self._count_result()  # (the one that just ended counts, even if this came at once)
            self.prev_winner = self.match.winner if self.match.over else None
        self.world = World(seed, config.FEEL_SETS[feel], True, config.SPIN_SETS[spin])
        self.match = Match(breaker)
        self.breaker = breaker
        self.phase = PLAYING
        self.game_no += 1
        self.seq = 0
        self.rematch = [False, False]
        self._counted = False
        self._live = False
        self._acc = 0.0
        self._inbox.clear()
        self._judged.clear()
        self._resync_due = False
        self._aim_want = self._aim_sent = (p.AIM_HIDDEN, 0, 0, False)
        self._place_want = None
        self.remote_cue.hide()
        self._toss_left = toss.total_s(self.game_no > 1)
        self._restart_clock()

    def _maybe_restart(self) -> None:
        """(Referee) both players want another game: toss the coin again."""
        if self.me != HOST or not all(self.rematch):
            return
        seed = self._rng.getrandbits(32) if self._rng else secrets.randbits(32)
        breaker = self._rng.randrange(2) if self._rng else secrets.randbelow(2)
        self._send(p.Start(seed, breaker, self._feel, self._spin))
        self._begin(seed, breaker, self._feel, self._spin)

    def _end_game(self, loser: int, reason: str) -> None:
        """(Referee) the game ends without a last shot: `loser` gave it up, or was gone too long."""
        self._live = False
        for ball in self.world.balls:  # the table stops where it is, here and (by the
            ball.vx = ball.vy = ball.qx = ball.qy = 0.0  # checkpoint) on the other machine
        self._judged.append(self.match.surrender(loser, reason))
        self._count_result()
        self._send_checkpoint(p.CHECK_END)

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
        self._aim_want = (p.AIM_HIDDEN, 0, 0, False)
        self.remote_cue.hide()

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
            forced = isinstance(msg, p.Checkpoint) and msg.kind in (p.CHECK_RESYNC, p.CHECK_END)
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

    def _take_final_word(self) -> None:
        """The other side is leaving: what it said before saying goodbye (the end of a game it
        gave up) still counts, even though the balls here may not have stopped yet."""
        while self._inbox:
            msg = self._inbox.popleft()
            if isinstance(msg, p.Checkpoint) and msg.kind == p.CHECK_END:
                self._take_checkpoint(msg)

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
        if not self.linked:
            return
        interval = 1.0 / config.NET_AIM_HZ
        changed = self._aim_want != self._aim_sent
        again = self._aim_want[3] and self.time - self._aim_at >= config.NET_DIAL_KEEPALIVE_S
        if (changed or again) and self.time - self._aim_at >= interval:
            state, angle, pull, dial = self._aim_want
            self._aim_n = (self._aim_n + 1) & 0xFF
            self._send(p.Aim(self._aim_n, state, angle, pull, dial), reliable=False)
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
        if self._pending is not None:
            self._pending.close()
        if self._relink is not None:
            self._relink.close()
