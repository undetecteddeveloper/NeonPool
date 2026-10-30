"""Wire protocol of network play: framed binary messages and the quantised shot. Pure (no pygame).

A frame is `[length u16][type u8][payload]`, little-endian, `length` counting type + payload and
never more than MAX_FRAME. No pickle: every field is read with a bounds check, so a broken, cut
or foreign frame raises `ProtocolError` and nothing else. docs/ARCHITECTURE.md "Chơi mạng".
"""

from __future__ import annotations

import math
import struct
import zlib
from dataclasses import dataclass
from typing import ClassVar, NamedTuple

from game import config
from game.physics.shot import Shot
from game.physics.world import N_BALLS
from game.rules.two_player import FOULS, GROUPS, OUTCOMES, REASONS, MatchShot, MatchState

PROTOCOL_VERSION = 1
MAX_FRAME = 1024  # bytes of type + payload; a checkpoint is ~330
_LEN = struct.Struct("<H")

REJECT_VERSION = 1  # the two builds differ: one must update
REJECT_BUSY = 2  # the room already has its two players
SHOT_NOT_YOUR_TURN = 1
SHOT_BAD_SEQ = 2
SHOT_NOT_READY = 3  # balls still moving, game over, or the cue ball is still in hand
CHECK_AFTER_SHOT = 0  # the referee judged a shot
CHECK_RESYNC = 1  # a shot was refused (or the table was set by hand): take the referee's table
CHECK_TIMEOUT = 2  # the turn was lost to the clock
BYE_LEAVE = 1
BYE_VERSION = 2
AIM_HIDDEN, AIM_RESTING, AIM_PULLING = 0, 1, 2

ANGLE_STEPS = 1 << 16
SPIN_STEPS = 32  # the spin dial moves in steps of 1/32 (play.py `_set_spin`): exact on the wire
_TAU = 2 * math.pi


class ProtocolError(ValueError):
    """A frame that cannot be a message of this protocol (broken, cut, foreign, out of range)."""


# --- quantising: what the wire can say is what BOTH machines simulate ----------------------------
def quantize_angle(angle: float) -> int:
    return round((angle % _TAU) / _TAU * ANGLE_STEPS) % ANGLE_STEPS


def dequantize_angle(q: int) -> float:
    return q * _TAU / ANGLE_STEPS


def quantize_pull(px: float) -> int:
    """The length of the pull on the cue (logical px, 0..MAX_DRAG_PX) as 0..255."""
    return round(max(0.0, min(px, config.MAX_DRAG_PX)) / config.MAX_DRAG_PX * 255)


def dequantize_pull(q: int) -> float:
    return q / 255 * config.MAX_DRAG_PX


def snap_shot(shot: Shot) -> Shot:
    """The shot as the wire carries it. Whoever shoots simulates THIS, never the raw shot."""
    return ShotMsg.from_shot(0, shot).to_shot()


def physics_fingerprint() -> int:
    """A number that changes with any constant that can change a shot's result. Two machines whose
    numbers differ would drift apart mid-game, so they refuse each other at the door."""
    c = config
    parts = (
        (c.TABLE_L, c.TABLE_W, c.BALL_R, c.POCKETS, c.HEAD_SPOT, c.FOOT_SPOT, c.RACK_GAP),
        (c.ROW_STEP, c.RACK_ORDER, c.PHYSICS_DT, c.MAX_STEP_FRAC, c.REST_SPEED),
        (c.MIN_EVENT_SPEED, c.FEEL_SETS, c.SPIN_SETS, c.SLIDE_GAIN, c.SPIN_MAX_RATIO),
    )
    return zlib.crc32(repr(parts).encode("utf-8"))


def clean_name(name: str) -> str:
    """A player name fit for the wire and the screen: printable, trimmed, not too long."""
    return "".join(ch for ch in name if ch.isprintable()).strip()[: config.NET_NAME_MAX]


# --- reading and writing -------------------------------------------------------------------------
class _Reader:
    def __init__(self, data: bytes) -> None:
        self._data, self._i = data, 0

    def take(self, fmt: str) -> tuple:
        st = struct.Struct("<" + fmt)
        if self._i + st.size > len(self._data):
            raise ProtocolError("message cut short")
        values = st.unpack_from(self._data, self._i)
        self._i += st.size
        return values

    def u8(self) -> int:
        return self.take("B")[0]

    def u16(self) -> int:
        return self.take("H")[0]

    def i8(self) -> int:
        return self.take("b")[0]

    def u32(self) -> int:
        return self.take("I")[0]

    def f64(self) -> float:
        value = self.take("d")[0]
        if not math.isfinite(value):
            raise ProtocolError("number is not finite")
        return value

    def text(self) -> str:
        n = self.u8()
        if self._i + n > len(self._data):
            raise ProtocolError("text cut short")
        raw = self._data[self._i : self._i + n]
        self._i += n
        try:
            return raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ProtocolError("text is not UTF-8") from exc

    def flag(self) -> bool:
        v = self.u8()
        if v > 1:
            raise ProtocolError("flag out of range")
        return bool(v)

    def choice(self, limit: int) -> int:
        v = self.u8()
        if v >= limit:
            raise ProtocolError("value out of range")
        return v

    def end(self) -> None:
        if self._i != len(self._data):
            raise ProtocolError("extra bytes after the message")


def _text(s: str) -> bytes:
    raw = s.encode("utf-8")
    if len(raw) > 255:
        raise ValueError("text too long for the wire")
    return bytes([len(raw)]) + raw


# --- messages ------------------------------------------------------------------------------------
@dataclass(frozen=True)
class Hello:
    """The guest knocks: build, physics fingerprint and name."""

    TYPE: ClassVar[int] = 1
    proto: int
    build: str
    fingerprint: int
    name: str

    def pack(self) -> bytes:
        return (
            struct.pack("<H", self.proto)
            + _text(self.build)
            + struct.pack("<I", self.fingerprint)
            + _text(self.name)
        )

    @classmethod
    def unpack(cls, r: _Reader) -> Hello:
        return cls(r.u16(), r.text(), r.u32(), r.text())


@dataclass(frozen=True)
class Welcome:
    TYPE: ClassVar[int] = 2
    name: str

    def pack(self) -> bytes:
        return _text(self.name)

    @classmethod
    def unpack(cls, r: _Reader) -> Welcome:
        return cls(r.text())


@dataclass(frozen=True)
class Reject:
    TYPE: ClassVar[int] = 3
    reason: int

    def pack(self) -> bytes:
        return bytes([self.reason])

    @classmethod
    def unpack(cls, r: _Reader) -> Reject:
        return cls(r.u8())


@dataclass(frozen=True)
class Start:
    """The host starts a game: the seed, who breaks, and the physics sets both machines use."""

    TYPE: ClassVar[int] = 4
    seed: int
    breaker: int
    feel: str
    spin: str

    def pack(self) -> bytes:
        return struct.pack("<IB", self.seed, self.breaker) + _text(self.feel) + _text(self.spin)

    @classmethod
    def unpack(cls, r: _Reader) -> Start:
        seed, breaker = r.u32(), r.choice(2)
        return cls(seed, breaker, r.text(), r.text())


@dataclass(frozen=True)
class Aim:
    """Where the sender's cue is: hidden, resting at an angle, or pulled back (not reliable)."""

    TYPE: ClassVar[int] = 16
    n: int  # counts up (wrapping at 256): a late packet is told from a new one
    state: int
    angle: int  # ANGLE_STEPS per turn
    pull: int  # 0..255 of MAX_DRAG_PX

    def pack(self) -> bytes:
        return struct.pack("<BBHB", self.n, self.state, self.angle, self.pull)

    @classmethod
    def unpack(cls, r: _Reader) -> Aim:
        return cls(r.u8(), r.choice(3), r.u16(), r.u8())


@dataclass(frozen=True)
class Place:
    """The cue ball in hand is at (x, y) millimetres; `final` once it is let go."""

    TYPE: ClassVar[int] = 17
    x_mm: int
    y_mm: int
    final: bool

    def pack(self) -> bytes:
        return struct.pack("<HHB", self.x_mm, self.y_mm, self.final)

    @classmethod
    def unpack(cls, r: _Reader) -> Place:
        return cls(r.u16(), r.u16(), r.flag())


@dataclass(frozen=True)
class ShotMsg:
    """A shot. Guest to host it is a request; host to guest it is the order to play it."""

    TYPE: ClassVar[int] = 32
    seq: int
    angle: int
    power: int
    spin: int  # in 1/SPIN_STEPS

    def pack(self) -> bytes:
        return struct.pack("<HHHb", self.seq, self.angle, self.power, self.spin)

    @classmethod
    def unpack(cls, r: _Reader) -> ShotMsg:
        seq, angle, power, spin = r.u16(), r.u16(), r.u16(), r.i8()
        if abs(spin) > SPIN_STEPS:
            raise ProtocolError("spin out of range")
        return cls(seq, angle, power, spin)

    @classmethod
    def from_shot(cls, seq: int, shot: Shot) -> ShotMsg:
        spin = max(-SPIN_STEPS, min(SPIN_STEPS, round(shot.spin * SPIN_STEPS)))
        return cls(seq, quantize_angle(shot.angle), round(shot.power * 65535), spin)

    def to_shot(self) -> Shot:
        return Shot(dequantize_angle(self.angle), self.power / 65535, self.spin / SPIN_STEPS)


@dataclass(frozen=True)
class ShotReject:
    TYPE: ClassVar[int] = 33
    seq: int
    reason: int

    def pack(self) -> bytes:
        return struct.pack("<HB", self.seq, self.reason)

    @classmethod
    def unpack(cls, r: _Reader) -> ShotReject:
        return cls(r.u16(), r.u8())


class BallPos(NamedTuple):
    """A ball in a checkpoint: exact, so both machines start the next shot from equal numbers."""

    in_play: bool
    pocket: int  # -1: not in a pocket
    x: float
    y: float


@dataclass(frozen=True)
class Checkpoint:
    """The referee's table after a shot (or after a refusal, or a lost turn)."""

    TYPE: ClassVar[int] = 34
    seq: int  # the number of the last shot played
    kind: int
    balls: tuple[BallPos, ...]
    state: MatchState

    def pack(self) -> bytes:
        if len(self.balls) != N_BALLS:
            raise ValueError("a checkpoint holds every ball")
        mask = sum(1 << n for n, b in enumerate(self.balls) if b.in_play)
        out = [struct.pack("<HBH", self.seq, self.kind, mask)]
        out += [struct.pack("<bdd", b.pocket, b.x, b.y) for b in self.balls]
        out.append(_pack_state(self.state))
        return b"".join(out)

    @classmethod
    def unpack(cls, r: _Reader) -> Checkpoint:
        seq, kind, mask = r.u16(), r.choice(3), r.u16()
        balls = []
        for n in range(N_BALLS):
            pocket, x, y = r.i8(), r.f64(), r.f64()
            if not -1 <= pocket < len(config.POCKETS):
                raise ProtocolError("pocket out of range")
            balls.append(BallPos(bool(mask >> n & 1), pocket, x, y))
        return cls(seq, kind, tuple(balls), _unpack_state(r))


@dataclass(frozen=True)
class TurnTimeout:
    """The clock of the player on turn ran out (the clock itself comes in a later stage)."""

    TYPE: ClassVar[int] = 48
    player: int

    def pack(self) -> bytes:
        return bytes([self.player])

    @classmethod
    def unpack(cls, r: _Reader) -> TurnTimeout:
        return cls(r.choice(2))


@dataclass(frozen=True)
class Emote:
    """A ready-made reaction, sent as a code so each side shows it in its own language."""

    TYPE: ClassVar[int] = 49
    code: int

    def pack(self) -> bytes:
        return bytes([self.code])

    @classmethod
    def unpack(cls, r: _Reader) -> Emote:
        return cls(r.u8())


@dataclass(frozen=True)
class Ping:
    TYPE: ClassVar[int] = 64
    token: int

    def pack(self) -> bytes:
        return struct.pack("<I", self.token)

    @classmethod
    def unpack(cls, r: _Reader) -> Ping:
        return cls(r.u32())


@dataclass(frozen=True)
class Pong:
    TYPE: ClassVar[int] = 65
    token: int

    def pack(self) -> bytes:
        return struct.pack("<I", self.token)

    @classmethod
    def unpack(cls, r: _Reader) -> Pong:
        return cls(r.u32())


@dataclass(frozen=True)
class Bye:
    TYPE: ClassVar[int] = 80
    reason: int

    def pack(self) -> bytes:
        return bytes([self.reason])

    @classmethod
    def unpack(cls, r: _Reader) -> Bye:
        return cls(r.u8())


Message = (
    Hello
    | Welcome
    | Reject
    | Start
    | Aim
    | Place
    | ShotMsg
    | ShotReject
    | Checkpoint
    | TurnTimeout
    | Emote
    | Ping
    | Pong
    | Bye
)
MESSAGE_TYPES: dict[int, type] = {
    cls.TYPE: cls
    for cls in (
        Hello,
        Welcome,
        Reject,
        Start,
        Aim,
        Place,
        ShotMsg,
        ShotReject,
        Checkpoint,
        TurnTimeout,
        Emote,
        Ping,
        Pong,
        Bye,
    )
}


# --- the referee's state -------------------------------------------------------------------------
def _pack_state(s: MatchState) -> bytes:
    flags = s.cue_in_hand | s.over << 1 | s.is_break << 2 | (s.last is not None) << 3
    mask = sum(1 << n for n in s.pocketed)
    out = [
        struct.pack(
            "<BBBBbHHHHH",
            s.turn,
            GROUPS.index(s.groups[0]),
            GROUPS.index(s.groups[1]),
            flags,
            -1 if s.winner is None else s.winner,
            mask,
            *s.shots,
            *s.fouls,
        )
    ]
    if s.last is not None:
        last = s.last
        out.append(
            struct.pack(
                "<BBBBB",
                last.shooter,
                OUTCOMES.index(last.outcome),
                REASONS.index(last.reason),
                GROUPS.index(last.group),
                last.timed_out,
            )
        )
        out.append(bytes([len(last.fouls), *(FOULS.index(f) for f in last.fouls)]))
        out.append(bytes([len(last.pocketed), *last.pocketed]))
    return b"".join(out)


def _unpack_state(r: _Reader) -> MatchState:
    turn, g0, g1, flags, winner, mask, s0, s1, f0, f1 = r.take("BBBBbHHHHH")
    if turn > 1 or g0 > 2 or g1 > 2 or flags > 15 or not -1 <= winner <= 1 or mask & 1:
        raise ProtocolError("match state out of range")
    over = bool(flags >> 1 & 1)
    if over != (winner != -1):
        raise ProtocolError("match state contradicts itself")
    last = None
    if flags >> 3 & 1:
        shooter, outcome, reason, group = r.choice(2), r.choice(4), r.choice(3), r.choice(3)
        timed_out = r.flag()
        fouls = tuple(FOULS[r.choice(len(FOULS))] for _ in range(r.choice(len(FOULS) + 1)))
        pocketed = tuple(r.choice(16) for _ in range(r.choice(16)))
        last = MatchShot(
            shooter, fouls, pocketed, GROUPS[group], OUTCOMES[outcome], REASONS[reason], timed_out
        )
    return MatchState(
        turn=turn,
        groups=(GROUPS[g0], GROUPS[g1]),
        cue_in_hand=bool(flags & 1),
        over=over,
        winner=None if winner == -1 else winner,
        is_break=bool(flags >> 2 & 1),
        pocketed=frozenset(n for n in range(1, 16) if mask >> n & 1),
        shots=(s0, s1),
        fouls=(f0, f1),
        last=last,
    )


# --- frames --------------------------------------------------------------------------------------
def encode(msg: Message) -> bytes:
    """The whole frame (length included) for a message."""
    body = bytes([msg.TYPE]) + msg.pack()
    if len(body) > MAX_FRAME:
        raise ValueError("message too big for a frame")
    try:
        return _LEN.pack(len(body)) + body
    except struct.error as exc:  # cannot happen below MAX_FRAME; keeps the contract in one place
        raise ValueError(str(exc)) from exc


def decode(frame: bytes) -> Message:
    """The message in a whole frame, or `ProtocolError`."""
    if len(frame) < _LEN.size + 1:
        raise ProtocolError("frame too short")
    (n,) = _LEN.unpack_from(frame)
    if n != len(frame) - _LEN.size or not 1 <= n <= MAX_FRAME:
        raise ProtocolError("frame length does not match")
    cls = MESSAGE_TYPES.get(frame[_LEN.size])
    if cls is None:
        raise ProtocolError(f"unknown message type {frame[_LEN.size]}")
    reader = _Reader(frame[_LEN.size + 1 :])
    try:
        msg = cls.unpack(reader)
    except (struct.error, ValueError, IndexError) as exc:
        if isinstance(exc, ProtocolError):
            raise
        raise ProtocolError(f"bad {cls.__name__}: {exc}") from exc
    reader.end()
    return msg


class FrameReader:
    """Cuts a byte stream (TCP) into whole frames. A bad length means the stream is lost."""

    def __init__(self) -> None:
        self._buf = bytearray()

    def feed(self, data: bytes) -> list[bytes]:
        self._buf += data
        frames = []
        while len(self._buf) >= _LEN.size:
            (n,) = _LEN.unpack_from(self._buf)
            if not 1 <= n <= MAX_FRAME:
                raise ProtocolError(f"frame length {n} out of range")
            if len(self._buf) < _LEN.size + n:
                break
            frames.append(bytes(self._buf[: _LEN.size + n]))
            del self._buf[: _LEN.size + n]
        return frames
