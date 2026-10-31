"""Watching the relay (Chặng 4): its status, the log with reasons, the day's numbers, the health
address and the ping the host reports. Brief: docs/plans/20261031-multiplayer-chang4.md.

By default the relay is `server/local_relay.py`. NEONPOOL_RELAY_TEST_URL + NEONPOOL_RELAY_TEST_KEY
point the same tests at another relay (the Cloudflare one under `wrangler dev --var ADMIN_KEY:...`);
the ones that need a short timer or a pretend clock are skipped there.
"""

import json
import os
import random
import time
import urllib.error
import urllib.request

import pytest

from game.net import protocol as p
from game.net import relay, tcp
from game.net import session as s
from server.local_relay import LOG_MAX, Relay
from tests.test_net_relay import drain, joined, ready_room, wait

OTHER = os.environ.get("NEONPOOL_RELAY_TEST_URL", "").rstrip("/")
OTHER_KEY = os.environ.get("NEONPOOL_RELAY_TEST_KEY", "")
local_only = pytest.mark.skipif(bool(OTHER), reason="needs the local relay's timers or clock")
KEY = "k3y-for-tests"


def fetch(url, path):
    """(HTTP status, parsed JSON or the text) of a plain request to the relay."""
    request = urllib.request.Request(
        f"{relay._http_base(url)}{path}", headers={"User-Agent": relay.USER_AGENT}
    )
    try:
        with urllib.request.urlopen(request, timeout=5) as r:
            status, text = r.status, r.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        status, text = exc.code, exc.read().decode("utf-8")
    try:
        return status, json.loads(text)
    except ValueError:
        return status, text


@pytest.fixture
def ops():
    """(url, key) of a relay that has an admin key."""
    if OTHER:
        if not OTHER_KEY:
            pytest.skip("NEONPOOL_RELAY_TEST_KEY is not set")
        yield OTHER, OTHER_KEY
        return
    server = Relay(guest_stale_s=0.5, admin_key=KEY)
    yield server.url, KEY
    server.close()


def status(ops, lines=200):
    url, key = ops
    code, body = fetch(url, f"/v1/status?key={key}&log={lines}")
    assert code == 200, body
    return body


def mine(body, code):
    return next((r for r in body["rooms"] if r["code"] == code), None)


def events(ops, code):
    return [(line["ev"], line.get("why")) for line in status(ops)["log"] if line["code"] == code]


# --- AC24: who is there ---
def test_ac24_status_lists_the_rooms_with_what_they_are_doing(ops):
    url, _ = ops
    room = ready_room(url)
    assert mine(status(ops), room.code)["state"] == "waiting"
    guest, host, _ = joined(url, room)
    assert wait(lambda: mine(status(ops), room.code)["state"] == "playing")
    assert mine(status(ops), room.code)["age_s"] >= 0
    room._closed = True  # (the host does not come back)
    room._ws.close()
    assert wait(lambda: mine(status(ops), room.code)["state"] == "host_away")
    guest.close()


def test_ac24_status_wants_the_key_and_tells_a_stranger_nothing(ops):
    url, key = ops
    for path in ("/v1/status", "/v1/status?key=", f"/v1/status?key={key}x", "/v1/status?key=nope"):
        code, body = fetch(url, path)
        assert code == 403 and body == "no\n", path
    assert fetch(url, f"/v1/status?key={key}")[0] == 200


@local_only
def test_ac24_a_relay_without_a_key_never_answers_status():
    server = Relay()
    try:
        for path in ("/v1/status", "/v1/status?key="):
            assert fetch(server.url, path)[0] == 403
    finally:
        server.close()


# --- AC25: the log, with reasons ---
def test_ac25_the_log_tells_what_happened_to_a_room_and_why(ops):
    url, _ = ops
    room = ready_room(url)
    guest, _, _ = joined(url, room)
    guest.close()
    assert wait(lambda: ("guest_out", "guest_link") in events(ops, room.code))
    guest2, _, _ = joined(url, room)
    room._ws.close()  # the host's link dies; the room's own thread takes the room back
    assert wait(lambda: ("host_back", None) in events(ops, room.code), 10.0)
    room.close()
    assert wait(lambda: ("room_end", "host_closed") in events(ops, room.code))
    assert events(ops, room.code) == [
        ("room_new", None),
        ("guest_in", None),
        ("guest_out", "guest_link"),
        ("guest_in", None),
        ("host_out", "host_link"),
        ("host_back", None),
        ("room_end", "host_closed"),
    ]
    assert not guest2.connected or wait(lambda: not guest2.connected)
    line = status(ops)["log"][-1]
    assert abs(line["at"] - time.time() * 1000) < 60_000 and set(line) <= {
        "at",
        "ev",
        "code",
        "why",
    }


def test_ac25_a_guest_that_went_silent_is_logged_as_replaced(ops):
    url, _ = ops
    room = ready_room(url)
    joined(url, room)
    time.sleep((0.5 if not OTHER else 4.0) + 0.6)
    joined(url, room)
    assert wait(lambda: ("guest_replaced", None) in events(ops, room.code))
    assert [e for e, _ in events(ops, room.code)][:4] == [
        "room_new",
        "guest_in",
        "guest_replaced",
        "guest_in",
    ]
    room.close()


@pytest.fixture
def local():
    """A local relay with short timers (host grace 1.5 s, stale guest 0.5 s, idle room 1 s)."""
    if OTHER:
        pytest.skip("needs the local relay")
    server = Relay(host_grace_s=1.5, guest_stale_s=0.5, room_idle_s=1.0, admin_key=KEY)
    yield server
    server.close()


@local_only
def test_ac25_an_idle_room_and_a_room_the_host_never_came_back_to_say_why_they_closed(local):
    idle = ready_room(local.url)
    assert wait(lambda: idle.state == relay.FAILED, 4.0)
    gone = ready_room(local.url)
    gone._closed = True
    gone._ws.close()
    assert wait(lambda: ("room_end", "expired") in local_events(local, gone.code), 5.0)
    assert ("room_end", "idle") in local_events(local, idle.code)
    assert [e for e, _ in local_events(local, gone.code)][:2] == ["room_new", "host_out"]


def local_events(server, code):
    return [(line["ev"], line.get("why")) for line in list(server.log) if line["code"] == code]


@local_only
def test_ac25_the_log_keeps_only_its_last_200_lines():
    server = Relay(admin_key=KEY)
    try:
        with server._lock:
            for i in range(LOG_MAX + 50):
                server._note("room_new", f"{i:04d}")
        body = fetch(server.url, f"/v1/status?key={KEY}&log=1000")[1]
        assert len(body["log"]) == LOG_MAX
        assert body["log"][0]["code"] == "0050" and body["log"][-1]["code"] == "0249"
        assert len(fetch(server.url, f"/v1/status?key={KEY}&log=5")[1]["log"]) == 5
        assert fetch(server.url, f"/v1/status?key={KEY}&log=0")[1]["log"] == []
    finally:
        server.close()


# --- AC26: the day's numbers and the health address ---
def test_ac26_the_day_counts_rooms_joins_and_frames(ops):
    url, _ = ops
    before = status(ops)["today"]
    room = ready_room(url)
    guest, host, _ = joined(url, room)
    for frame in [p.encode(p.Ping(i)) for i in range(40)]:
        guest.send(frame)
    assert len(drain(host, 40)) == 40
    guest.close()
    room.close()  # (the relay hears of the frames at the latest when the room ends)

    def gained():
        now = status(ops)["today"]
        return {k: now[k] - before[k] for k in ("rooms", "joins", "frames")}

    assert wait(lambda: gained()["frames"] >= 40, 8.0), gained()
    assert gained()["rooms"] == 1 and gained()["joins"] == 1
    assert status(ops)["today"]["used_pct"] >= 0.0


@local_only
def test_ac26_health_turns_to_503_when_the_free_share_is_nearly_used_and_the_day_rolls_over():
    now = [0.0]
    server = Relay(admin_key=KEY, daily_limit=10, clock=lambda: now[0])
    try:
        assert fetch(server.url, "/v1/health") == (200, {"ok": True, "rooms": 0, "used_pct": 0.0})
        room = ready_room(server.url)  # one event of ten
        code, body = fetch(server.url, "/v1/health")
        assert code == 200 and body["rooms"] == 1 and body["used_pct"] == 10.0
        guest, host, _ = joined(server.url, room)  # two events, 20 frames below make one more
        for frame in [p.encode(p.Ping(i)) for i in range(20)]:
            guest.send(frame)
        assert len(drain(host, 20)) == 20
        assert wait(lambda: fetch(server.url, "/v1/health")[1]["used_pct"] == 30.0)
        with server._lock:
            for i in range(6):
                server._note("room_new", f"{i:04d}")
        code, body = fetch(server.url, "/v1/health")
        assert (code, body["ok"], body["why"], body["used_pct"]) == (503, False, "near_limit", 90.0)
        today = fetch(server.url, f"/v1/status?key={KEY}")[1]
        assert today["day"] == "1970-01-01" and today["today"]["frames"] == 20
        now[0] = 2 * 86400.0  # two days later
        again = fetch(server.url, f"/v1/status?key={KEY}")[1]
        assert again["day"] == "1970-01-03"
        assert again["today"] == {"rooms": 0, "joins": 0, "frames": 0, "events": 0, "used_pct": 0.0}
        assert fetch(server.url, "/v1/health")[0] == 200
        guest.close()
        room.close()
    finally:
        server.close()


def test_ac26_health_needs_no_key(ops):
    url, _ = ops
    code, body = fetch(url, "/v1/health")
    assert code == 200 and body["ok"] is True and 0 <= body["used_pct"] < 90


# --- AC27: the ping the host reports ---
def test_ac27_the_hosts_ping_shows_in_the_status_only_while_a_guest_is_there(ops):
    url, _ = ops
    room = ready_room(url)
    room.report_rtt(0.05)  # (nobody to ping yet: the relay ignores it)
    assert mine(status(ops), room.code)["rtt_ms"] is None
    guest, host, _ = joined(url, room)
    assert mine(status(ops), room.code)["rtt_ms"] is None  # (a new guest: no news yet)
    room._stat_at = -100.0
    room.report_rtt(0.048)
    assert wait(lambda: mine(status(ops), room.code)["rtt_ms"] == 48)
    room.report_rtt(0.2)  # (too soon after the last one: not sent)
    time.sleep(0.3)
    assert mine(status(ops), room.code)["rtt_ms"] == 48
    room.report_rtt(None, now=1e9)  # (no ping measured yet: nothing to say)
    guest.close()
    assert wait(lambda: mine(status(ops), room.code)["rtt_ms"] is None)
    room.close()


def test_ac27_a_nonsense_ping_is_ignored(ops):
    url, _ = ops
    room = ready_room(url)
    joined(url, room)
    for rtt in ("fast", -3, 10**9, True, None, [1]):
        room._out.put(relay._note({"t": "stat", "rtt": rtt}), True)
    room._out.put("not json", True)
    room._out.put(relay._note({"t": "stat", "rtt": 12}), True)  # (one that is fine, after them)
    assert wait(lambda: mine(status(ops), room.code)["rtt_ms"] == 12)
    room.close()


def test_ac27_a_game_through_the_relay_reports_its_ping(ops):
    url, _ = ops
    room = ready_room(url)
    guest_t, host_t, j = joined(url, room)
    host = s.Session(host_t, True, "Hoa", rng=random.Random(2))
    guest = s.Session(guest_t, False, "Nam")

    def tick():
        host.update(0.02)
        guest.update(0.02)
        time.sleep(0.001)

    assert wait(lambda: (tick(), host.playing and guest.playing)[1], 10.0)
    host.set_relink(relay.HostRelink(room))
    room._stat_at = -100.0
    assert wait(lambda: (tick(), host.rtt_s is not None)[1], 10.0)
    seen = []
    assert wait(lambda: (tick(), seen.append(mine(status(ops), room.code)["rtt_ms"]), seen[-1])[2])
    assert seen[-1] == pytest.approx(host.rtt_s * 1000, abs=300)
    guest.leave()
    assert tcp.CONNECT_OK == j.state
    room.close()
