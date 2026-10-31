"""`tools/relay_ops.py`: the words it writes, where it finds the key, what it says when something
is missing. (The relay itself: test_net_ops.py.) AC29 of docs/plans/20261031-multiplayer-chang4.md.
"""

import time

import pytest

from server.local_relay import Relay
from tests.test_net_relay import joined, ready_room, wait
from tools import relay_ops as ops

BODY = {
    "day": "2026-10-31",
    "rooms": [
        {"code": "KXQM", "state": "playing", "age_s": 754, "rtt_ms": 48},
        {"code": "ABCD", "state": "waiting", "age_s": 9, "rtt_ms": None},
        {"code": "ZZZZ", "state": "host_away", "age_s": 3700, "rtt_ms": None},
    ],
    "today": {"rooms": 3, "joins": 2, "frames": 4210, "events": 9, "used_pct": 1.2},
    "log": [
        {"at": 1_000_000_000_000, "ev": "room_new", "code": "KXQM"},
        {"at": 1_000_000_060_000, "ev": "host_out", "code": "KXQM", "why": "host_link"},
        {"at": 1_000_000_120_000, "ev": "room_end", "code": "KXQM", "why": "expired"},
        {"at": 1_000_000_180_000, "ev": "from_the_future", "code": "ABCD", "why": "new_reason"},
    ],
}


@pytest.fixture(autouse=True)
def no_real_key(monkeypatch, tmp_path):
    """Never touch the owner's key: an empty folder and no variable unless a test sets one."""
    monkeypatch.delenv(ops.KEY_ENV, raising=False)
    monkeypatch.setenv("NEONPOOL_ADMIN_KEY_FILE", str(tmp_path / "relay-admin.key"))


def test_ac29_the_status_reads_as_rooms_numbers_and_a_log_with_reasons():
    text = ops.render_status(BODY, "wss://example")
    assert "ngày 2026-10-31" in text
    assert "3 phòng mới · 2 lượt vào · 4.210 khung tin · 1,2% mức miễn phí" in text
    assert "Đang có 3 phòng:" in text
    rows = {line.split()[0]: line for line in text.splitlines() if line.startswith("  ")}
    assert (
        "đang chơi" in rows["KXQM"] and "12 phút" in rows["KXQM"] and "ping 48 ms" in rows["KXQM"]
    )
    assert (
        "đang chờ khách" in rows["ABCD"]
        and "9 giây" in rows["ABCD"]
        and "ping -- ms" in rows["ABCD"]
    )
    assert "1 giờ 1 phút" in rows["ZZZZ"] and "chủ phòng đang nối lại" in rows["ZZZZ"]
    assert "phòng mới" in text and "chủ phòng mất kết nối — đường nối của chủ phòng đứt" in text
    assert "phòng đóng — chủ phòng mất kết nối quá 90 giây" in text
    assert "from_the_future — new_reason" in text  # (a word it does not know is shown as it is)


def test_ac29_an_empty_relay_says_so_without_breaking():
    empty = {"day": "2026-10-31", "rooms": [], "today": {}, "log": []}
    text = ops.render_status(empty)
    assert "Đang có 0 phòng." in text and "Nhật ký: trống." in text
    assert "0 phòng mới" in text


def test_ac29_health_says_well_near_the_limit_or_no_answer():
    assert ops.render_health(200, {"ok": True, "rooms": 2, "used_pct": 4.5}).startswith("KHOẺ: 2")
    near = ops.render_health(503, {"ok": False, "why": "near_limit", "used_pct": 93.0})
    assert "SẮP HẾT LƯỢT MIỄN PHÍ" in near and "93.0" in near
    assert ops.render_health(0, "timed out").startswith("KHÔNG TRẢ LỜI")
    assert ops.render_health(500, "boom").startswith("LỖI HTTP 500")


def test_ac29_the_key_comes_from_the_environment_then_the_file_else_none(monkeypatch, tmp_path):
    assert ops.read_key() is None
    ops.key_path().write_text("from-file\n", encoding="utf-8")
    assert ops.read_key() == "from-file"
    monkeypatch.setenv(ops.KEY_ENV, " from-env ")
    assert ops.read_key() == "from-env"


def test_ac29_without_a_key_status_says_what_to_do(capsys):
    assert ops.main(["--url", "ws://127.0.0.1:9", "status"]) == 1
    said = capsys.readouterr().out
    assert "THIẾU KHOÁ" in said and "relay_ops.py setup" in said


def test_ac29_status_against_a_real_relay_and_a_wrong_key(monkeypatch, capsys):
    server = Relay(guest_stale_s=0.5, admin_key="right-key")
    try:
        room = ready_room(server.url)
        joined(server.url, room)
        room._stat_at = -100.0
        room.report_rtt(0.031)
        monkeypatch.setenv(ops.KEY_ENV, "right-key")
        assert wait(lambda: server.rooms[room.code].rtt_ms == 31)
        assert ops.main(["--url", server.url, "status", "--log", "5"]) == 0
        said = capsys.readouterr().out
        assert room.code in said and "đang chơi" in said and "ping 31 ms" in said
        assert "khách vào" in said and "1 lượt vào" in said
        monkeypatch.setenv(ops.KEY_ENV, "wrong")
        assert ops.main(["--url", server.url, "status"]) == 1
        assert "KHOÁ BỊ TỪ CHỐI" in capsys.readouterr().out
        room.close()
    finally:
        server.close()


def test_ac29_status_with_no_relay_answering_and_an_old_relay(monkeypatch, capsys):
    monkeypatch.setenv(ops.KEY_ENV, "k")
    assert ops.main(["--url", "ws://127.0.0.1:9", "status"]) == 1
    assert "KHÔNG TRẢ LỜI" in capsys.readouterr().out
    old = Relay()  # (no admin key set: also what a relay from before Chặng 4 answers, 404 aside)
    try:
        assert ops.main(["--url", old.url, "status"]) == 1
        assert "KHOÁ BỊ TỪ CHỐI" in capsys.readouterr().out
    finally:
        old.close()


def test_ac29_age_and_count_words():
    assert [ops._age(s) for s in (0, 59, 60, 3599, 3600, 7384)] == [
        "0 giây",
        "59 giây",
        "1 phút",
        "59 phút",
        "1 giờ 0 phút",
        "2 giờ 3 phút",
    ]
    assert ops._count(1234567) == "1.234.567" and ops._count(7) == "7"
    assert time.strftime("%Y", time.localtime(1_000_000_000)) == "2001"  # (the sample dates)


def test_ac29_a_relay_from_before_this_stage_is_told_to_be_updated(monkeypatch, capsys):
    monkeypatch.setenv(ops.KEY_ENV, "k")
    monkeypatch.setattr(ops, "fetch", lambda *a, **k: (404, "no such thing\n"))
    assert ops.main(["--url", "ws://example", "status"]) == 1
    assert "relay_ops.py deploy" in capsys.readouterr().out
