"""Run EVERY state of `states.py` headless, a few frames each, and report the ones that fail.

This is what keeps the developer's tool honest: a state that stops working (because the game it
points at changed) shows up here, in `tools/dev.py --check` and in tests/test_dev_tool.py.
"""

from __future__ import annotations

import logging
import time

from tools.devkit.harness import Harness
from tools.devkit.states import STATES, State

log = logging.getLogger("neonpool.dev")
DT = 1 / 60


def frames(app, harness: Harness, count: int) -> None:
    for _ in range(count):
        harness.tick(DT)
        app.update(DT)
        app.draw()


def run_one(app, harness: Harness, st: State, count: int) -> str | None:
    """The state's error as text, or None if it ran and drew `count` frames."""
    try:
        harness.last_error = None
        st.run(harness)
        frames(app, harness, count)
    except Exception as exc:
        log.exception("state %r failed", st.name)
        return f"{type(exc).__name__}: {exc}"
    return harness.last_error


def run_check(app, *, count: int = 45, only: list[State] | None = None) -> list[tuple[str, str]]:
    """[(state name, error)] for every state that failed (empty: all of them work)."""
    harness = Harness(app)
    lang, fps = app.settings.lang, app.settings.show_fps
    bad = []
    for st in only if only is not None else STATES:
        t0 = time.perf_counter()
        error = run_one(app, harness, st, count)
        if error:
            bad.append((st.name, error))
        log.debug("%-60s %6.0f ms", st.name, (time.perf_counter() - t0) * 1000)
    harness.reset()
    app.change_settings(lang=lang, show_fps=fps)  # (the states that change them are undone)
    return bad
