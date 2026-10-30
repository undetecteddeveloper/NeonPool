"""The other player's cue, as the screen shows it. Pure (no pygame).

Only the NEWEST packet counts (an older one that arrives late is dropped), and the picture closes
on it with a filter about one frame long: no buffer, so the cue is never more than about a frame
behind what the network delivered. Hidden means no cue; it comes back at once at its angle
(no swing across the table from where it was last seen).
"""

from __future__ import annotations

import math

from game import config
from game.net.protocol import AIM_HIDDEN, AIM_PULLING, Aim, dequantize_angle, dequantize_pull


def _newer(n: int, than: int) -> bool:
    """Packet number `n` is after `than` (they count up and wrap at 256)."""
    return 0 < (n - than) & 0xFF < 128


class RemoteCue:
    def __init__(self) -> None:
        self.state = AIM_HIDDEN
        self.angle = 0.0  # where the cue points on the screen (radians)
        self.pull = 0.0  # how far it is pulled back (logical px, 0..MAX_DRAG_PX)
        self._to_angle = 0.0
        self._to_pull = 0.0
        self._last_n: int | None = None
        self.received = 0  # packets that counted
        self.dropped = 0  # packets that were late or repeated

    def receive(self, aim: Aim) -> bool:
        """Take a packet; False if it was older than one already seen."""
        if self._last_n is not None and not _newer(aim.n, self._last_n):
            self.dropped += 1
            return False
        self._last_n = aim.n
        self.received += 1
        was_hidden = self.state == AIM_HIDDEN
        self.state = aim.state
        self._to_angle = dequantize_angle(aim.angle)
        self._to_pull = dequantize_pull(aim.pull) if aim.state == AIM_PULLING else 0.0
        if was_hidden and aim.state != AIM_HIDDEN:
            self.angle, self.pull = self._to_angle, self._to_pull
        return True

    @property
    def visible(self) -> bool:
        return self.state != AIM_HIDDEN

    @property
    def power(self) -> float:
        """The strength of the pull, by the same curve as the local cue."""
        return min(1.0, self.pull / config.MAX_DRAG_PX) ** config.POWER_CURVE

    def update(self, dt: float) -> None:
        if not self.visible or dt <= 0:
            return
        k = 1.0 - math.exp(-dt / config.NET_REMOTE_CUE_TAU_S)
        turn = math.atan2(
            math.sin(self._to_angle - self.angle), math.cos(self._to_angle - self.angle)
        )
        self.angle += turn * k
        self.pull += (self._to_pull - self.pull) * k
