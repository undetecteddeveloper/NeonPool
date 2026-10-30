"""AC1: playing alone is exactly what it was before network play (a scripted game, fingerprinted).

The fingerprint was taken on `main` before `PlayScene` was split for network play; if it changes,
solo practice changed. Like the 15-shot physics fingerprint of the spin work, it depends on the
platform's maths library: a different machine that differs only here is a reason to look, not
proof of a bug.
"""

import hashlib

import pygame as pg
import pytest

from game import config, i18n
from game.app import App
from game.physics import Shot

GOLDEN = "91d0a2f288122be7"

SHOTS = (  # the break, then three more: a mix of power, angle and spin
    Shot(0.0, 0.9, 0.0),
    Shot(0.35, 0.6, 0.5),
    Shot(-0.2, 0.45, -0.5),
    Shot(3.0, 0.7, 0.0),
)


@pytest.fixture
def app():
    pg.init()
    a = App(pg.display.set_mode(config.LOGICAL_SIZE))
    a.go_play()
    yield a
    pg.quit()
    i18n.set_lang("vi")


def settle(app):
    for _ in range(90 * 60):
        if not app.play._live:
            return
        app.update(1 / 60)
    raise AssertionError("the balls never stopped")


def fingerprint(app) -> str:
    play = app.play
    r = play.rules
    parts = [repr((b.number, b.x, b.y, b.in_play, b.pocket)) for b in play.world.balls]
    parts.append(repr((r.shots, r.fouls, sorted(r.pocketed), r.group, r.phase, r.cue_in_hand)))
    parts.append(repr((r.is_break, r.last, r.score)))
    return hashlib.sha256("|".join(parts).encode()).hexdigest()[:16]


def test_ac1_solo_fingerprint_unchanged(app):
    for shot in SHOTS:
        play = app.play
        if play.rules.cue_in_hand:
            play.rules.cue_placed()  # leave the cue ball where it stopped
        play.fire(shot)
        settle(app)
    assert fingerprint(app) == GOLDEN
