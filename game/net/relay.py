"""Meeting through the relay: a room code instead of an address. Pure (no pygame).

The relay (`server/`: Cloudflare for real, `server/local_relay.py` on this machine) gives the host
a four-letter code and passes whole frames between host and guest over WebSockets; it never reads
them. Two machines on the same network go straight to each other instead, through the host's door
in `tcp.py` (it wants the room's secret, which only someone who typed the code gets from the
relay); the guest tries that for NET_LAN_TRY_S before going through the relay. The relay's
protocol: docs/ARCHITECTURE.md (network play). Every wait is in a thread: the game loop only asks.
"""

from __future__ import annotations

import json
import logging
import os
import secrets
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import deque

from websockets.exceptions import ConnectionClosed, InvalidStatus, WebSocketException
from websockets.sync.client import ClientConnection
from websockets.sync.client import connect as ws_connect

from game import config
from game.net import protocol as p
from game.net import tcp

log = logging.getLogger("neonpool")

API = "/v1"
CONNECTING, READY, FAILED = "connecting", "ready", "failed"
# what went wrong, for the screens (net.err.*)
ERR_NO_SERVER = "no_server"  # this build knows no relay
ERR_OFFLINE = "offline"  # no internet, or the relay does not answer
ERR_BUSY = "busy"  # the relay turns rooms away (its free share for the day is used up)
ERR_VERSION = "version"  # the relay speaks another version of this
ERR_BAD_CODE = "bad_code"
ERR_NO_ROOM = "no_room"
ERR_FULL = "full"
ERR_AWAY = "away"  # the room is there but its host is reconnecting
ERR_GONE = "gone"  # the room closed while its host was away
ERR_IDLE = "idle"  # nobody came for a long time: the relay closed the room
WHY = {ERR_BAD_CODE, ERR_NO_ROOM, ERR_FULL, ERR_AWAY, ERR_GONE, ERR_IDLE}
WS_OPTIONS = {
    "compression": None,  # frames are small; squeezing them only costs time
    "max_size": 4 * p.MAX_FRAME,
    "close_timeout": 2.0,
    "open_timeout": config.NET_CONNECT_TIMEOUT_S,
}


# --- codes and addresses ---
def relay_url() -> str:
    """Where the relay is: NEONPOOL_RELAY_URL (tests, the dev tool), else this build's own."""
    return os.environ.get("NEONPOOL_RELAY_URL", config.NET_RELAY_URL).strip().rstrip("/")


def clean_code(text: str) -> str:
    """What a player typed, as a code: capitals, only the code's letters, no longer than one."""
    up = "".join(ch for ch in text.upper() if ch in config.NET_ROOM_LETTERS)
    return up[: config.NET_ROOM_LEN]


def is_code(text: str) -> bool:
    return len(text) == config.NET_ROOM_LEN and clean_code(text) == text


def new_code(rng=None) -> str:
    pick = rng.choice if rng is not None else secrets.choice
    return "".join(pick(config.NET_ROOM_LETTERS) for _ in range(config.NET_ROOM_LEN))


def lan_info(addrs: list[tuple[str, int]], secret: bytes) -> str:
    """The host's way in on its own network, as the relay carries it (it does not read it)."""
    return ",".join(f"{h}:{port}" for h, port in addrs) + ";" + secret.hex()


def parse_lan(text: str) -> tuple[list[tuple[str, int]], bytes] | None:
    where, _, key = text.partition(";")
    try:
        secret = bytes.fromhex(key)
    except ValueError:
        return None
    if len(secret) != tcp.SECRET_LEN:
        return None
    addrs = []
    for each in where.split(",")[:4]:
        parsed = tcp.parse_address(each, 0)
        if parsed is not None and parsed[1] > 0:
            addrs.append(parsed)
    return (addrs, secret) if addrs else None


def _http_base(url: str) -> str:
    scheme, _, rest = url.partition("://")
    return {"wss": "https", "ws": "http"}.get(scheme, scheme) + "://" + rest


def _status_error(status: int) -> str:
    return ERR_VERSION if status == 404 else ERR_BUSY


def look(url: str, code: str, timeout: float = config.NET_CONNECT_TIMEOUT_S) -> dict:
    """Ask the relay about a room: {"ok": True, "lan": ...} or {"ok": False, "why": ...}."""
    query = urllib.parse.urlencode({"code": code})
    try:
        with urllib.request.urlopen(f"{_http_base(url)}{API}/look?{query}", timeout=timeout) as r:
            answer = json.loads(r.read(4096).decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return {"ok": False, "why": _status_error(exc.code)}
    except (OSError, ValueError):
        return {"ok": False, "why": ERR_OFFLINE}
    if not isinstance(answer, dict):
        return {"ok": False, "why": ERR_VERSION}
    if not answer.get("ok"):
        why = answer.get("why")
        return {"ok": False, "why": why if why in WHY else ERR_NO_ROOM}
    lan = answer.get("lan")
    return {"ok": True, "lan": lan if isinstance(lan, str) else ""}


def _open(url: str) -> tuple[ClientConnection | None, str | None]:
    """A WebSocket to the relay, or why there is none."""
    try:
        return ws_connect(url, **WS_OPTIONS), None
    except InvalidStatus as exc:
        return None, _status_error(exc.response.status_code)
    except (OSError, TimeoutError, WebSocketException):
        return None, ERR_OFFLINE


def _first_word(ws: ClientConnection) -> dict:
    """The relay's first (text) message on a new socket."""
    try:
        msg = ws.recv(timeout=config.NET_CONNECT_TIMEOUT_S)
        word = json.loads(msg) if isinstance(msg, str) else None
    except (TimeoutError, ConnectionClosed, OSError, ValueError):
        word = None
    if not isinstance(word, dict):
        return {"t": "error", "why": ERR_OFFLINE}
    return word


def _note(word: dict) -> str:
    return json.dumps(word, separators=(",", ":"))


def _hang_up(ws: ClientConnection) -> None:
    try:
        ws.close()
    except (OSError, WebSocketException):
        pass


# --- the guest's way through the relay ---
class WsTransport:
    """A WebSocket through the relay as a `Transport`: each binary message holds whole frames.
    Like `tcp.TcpTransport`, one thread reads and one writes, so nothing here waits."""

    def __init__(self, ws: ClientConnection) -> None:
        tcp.wake_threads_fast()
        self._ws = ws
        self._in: deque[bytes] = deque()
        self._out = tcp.OutQueue()
        self._up = True
        threading.Thread(target=self._read_loop, name="relay-read", daemon=True).start()
        threading.Thread(target=self._write_loop, name="relay-write", daemon=True).start()

    @property
    def connected(self) -> bool:
        return self._up

    def send(self, frame: bytes, reliable: bool = True) -> None:
        if self._up:
            self._out.put(frame, reliable)

    def poll(self) -> list[bytes]:
        frames = []
        while True:
            try:
                frames.append(self._in.popleft())
            except IndexError:
                return frames

    def close(self) -> None:
        self._out.finish()

    def _read_loop(self) -> None:
        reader = p.FrameReader()
        try:
            for msg in self._ws:
                if isinstance(msg, bytes):
                    self._in.extend(reader.feed(msg))
        except p.ProtocolError as exc:
            log.warning("relay: the stream is broken (%s); hanging up", exc)
        except (ConnectionClosed, OSError):
            pass
        finally:
            self._up = False
            self._out.finish()

    def _write_loop(self) -> None:
        try:
            while (batch := self._out.take()) is not None:
                for frame in batch:
                    self._ws.send(frame)
        except (ConnectionClosed, OSError):
            pass
        finally:
            self._up = False
            _hang_up(self._ws)


def _try_lan(where: list[tuple[str, int]], secret: bytes, wait_s: float) -> tcp.TcpTransport | None:
    """Knock at every address of the host's own network at once; the first door that opens."""
    tries = [tcp.Connector(h, port, wait_s, secret) for h, port in where]
    deadline = time.monotonic() + wait_s
    won = None
    while time.monotonic() < deadline and won is None:
        for each in tries:
            got = each.result()
            if got is not None:
                won = got
                break
        if all(each.state == tcp.CONNECT_FAILED for each in tries):
            break
        time.sleep(0.005)
    for each in tries:  # a slower door that opened as well is shut again
        extra = each.result()
        if extra is not None:
            extra.close()
    return won


class Join:
    """Going into a room by its code, in a thread: ask `result()` each frame, like
    `tcp.Connector`. Straight in if the host is on this network, through the relay if not.
    `lan` is what the relay said about the host's network (kept for coming back)."""

    def __init__(
        self,
        code: str,
        url: str | None = None,
        lan: tuple[list[tuple[str, int]], bytes] | None = None,
        lan_wait_s: float = config.NET_LAN_TRY_S,
    ) -> None:
        self.code = code
        self.url = relay_url() if url is None else url
        self.state = tcp.CONNECT_CONNECTING
        self.error: str | None = None
        self.lan = lan
        self.straight = False  # it went straight, not through the relay
        self._transport = None
        self._lan_wait_s = lan_wait_s
        threading.Thread(target=self._run, name="relay-join", daemon=True).start()

    def result(self):
        """The connection once it is made (only the first time you ask after that)."""
        transport, self._transport = self._transport, None
        return transport

    def _fail(self, why: str) -> None:
        self.error = why
        self.state = tcp.CONNECT_FAILED

    def _done(self, transport, straight: bool) -> None:
        self.straight = straight
        self._transport = transport
        self.state = tcp.CONNECT_OK

    def _run(self) -> None:
        if not self.url:
            self._fail(ERR_NO_SERVER)
            return
        answer = look(self.url, self.code)
        if answer["ok"]:
            self.lan = parse_lan(answer["lan"]) or self.lan
        if self.lan is not None:
            straight = _try_lan(*self.lan, self._lan_wait_s)
            if straight is not None:
                self._done(straight, True)
                return
        if not answer["ok"]:
            self._fail(answer["why"])
            return
        query = urllib.parse.urlencode({"code": self.code})
        ws, why = _open(f"{self.url}{API}/join?{query}")
        if ws is None:
            self._fail(why)
            return
        word = _first_word(ws)
        if word.get("t") != "joined":
            _hang_up(ws)
            why = word.get("why")
            self._fail(why if why in WHY or why == ERR_OFFLINE else ERR_NO_ROOM)
            return
        self._done(WsTransport(ws), False)


class GuestRelink:
    """The guest's `Relinker`: the same way in as the first time (straight, then the relay),
    tried again a second apart until it works. Remembers the host's network, so a guest whose
    internet is gone but who sits on the host's wifi still gets back in."""

    def __init__(self, join: Join, every_s: float = config.NET_REJOIN_TRY_S) -> None:
        self._code, self._url, self._lan = join.code, join.url, join.lan
        self._every_s = every_s
        self._attempt: Join | None = None
        self._next_at = 0.0
        self._closed = False

    def poll(self):
        if self._closed:
            return None
        now = time.monotonic()
        if self._attempt is None and now >= self._next_at:
            self._attempt = Join(self._code, self._url, self._lan)
        if self._attempt is not None:
            transport = self._attempt.result()
            if self._attempt.lan is not None:
                self._lan = self._attempt.lan
            if transport is not None:  # the session hears this one out before another is made
                self._attempt, self._next_at = None, now + config.NET_HANDSHAKE_TIMEOUT_S
            elif self._attempt.state == tcp.CONNECT_FAILED:
                self._attempt, self._next_at = None, now + self._every_s
            return transport
        return None

    def close(self) -> None:
        self._closed = True


# --- the host's room ---
class Channel:
    """The host's end of one guest's way through the relay. A guest who leaves ends it; whoever
    comes in next gets a new channel (numbered by the relay), so nothing meant for one reaches
    the other."""

    def __init__(self, room: HostRoom, n: int) -> None:
        self._room, self.n = room, n
        self._in: deque[bytes] = deque()
        self._reader = p.FrameReader()
        self.up = True

    @property
    def connected(self) -> bool:
        return self.up

    def send(self, frame: bytes, reliable: bool = True) -> None:
        if self.up:
            self._room._send((self.n, frame), reliable)

    def poll(self) -> list[bytes]:
        frames = []
        while True:
            try:
                frames.append(self._in.popleft())
            except IndexError:
                return frames

    def close(self) -> None:
        self.up = False

    def _arrive(self, data: bytes) -> None:
        try:
            self._in.extend(self._reader.feed(data))
        except p.ProtocolError as exc:
            log.warning("relay: a guest's stream is broken (%s)", exc)
            self.up = False


class HostRoom:
    """A room: a code from the relay, a door on this network, and `accept()` handing over each
    guest connection (from either) once, without waiting. The relay link comes back by itself if
    it breaks (the room's `key` takes the code back); `state` / `code` / `error` are for the
    screen."""

    def __init__(
        self, url: str | None = None, port: int = config.NET_PORT, door: bool = True
    ) -> None:
        self.url = relay_url() if url is None else url
        self.state = CONNECTING
        self.code = ""
        self.error: str | None = None
        self.secret = secrets.token_bytes(tcp.SECRET_LEN)
        self._key = ""
        self._fresh: deque = deque()
        self._channel: Channel | None = None
        self._out: tcp.OutQueue | None = None
        self._ws: ClientConnection | None = None
        self._lock = threading.Lock()
        self._closed = False
        self.door = self._open_door(port) if door else None
        if not self.url:
            self.state, self.error = FAILED, ERR_NO_SERVER
            return
        threading.Thread(target=self._run, name="relay-host", daemon=True).start()

    def _open_door(self, port: int) -> tcp.TcpListener | None:
        for each in (port, 0):
            try:
                return tcp.TcpListener(each, secret=self.secret)
            except OSError as exc:
                log.info("relay: no door on port %s (%s)", each, exc)
        return None

    def lan(self) -> str:
        if self.door is None:
            return ""
        return lan_info([(tcp.local_address(), self.door.port)], self.secret)

    # --- what the screens and the session ask ---
    def accept(self):
        if self.door is not None:
            straight = self.door.accept()
            if straight is not None:
                return straight
        try:
            return self._fresh.popleft()
        except IndexError:
            return None

    def close(self) -> None:
        """Shut the room: the relay forgets the code at once."""
        if self._closed:
            return
        self._closed = True
        if self.door is not None:
            self.door.close()
        with self._lock:
            out, ws = self._out, self._ws
            if self._channel is not None:
                self._channel.up = False
        if out is not None:
            out.put(_note({"t": "close"}), True)
            out.finish()
        elif ws is not None:
            _hang_up(ws)

    # --- the relay link (its own thread) ---
    def _send(self, item, reliable: bool) -> None:
        out = self._out
        if out is not None:
            out.put(item, reliable)

    def _run(self) -> None:
        while not self._closed:
            if self.code:
                query = urllib.parse.urlencode({"code": self.code, "key": self._key})
                ws, why = _open(f"{self.url}{API}/host?{query}")
            else:
                ws, why = _open(f"{self.url}{API}/host")
            if ws is not None:
                word = _first_word(ws)
                if word.get("t") == "room" and isinstance(word.get("code"), str):
                    self._serve(ws, word)
                    if self.error == ERR_IDLE:
                        self.state = FAILED
                        return
                    continue
                _hang_up(ws)
                why = word.get("why") if word.get("why") in WHY else ERR_OFFLINE
            if not self.code or why in (ERR_GONE, ERR_IDLE):
                self.state, self.error = FAILED, why
                return
            time.sleep(config.NET_REJOIN_TRY_S)  # the room still has its code: knock again

    def _serve(self, ws: ClientConnection, word: dict) -> None:
        out = tcp.OutQueue()
        with self._lock:
            if self._closed:
                _hang_up(ws)
                return
            self._ws, self._out = ws, out
        self.code, self._key = word["code"], str(word.get("key", ""))
        self.state, self.error = READY, None
        threading.Thread(
            target=self._write_loop, args=(ws, out), name="relay-hw", daemon=True
        ).start()
        out.put(_note({"t": "lan", "lan": self.lan()}), True)
        try:
            for msg in ws:
                if isinstance(msg, bytes):
                    channel = self._channel
                    if channel is not None and channel.up:
                        channel._arrive(msg)
                else:
                    self._hear(msg, out)
        except (ConnectionClosed, OSError):
            pass
        finally:
            with self._lock:
                self._ws = self._out = None
                if self._channel is not None:
                    self._channel.up = False
                self._channel = None
            out.finish()

    def _hear(self, text: str, out: tcp.OutQueue) -> None:
        try:
            word = json.loads(text)
        except ValueError:
            return
        if not isinstance(word, dict):
            return
        if word.get("t") == "peer":
            with self._lock:
                if self._channel is not None:
                    self._channel.up = False
                self._channel = None
                if word.get("on") and isinstance(word.get("n"), int):
                    self._channel = Channel(self, word["n"])
                    out.put(_note({"t": "ack", "n": word["n"]}), True)
                    self._fresh.append(self._channel)
        elif word.get("t") == "error" and word.get("why") == ERR_IDLE:
            self.error = ERR_IDLE

    def _write_loop(self, ws: ClientConnection, out: tcp.OutQueue) -> None:
        try:
            while (batch := out.take()) is not None:
                for item in batch:
                    if isinstance(item, str):
                        ws.send(item)
                    else:
                        n, frame = item
                        channel = self._channel
                        if channel is not None and channel.up and channel.n == n:
                            ws.send(frame)
        except (ConnectionClosed, OSError):
            pass
        finally:
            _hang_up(ws)


class HostRelink:
    """The room's `Relinker` for the host: the same room that let the guest in."""

    def __init__(self, room: HostRoom) -> None:
        self._room = room

    def poll(self):
        return self._room.accept()

    def close(self) -> None:
        self._room.close()
