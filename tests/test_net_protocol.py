"""The wire protocol (AC2: same shot through the wire gives the same table; AC3: round trips and
rejection of bad frames)."""

import random
import struct

import pytest

from game import config
from game.net import protocol as p
from game.physics import Shot, World
from game.rules.two_player import MatchShot, MatchState


def sample_state(last: bool = True) -> MatchState:
    return MatchState(
        turn=1,
        groups=("solid", "stripe"),
        cue_in_hand=True,
        over=False,
        winner=None,
        is_break=False,
        pocketed=frozenset({3, 8, 12}),
        shots=(4, 3),
        fouls=(1, 0),
        last=MatchShot(0, ("foul.scratch", "foul.no_cushion"), (3, 12), "solid", None, None)
        if last
        else None,
    )


def sample_balls() -> tuple[p.BallPos, ...]:
    return tuple(
        p.BallPos(n % 5 != 0, -1 if n % 5 else 2, 0.1 * n + 1e-9, 1.27 - 0.07 * n)
        for n in range(16)
    )


def samples() -> list:
    over = MatchState(
        0, ("solid", "stripe"), False, True, 1, False, frozenset(), (9, 8), (2, 3),
        MatchShot(0, (), (8,), None, "lost", "result.lost_early"),
    )  # fmt: skip
    return [
        p.Hello(p.PROTOCOL_VERSION, config.GAME_VERSION, p.physics_fingerprint(), "Lan Anh ✓"),
        p.Welcome("Bình"),
        p.Reject(p.REJECT_VERSION),
        p.Start(123456789, 1, "VUA", "VUA"),
        p.Aim(255, p.AIM_PULLING, 65535, 200),
        p.Place(2540, 1270, True),
        p.ShotMsg(65535, 12345, 65535, -32),
        p.ShotReject(7, p.SHOT_NOT_YOUR_TURN),
        p.Checkpoint(5, p.CHECK_AFTER_SHOT, sample_balls(), sample_state()),
        p.Checkpoint(6, p.CHECK_RESYNC, sample_balls(), sample_state(last=False)),
        p.Checkpoint(7, p.CHECK_TIMEOUT, sample_balls(), over),
        p.TurnTimeout(1),
        p.Emote(2),
        p.Ping(4_000_000_000),
        p.Pong(1),
        p.Bye(p.BYE_LEAVE),
    ]


# --- AC3: every message makes the round trip ----------------------------------------------------
def test_ac3_roundtrip_every_message():
    for msg in samples():
        frame = p.encode(msg)
        assert p.decode(frame) == msg, type(msg).__name__


def test_ac3_the_samples_cover_every_message_type():
    assert {type(m).TYPE for m in samples()} == set(p.MESSAGE_TYPES)


def test_a_frame_says_its_own_length_and_stays_small():
    for msg in samples():
        frame = p.encode(msg)
        assert struct.unpack_from("<H", frame)[0] == len(frame) - 2
        assert len(frame) - 2 <= p.MAX_FRAME
    assert len(p.encode(p.Checkpoint(1, 0, sample_balls(), sample_state()))) < 400


# --- AC3: bad frames are refused, politely ---
def test_ac3_corrupt_truncated_unknown_rejected():
    for msg in samples():
        frame = p.encode(msg)
        for cut in range(len(frame)):  # every shorter prefix
            with pytest.raises(p.ProtocolError):
                p.decode(frame[:cut])
        with pytest.raises(p.ProtocolError):  # one byte too many
            p.decode(frame + b"\x00")
    with pytest.raises(p.ProtocolError):  # a type nobody knows
        p.decode(struct.pack("<HB", 1, 200))
    with pytest.raises(p.ProtocolError):  # zero length
        p.decode(struct.pack("<H", 0))
    with pytest.raises(p.ProtocolError):  # longer than allowed
        p.decode(struct.pack("<H", p.MAX_FRAME + 1) + bytes(p.MAX_FRAME + 1))


def test_ac3_random_damage_never_raises_anything_but_protocolerror():
    rng = random.Random(1)
    for msg in samples():
        frame = bytearray(p.encode(msg))
        for _ in range(200):
            damaged = bytearray(frame)
            for _ in range(rng.randint(1, 4)):
                damaged[rng.randrange(len(damaged))] = rng.randrange(256)
            try:
                p.decode(bytes(damaged))
            except p.ProtocolError:
                pass  # the only complaint allowed; any other exception fails the test


@pytest.mark.parametrize(
    "frame",
    [
        struct.pack("<HBBBHB", 5, 16, 0, 3, 0, 0),  # aim state 3
        struct.pack("<HBHHHb", 7, 32, 1, 0, 0, 33),  # spin beyond the dial
        struct.pack("<HBBBHBB", 6, 4 + 0, 0, 0, 0, 0, 0),  # a Start cut short
        struct.pack("<HBB", 2, 17, 0) + b"",  # a Place cut short
        struct.pack("<HBHHB", 6, 17, 1, 1, 2),  # a flag that is neither 0 nor 1
        struct.pack("<HBBB", 3, 2, 3, 0xFF),  # a name whose length overruns the frame
        struct.pack("<HBBB", 3, 2, 1, 0xFF),  # a name that is not UTF-8
        struct.pack("<HBB", 2, 48, 2),  # a player that does not exist
    ],
)
def test_ac3_values_out_of_range_are_refused(frame):
    with pytest.raises(p.ProtocolError):
        p.decode(frame)


def test_ac3_a_checkpoint_with_a_bad_ball_or_state_is_refused():
    good = p.encode(p.Checkpoint(1, 0, sample_balls(), sample_state()))
    nan = bytearray(good)
    nan[2 + 1 + 5 + 1 : 2 + 1 + 5 + 9] = struct.pack("<d", float("nan"))  # ball 0's x
    with pytest.raises(p.ProtocolError):
        p.decode(bytes(nan))
    bad_pocket = bytearray(good)
    bad_pocket[2 + 1 + 5] = 99  # ball 0's pocket
    with pytest.raises(p.ProtocolError):
        p.decode(bytes(bad_pocket))
    contradictory = MatchState(
        0, (None, None), False, False, 1, True, frozenset(), (0, 0), (0, 0), None
    )
    with pytest.raises(p.ProtocolError):  # "not over" yet "winner 1"
        p.decode(p.encode(p.Checkpoint(1, 0, sample_balls(), contradictory)))


def test_the_frame_reader_cuts_a_stream_into_frames_however_it_arrives():
    frames = [p.encode(m) for m in samples()]
    stream = b"".join(frames)
    rng = random.Random(2)
    reader, got, i = p.FrameReader(), [], 0
    while i < len(stream):
        n = rng.randint(1, 37)
        got += reader.feed(stream[i : i + n])
        i += n
    assert got == frames


def test_the_frame_reader_gives_up_on_a_stream_with_a_wild_length():
    with pytest.raises(p.ProtocolError):
        p.FrameReader().feed(struct.pack("<H", 0) + b"abc")
    with pytest.raises(p.ProtocolError):
        p.FrameReader().feed(struct.pack("<H", p.MAX_FRAME + 1))


# --- the shot on the wire ------------------------------------------------------------------------
def test_quantising_keeps_a_shot_within_a_hair_of_the_original():
    rng = random.Random(3)
    for _ in range(500):
        shot = Shot(rng.uniform(-7, 7), rng.random(), rng.randint(-32, 32) / 32)
        snap = p.snap_shot(shot)
        turn = abs(
            (snap.angle - shot.angle + 3.141592653589793) % 6.283185307179586 - 3.141592653589793
        )
        assert turn < 1e-4 and abs(snap.power - shot.power) < 1e-4
        assert snap.spin == shot.spin  # the dial's steps are exact
        assert p.snap_shot(snap) == snap  # snapping twice changes nothing


def test_the_ends_of_the_ranges_survive_the_wire():
    for shot in (Shot(0.0, 0.0, -1.0), Shot(6.283, 1.0, 1.0), Shot(-3.1415, 0.5, 0.0)):
        assert p.decode(p.encode(p.ShotMsg.from_shot(9, shot))).to_shot() == p.snap_shot(shot)


def test_ac2_same_shot_same_seed_same_state_through_protocol():
    """The shooter plays the snapped shot, the other machine plays what came over the wire."""
    raw = Shot(0.123456789, 0.8123456, 0.5)  # a hard break with some follow
    mine = p.snap_shot(raw)
    theirs = p.decode(p.encode(p.ShotMsg.from_shot(1, raw))).to_shot()
    assert mine == theirs
    a, b = World(seed=7), World(seed=7)
    a.apply(mine)
    b.apply(theirs)
    steps = 0
    while not (a.at_rest() and b.at_rest()) and steps < 60 * 240:
        assert a.step() == b.step()
        steps += 1
    assert a.at_rest() and b.at_rest()
    for x, y in zip(a.balls, b.balls, strict=True):
        assert (x.x, x.y, x.vx, x.vy, x.in_play, x.pocket) == (
            y.x,
            y.y,
            y.vx,
            y.vy,
            y.in_play,
            y.pocket,
        )


def test_the_cue_pull_and_position_units_round_trip_closely():
    for px in (0, 1, 50, 219, 220, 500):
        assert abs(p.dequantize_pull(p.quantize_pull(px)) - min(px, config.MAX_DRAG_PX)) <= 0.5
    assert abs(p.dequantize_angle(p.quantize_angle(-1.0)) - (6.283185307179586 - 1.0)) < 1e-4


# --- the door: a build or physics that differs ---
def test_the_physics_fingerprint_is_stable_and_notices_a_changed_constant(monkeypatch):
    before = p.physics_fingerprint()
    assert before == p.physics_fingerprint()
    monkeypatch.setattr(config, "BALL_R", config.BALL_R * 1.001)
    assert p.physics_fingerprint() != before


def test_names_are_cleaned_for_the_wire():
    assert p.clean_name("  Lan\tAnh\n ") == "LanAnh"
    assert len(p.clean_name("x" * 100)) == config.NET_NAME_MAX
    assert p.clean_name("") == ""
