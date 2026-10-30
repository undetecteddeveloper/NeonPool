"""Direct connection over TCP on the local network. Pure (no pygame).

The game loop never waits for a socket: each connection has a reading thread and a writing thread
that only move whole frames between the socket and two queues, and `poll()` / `send()` just touch
the queues. A run of unreliable frames waiting to go out is cut down to the newest one (an old
cue position is worth nothing), but reliable frames keep their order. Hanging up flushes what is
still queued first, so a goodbye is delivered. Windows asks once whether the game may listen.
"""

from __future__ import annotations

import logging
import socket
import sys
import threading
from collections import deque

from game import config
from game.net import protocol as p

log = logging.getLogger("neonpool")

CONNECT_CONNECTING, CONNECT_OK, CONNECT_FAILED = "connecting", "ok", "failed"
ERR_REFUSED, ERR_TIMEOUT, ERR_ADDRESS, ERR_UNREACHABLE = (
    "refused",  # nobody is listening there
    "timeout",  # no answer in time
    "address",  # not an address
    "unreachable",  # the network says no
)
_RECV = 65536
SWITCH_INTERVAL_S = 0.0002
_switch_interval_set = False


def _wake_threads_fast() -> None:
    """Make the network threads get the interpreter at once. By default a thread waiting for it
    asks the busy one to let go only after 5 ms; on Windows that wait is rounded up to a clock tick,
    so a frame from the network sat ~10 ms behind a busy main thread (measured: tools/netbench.py
    --tcp). Under 1 ms the wait is rounded down to nothing and the hand-over is immediate."""
    global _switch_interval_set
    if not _switch_interval_set:
        sys.setswitchinterval(SWITCH_INTERVAL_S)
        _switch_interval_set = True


class OutQueue:
    """Frames waiting to be written, in order; a run of unreliable ones keeps only the newest."""

    def __init__(self) -> None:
        self._frames: deque[tuple[bytes, bool]] = deque()
        self._cond = threading.Condition()
        self._finished = False

    def put(self, frame: bytes, reliable: bool) -> None:
        with self._cond:
            if self._finished:
                return
            if not reliable and self._frames and not self._frames[-1][1]:
                self._frames[-1] = (frame, False)
            else:
                self._frames.append((frame, reliable))
            self._cond.notify()

    def take(self) -> list[bytes] | None:
        """Everything waiting (blocks until there is something); None once finished and empty."""
        with self._cond:
            while not self._frames and not self._finished:
                self._cond.wait()
            if not self._frames:
                return None
            out = [f for f, _ in self._frames]
            self._frames.clear()
            return out

    def finish(self) -> None:
        with self._cond:
            self._finished = True
            self._cond.notify_all()


class TcpTransport:
    """A connected socket as a `Transport`."""

    def __init__(self, sock: socket.socket) -> None:
        _wake_threads_fast()
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        sock.settimeout(None)
        self._sock = sock
        self._in: deque[bytes] = deque()
        self._out = OutQueue()
        self._up = True
        threading.Thread(target=self._read_loop, name="net-read", daemon=True).start()
        threading.Thread(target=self._write_loop, name="net-write", daemon=True).start()

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
        """Hang up once what is queued has been written."""
        self._out.finish()

    def _read_loop(self) -> None:
        reader = p.FrameReader()
        try:
            while True:
                data = self._sock.recv(_RECV)
                if not data:
                    break
                self._in.extend(reader.feed(data))
        except p.ProtocolError as exc:
            log.warning("net: the stream is broken (%s); hanging up", exc)
        except OSError:
            pass
        finally:
            self._up = False
            self._out.finish()

    def _write_loop(self) -> None:
        try:
            while (batch := self._out.take()) is not None:
                self._sock.sendall(b"".join(batch))
        except OSError:
            pass
        finally:
            self._up = False
            for end in (lambda: self._sock.shutdown(socket.SHUT_RDWR), self._sock.close):
                try:
                    end()
                except OSError:
                    pass


class TcpListener:
    """A room waiting for its guest. `accept()` hands over each new connection once, without
    waiting; a third person knocking while the room is full is told so and sent away."""

    def __init__(self, port: int = config.NET_PORT, bind: str = "0.0.0.0") -> None:
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        if sys.platform != "win32":  # on Windows this would let a second program share the port
            self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind((bind, port))
        self._sock.listen(2)
        self.port: int = self._sock.getsockname()[1]
        self._fresh: deque[TcpTransport] = deque()
        self._current: TcpTransport | None = None
        self._open = True
        threading.Thread(target=self._accept_loop, name="net-accept", daemon=True).start()

    def accept(self) -> TcpTransport | None:
        try:
            return self._fresh.popleft()
        except IndexError:
            return None

    def close(self) -> None:
        self._open = False
        try:
            self._sock.close()
        except OSError:
            pass

    def _accept_loop(self) -> None:
        while self._open:
            try:
                conn, _ = self._sock.accept()
            except OSError:
                return
            if self._current is not None and self._current.connected:
                try:
                    conn.sendall(p.encode(p.Reject(p.REJECT_BUSY)))
                    conn.close()
                except OSError:
                    pass
                continue
            self._current = TcpTransport(conn)
            self._fresh.append(self._current)


class Connector:
    """Joining a room, in a thread: ask `result()` each frame."""

    def __init__(self, host: str, port: int, timeout: float = config.NET_CONNECT_TIMEOUT_S) -> None:
        self.state = CONNECT_CONNECTING
        self.error: str | None = None
        self._transport: TcpTransport | None = None
        threading.Thread(
            target=self._run, args=(host, port, timeout), name="net-connect", daemon=True
        ).start()

    def result(self) -> TcpTransport | None:
        """The connection once it is made (only the first time you ask after that)."""
        transport, self._transport = self._transport, None
        return transport

    def _run(self, host: str, port: int, timeout: float) -> None:
        try:
            sock = socket.create_connection((host, port), timeout)
        except ConnectionRefusedError:
            self.error = ERR_REFUSED
        except TimeoutError:
            self.error = ERR_TIMEOUT
        except socket.gaierror:
            self.error = ERR_ADDRESS
        except OSError:
            self.error = ERR_UNREACHABLE
        else:
            self._transport = TcpTransport(sock)
            self.state = CONNECT_OK
            return
        self.state = CONNECT_FAILED


def local_address() -> str:
    """This machine's address on the local network (what the other player types)."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("192.0.2.1", 9))  # no packet is sent; it only picks the outgoing interface
            return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"


def parse_address(text: str) -> tuple[str, int] | None:
    """'192.168.1.5' or '192.168.1.5:47474' -> (host, port); None if it is not an address."""
    text = text.strip()
    host, colon, port_text = text.partition(":")
    if not host or not host.isascii() or not all(ch.isalnum() or ch in ".-" for ch in host):
        return None
    if not colon:
        return host, config.NET_PORT
    if not port_text.isdigit() or not 1 <= int(port_text) <= 65535:
        return None
    return host, int(port_text)
