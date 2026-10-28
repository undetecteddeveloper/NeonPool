"""Pure physics (no pygame import). See docs/ARCHITECTURE.md."""

from game.physics.raycast import Contact, first_contact
from game.physics.shot import Shot
from game.physics.world import (
    Ball,
    BallHitBall,
    BallHitCushion,
    BallPocketed,
    Event,
    World,
)

__all__ = [
    "Ball",
    "BallHitBall",
    "BallHitCushion",
    "BallPocketed",
    "Contact",
    "Event",
    "Shot",
    "World",
    "first_contact",
]
