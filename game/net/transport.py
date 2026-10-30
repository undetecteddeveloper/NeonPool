"""How frames get from one machine to the other. Pure (no pygame).

`Transport` is all the `Session` knows about the network: whole frames in, whole frames out.
`reliable=True` frames arrive in order and never get lost (TCP, or a reliable layer over UDP);
`reliable=False` frames (the other player's cue) may be lost or late, and a transport that has to
queue them keeps only the newest. `NetSim` is a link in virtual time with delay, jitter, loss and
cuts, seeded so a test plays the same bad network every run; `loopback_pair` is the same with
nothing wrong. Real sockets are in `tcp.py`; a path through a relay will be another transport,
with the protocol and the session unchanged.
"""

from __future__ import annotations

import heapq
import random
from typing import Protocol


class Transport(Protocol):
    @property
    def connected(self) -> bool: ...

    def send(self, frame: bytes, reliable: bool = True) -> None:
        """Hand a whole frame over; never blocks."""

    def poll(self) -> list[bytes]:
        """The whole frames that arrived since the last call, in order; never blocks."""

    def close(self) -> None: ...


class SimEndpoint:
    """One end of a `NetSim` link."""

    def __init__(self, sim: NetSim, side: int) -> None:
        self._sim, self._side = sim, side
        self.frames_sent = 0
        self.bytes_sent = 0
        self._last_reliable_at = 0.0  # reliable frames never overtake one another

    @property
    def connected(self) -> bool:
        """Up, or down with frames still to read (a closed TCP link still delivers what was
        sent before it closed)."""
        return self._sim.up or bool(self._sim._queues[self._side])

    def send(self, frame: bytes, reliable: bool = True) -> None:
        if not self._sim.up:
            return
        self.frames_sent += 1
        self.bytes_sent += len(frame)
        sim = self._sim
        delay = sim.latency_s + sim.rng.uniform(0.0, sim.jitter_s)
        if reliable:
            while sim.rng.random() < sim.loss:  # a lost packet is sent again after a timeout
                delay += sim.rto_s
            at = max(sim.now + delay, self._last_reliable_at)
            self._last_reliable_at = at
        else:
            if sim.rng.random() < sim.loss:
                return
            at = sim.now + delay
        sim._push(1 - self._side, at, frame)

    def poll(self) -> list[bytes]:
        return self._sim._take(self._side)

    def close(self) -> None:
        self._sim.cut()


class NetSim:
    """A link between two endpoints, `a` and `b`, in virtual time: call `advance(dt)` to let time
    pass. Frames sent on one end show up on the other after `latency_s` plus up to `jitter_s`.
    A lost reliable frame costs `rto_s` more per loss (and holds back the frames behind it);
    a lost unreliable frame is gone."""

    def __init__(
        self,
        latency_s: float = 0.0,
        jitter_s: float = 0.0,
        loss: float = 0.0,
        seed: int = 0,
        rto_s: float | None = None,
    ) -> None:
        self.latency_s, self.jitter_s, self.loss = latency_s, jitter_s, loss
        self.rto_s = max(0.2, 3 * latency_s) if rto_s is None else rto_s
        self.rng = random.Random(seed)  # the network's own luck: the same every run
        self.now = 0.0
        self.up = True
        self.a, self.b = SimEndpoint(self, 0), SimEndpoint(self, 1)
        self._queues: tuple[list, list] = ([], [])  # heaps of (arrives_at, order, frame)
        self._order = 0

    def _push(self, side: int, at: float, frame: bytes) -> None:
        self._order += 1
        heapq.heappush(self._queues[side], (at, self._order, frame))

    def _take(self, side: int) -> list[bytes]:
        queue, out = self._queues[side], []
        while queue and queue[0][0] <= self.now:
            out.append(heapq.heappop(queue)[2])
        return out

    def advance(self, dt: float) -> None:
        self.now += dt

    def until_next(self, side: int) -> float | None:
        """Seconds until the next frame reaches endpoint `side` (0 if one is due), None if none."""
        queue = self._queues[side]
        return max(0.0, queue[0][0] - self.now) if queue else None

    def cut(self) -> None:
        """The link goes down for good (a cable pulled, a process gone)."""
        self.up = False


def loopback_pair() -> tuple[SimEndpoint, SimEndpoint]:
    """Two endpoints joined by a perfect link: a frame sent is there at once."""
    sim = NetSim()
    return sim.a, sim.b
