"""The relay, on this machine: the same protocol as the real one (`server/cloudflare/`), for the
tests, the smoke run and the dev tool, so none of them need the internet.

    .venv\\Scripts\\python.exe -m server.local_relay [--port 47480]

then start the game with NEONPOOL_RELAY_URL=ws://127.0.0.1:47480. The protocol (v1) is written
down in docs/ARCHITECTURE.md (network play); tests/test_net_relay.py checks both relays against it.
The relay never reads a game frame: it hands out room codes and passes frames along.
"""

from __future__ import annotations

import argparse
import hmac
import json
import math
import secrets
import threading
import time
import urllib.parse
from collections import deque
from dataclasses import dataclass, field

from websockets.exceptions import ConnectionClosed
from websockets.sync.server import Server, ServerConnection, serve

from game.net import relay as r

HOST_GRACE_S = 90.0  # a host whose link broke has this long to take the room back
GUEST_STALE_S = 4.0  # a guest silent this long gives its place to whoever comes in
ROOM_IDLE_S = 30 * 60.0  # a room nobody has come into for this long is closed
TEXT_MAX = 512  # longest text message taken from a player
CLOSE_HOST_AWAY = 4000  # the guest's link is closed because the host's broke
LOG_MAX = 200  # lines of the log kept (the newest)
DAILY_LIMIT = 100_000  # requests a day on the free plan of the real relay (a frame message is 1/20)
HEALTH_LIMIT_PCT = 90.0  # `/v1/health` says "near_limit" (HTTP 503) from here
FRAMES_PER_REQUEST = 20
RTT_MAX_MS = 60_000


@dataclass
class Room:
    code: str
    key: str
    host: ServerConnection | None = None
    guest: ServerConnection | None = None
    lan: str = ""
    n: int = 0  # the number of the latest guest
    acked: int | None = None  # the host has heard of guest n: its frames may go to it
    guest_seen: float = 0.0
    host_away_at: float | None = None
    quiet_since: float = field(default_factory=time.monotonic)  # no guest since then
    born: float = field(default_factory=time.monotonic)
    rtt_ms: int | None = None  # the host's word on the ping between the two players


def _send(conn: ServerConnection | None, word) -> None:
    if conn is None:
        return
    try:
        conn.send(word if isinstance(word, bytes) else json.dumps(word))
    except (ConnectionClosed, OSError):
        pass


def _close(conn: ServerConnection | None, code: int = 1000) -> None:
    if conn is None:
        return
    threading.Thread(target=conn.close, args=(code,), daemon=True).start()  # (it waits)


class Relay:
    """A relay on `host`:`port` (0: any free port; `url` says where it ended up)."""

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 0,
        *,
        host_grace_s: float = HOST_GRACE_S,
        guest_stale_s: float = GUEST_STALE_S,
        room_idle_s: float = ROOM_IDLE_S,
        admin_key: str = "",
        daily_limit: int = DAILY_LIMIT,
        clock=time.time,
    ) -> None:
        self.host_grace_s, self.guest_stale_s, self.room_idle_s = (
            host_grace_s,
            guest_stale_s,
            room_idle_s,
        )
        self.admin_key, self.daily_limit, self._clock = admin_key, daily_limit, clock
        self.rooms: dict[str, Room] = {}
        self.log: deque[dict] = deque(maxlen=LOG_MAX)
        self._day = ""
        self._today = {"rooms": 0, "joins": 0, "frames": 0, "events": 0}
        self._lock = threading.Lock()
        self._server: Server = serve(
            self._handle,
            host,
            port,
            process_request=self._http,
            compression=None,
            max_size=4 * 1024,
        )
        self.port = self._server.socket.getsockname()[1]
        self.url = f"ws://{host}:{self.port}"
        self._open = True
        threading.Thread(target=self._server.serve_forever, name="relay", daemon=True).start()
        threading.Thread(target=self._janitor, name="relay-janitor", daemon=True).start()

    def close(self) -> None:
        self._open = False
        self._server.shutdown()

    # --- rooms ---
    def _room(self, code: str) -> Room | None:
        """The room, unless it has expired (call with the lock held)."""
        room = self.rooms.get(code)
        if room is not None and room.host_away_at is not None:
            if time.monotonic() - room.host_away_at > self.host_grace_s:
                del self.rooms[code]
                self._note("room_end", code, "expired")
                return None
        return room

    # --- the log and the day's numbers (call with the lock held) ---
    def _roll(self) -> None:
        day = time.strftime("%Y-%m-%d", time.gmtime(self._clock()))
        if day != self._day:
            self._day = day
            self._today = {"rooms": 0, "joins": 0, "frames": 0, "events": 0}

    def _note(self, ev: str, code: str, why: str | None = None) -> None:
        self._roll()
        line = {"at": int(self._clock() * 1000), "ev": ev, "code": code}
        if why is not None:
            line["why"] = why
        self.log.append(line)
        self._today["events"] += 1
        if ev == "room_new":
            self._today["rooms"] += 1
        elif ev == "guest_in":
            self._today["joins"] += 1

    def _count_frame(self) -> None:
        self._roll()
        self._today["frames"] += 1

    def _used_pct(self) -> float:
        used = math.ceil(self._today["frames"] / FRAMES_PER_REQUEST) + self._today["events"]
        return round(100.0 * used / self.daily_limit, 2)

    @staticmethod
    def _state(room: Room) -> str:
        if room.host is None:
            return "host_away"
        return "playing" if room.guest is not None else "waiting"

    def _health(self) -> tuple[int, dict]:
        self._roll()
        pct = self._used_pct()
        body = {"ok": pct < HEALTH_LIMIT_PCT, "rooms": len(self.rooms), "used_pct": pct}
        if not body["ok"]:
            body["why"] = "near_limit"
        return (200 if body["ok"] else 503), body

    def _status(self, lines: int) -> dict:
        self._roll()
        now = time.monotonic()
        rooms = [
            {
                "code": room.code,
                "state": self._state(room),
                "age_s": int(now - room.born),
                "rtt_ms": room.rtt_ms if room.guest is not None else None,
            }
            for room in self.rooms.values()
        ]
        return {
            "day": self._day,
            "rooms": rooms,
            "today": {**self._today, "used_pct": self._used_pct()},
            "log": list(self.log)[-lines:] if lines > 0 else [],
        }

    def _guest_fresh(self, room: Room) -> bool:
        return room.guest is not None and time.monotonic() - room.guest_seen <= self.guest_stale_s

    def _janitor(self) -> None:
        while self._open:
            time.sleep(0.25)
            with self._lock:
                now = time.monotonic()
                for code in list(self.rooms):
                    room = self._room(code)
                    if room is None or room.guest is not None or room.host is None:
                        continue
                    if now - room.quiet_since > self.room_idle_s:
                        del self.rooms[code]
                        self._note("room_end", code, "idle")
                        _send(room.host, {"t": "error", "why": r.ERR_IDLE})
                        _close(room.host)

    # --- plain requests ---
    def _http(self, conn: ServerConnection, request):
        url = urllib.parse.urlsplit(request.path)
        if (request.headers.get("User-Agent") or "").startswith("Python-urllib"):
            return conn.respond(403, "error code: 1010\n")  # (as Cloudflare does: its default name)
        if url.path == "/":
            return conn.respond(200, "neonpool relay 1\n")
        if url.path in (f"{r.API}/host", f"{r.API}/join"):
            return None  # a WebSocket: on to `_handle`
        query = {k: v[0] for k, v in urllib.parse.parse_qs(url.query).items()}
        if url.path == f"{r.API}/health":
            with self._lock:
                status, body = self._health()
            return self._json(conn, status, body)
        if url.path == f"{r.API}/status":
            given = query.get("key", "")
            if not self.admin_key or not hmac.compare_digest(given, self.admin_key):
                return conn.respond(403, "no\n")
            lines = int(query["log"]) if query.get("log", "").isdigit() else 20
            with self._lock:
                body = self._status(lines)
            return self._json(conn, 200, body)
        if url.path != f"{r.API}/look":
            return conn.respond(404, "no such thing\n")
        code = query.get("code", "")
        with self._lock:
            answer = self._look(code)
        return conn.respond(200, json.dumps(answer))

    @staticmethod
    def _json(conn: ServerConnection, status: int, body: dict):
        response = conn.respond(status, json.dumps(body))
        response.headers["Content-Type"] = "application/json"
        return response

    def _look(self, code: str) -> dict:
        if not r.is_code(code):
            return {"ok": False, "why": r.ERR_BAD_CODE}
        room = self._room(code)
        if room is None:
            return {"ok": False, "why": r.ERR_NO_ROOM}
        if room.host is None:
            return {"ok": False, "why": r.ERR_AWAY}
        if self._guest_fresh(room):
            return {"ok": False, "why": r.ERR_FULL}
        return {"ok": True, "lan": room.lan}

    # --- WebSockets ---
    def _handle(self, conn: ServerConnection) -> None:
        url = urllib.parse.urlsplit(conn.request.path)
        query = {k: v[0] for k, v in urllib.parse.parse_qs(url.query).items()}
        if url.path == f"{r.API}/host":
            self._host(conn, query.get("code"), query.get("key", ""))
        else:
            self._guest(conn, query.get("code", ""))

    def _host(self, conn: ServerConnection, code: str | None, key: str) -> None:
        with self._lock:
            if code is None:
                code = r.new_code()
                while code in self.rooms:
                    code = r.new_code()
                room = self.rooms[code] = Room(code, secrets.token_hex(16))
                self._note("room_new", code)
            else:
                room = self._room(code)
                if room is None or not hmac.compare_digest(room.key, key):
                    _send(conn, {"t": "error", "why": r.ERR_GONE})
                    return
                _close(room.host)  # (a link of the host's that had not noticed it was dead) ...
                guest, room.guest = room.guest, None
                _close(guest, CLOSE_HOST_AWAY)  # ... took the guest's channel with it
                self._note("host_back", code)
            room.host, room.host_away_at, room.acked = conn, None, None
            _send(conn, {"t": "room", "code": room.code, "key": room.key})
        closing = False
        try:
            for msg in conn:
                if isinstance(msg, bytes):
                    with self._lock:
                        self._count_frame()
                        if room.host is conn and room.guest is not None and room.acked == room.n:
                            _send(room.guest, msg)
                elif len(msg) <= TEXT_MAX:
                    closing = self._host_says(room, conn, msg)
                    if closing:
                        return
        except ConnectionClosed:
            pass
        finally:
            with self._lock:
                if room.host is conn:
                    room.host, room.acked = None, None
                    room.host_away_at = time.monotonic()
                    guest, room.guest = room.guest, None
                    _close(guest, CLOSE_HOST_AWAY)  # the guest's game waits and comes back
                    if closing and self.rooms.get(room.code) is room:
                        del self.rooms[room.code]
                        self._note("room_end", room.code, "host_closed")
                    elif not closing:
                        self._note("host_out", room.code, "host_link")

    def _host_says(self, room: Room, conn: ServerConnection, text: str) -> bool:
        """A word from the host; True when it closes the room."""
        try:
            word = json.loads(text)
        except ValueError:
            return False
        if not isinstance(word, dict):
            return False
        with self._lock:
            if room.host is not conn:
                return False
            if word.get("t") == "lan" and isinstance(word.get("lan"), str):
                room.lan = word["lan"][:300]
            elif word.get("t") == "ack" and word.get("n") == room.n and room.guest is not None:
                room.acked = room.n
            elif word.get("t") == "stat":
                rtt = word.get("rtt")
                if isinstance(rtt, (int, float)) and not isinstance(rtt, bool):
                    if 0 <= rtt <= RTT_MAX_MS and room.guest is not None:
                        room.rtt_ms = int(rtt)
            elif word.get("t") == "close":
                return True
        return False

    def _guest(self, conn: ServerConnection, code: str) -> None:
        with self._lock:
            answer = self._look(code)
            room = self.rooms.get(code)
            if not answer["ok"]:
                _send(conn, {"t": "error", "why": answer["why"]})
                return
            old, room.guest = room.guest, conn
            _close(old)  # (a guest that had gone silent)
            if old is not None:
                self._note("guest_replaced", code)
            self._note("guest_in", code)
            room.n += 1
            room.rtt_ms = None
            room.acked = None
            room.guest_seen = time.monotonic()
            _send(room.host, {"t": "peer", "on": True, "n": room.n})
            _send(conn, {"t": "joined"})
        try:
            for msg in conn:
                room.guest_seen = time.monotonic()
                if isinstance(msg, bytes):
                    with self._lock:
                        self._count_frame()
                        if room.guest is conn and room.host is not None:
                            _send(room.host, msg)
        except ConnectionClosed:
            pass
        finally:
            with self._lock:
                if room.guest is conn:
                    room.guest, room.acked, room.rtt_ms = None, None, None
                    room.quiet_since = time.monotonic()
                    self._note("guest_out", code, "guest_link")
                    _send(room.host, {"t": "peer", "on": False})


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=47480)
    parser.add_argument("--key", default="", help="admin key for /v1/status (none: refused)")
    args = parser.parse_args()
    relay = Relay(args.host, args.port, admin_key=args.key)
    print(f"relay at {relay.url}  (NEONPOOL_RELAY_URL={relay.url}); Ctrl+C stops it", flush=True)
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        relay.close()


if __name__ == "__main__":
    main()
