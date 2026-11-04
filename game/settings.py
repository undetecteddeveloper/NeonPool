"""The player's settings, kept when the game is closed: language, volume, music volume, screen
shake, FPS counter, the name shown to the other player in a two-player game.

Stored as a small JSON file in the user's own settings folder (Windows: %APPDATA%\\NeonPool), never
next to the game. A missing or broken file gives the defaults; every value is checked on the way
in. Writing goes through a temporary file, so a crash never leaves half a file behind.
The environment variable NEONPOOL_SETTINGS points somewhere else (tests and tools use it).
No pygame here.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

from game.config import NET_NAME_MAX

log = logging.getLogger("neonpool")
LANGS = ("vi", "en")


@dataclass
class Settings:
    lang: str = "vi"
    volume: float = 0.8  # sound effects, 0..1, in steps of VOLUME_STEP
    music: float = 0.5  # background music, the same way
    shake: bool = True  # the screen shakes on the break and on very hard hits
    show_fps: bool = False  # frames per second in the top-left corner
    player_name: str = ""  # shown to the other player; empty: the game uses a default word
    practice_best: int = 0  # best streak ever reached in Practice "the Ghost" (0..15), never drops
    practice_best_call: int = 0  # the same for Practice "Call the Pocket"
    practice_best_sprint: int = (
        0  # the same for Practice "Sprint" (balls potted before time ran out)
    )


# Which setting holds the best of each practice mode (config.PRACTICE_MODES).
PRACTICE_BEST_FIELD = {
    "ghost": "practice_best",
    "call": "practice_best_call",
    "sprint": "practice_best_sprint",
}


def best_for(settings: Settings, mode: str) -> int:
    """The best result kept for this practice mode."""
    return getattr(settings, PRACTICE_BEST_FIELD[mode])


def settings_path() -> Path:
    override = os.environ.get("NEONPOOL_SETTINGS")
    if override:
        return Path(override)
    if sys.platform == "win32" and os.environ.get("APPDATA"):
        return Path(os.environ["APPDATA"]) / "NeonPool" / "settings.json"
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "neonpool" / "settings.json"


def _clean(raw: dict) -> Settings:
    """Settings from what was in the file: a wrong or missing value falls back to its default."""
    s = Settings()
    if raw.get("lang") in LANGS:
        s.lang = raw["lang"]
    for name in ("volume", "music"):
        vol = raw.get(name)
        if isinstance(vol, int | float) and not isinstance(vol, bool):
            setattr(s, name, round(min(1.0, max(0.0, float(vol))), 2))
    for name in ("shake", "show_fps"):
        if isinstance(raw.get(name), bool):
            setattr(s, name, raw[name])
    if isinstance(raw.get("player_name"), str):
        s.player_name = "".join(c for c in raw["player_name"] if c.isprintable()).strip()[
            :NET_NAME_MAX
        ]
    for name in PRACTICE_BEST_FIELD.values():
        best = raw.get(name)
        if isinstance(best, int) and not isinstance(best, bool):
            setattr(s, name, max(0, min(15, best)))
    return s


def load(path: Path | None = None) -> Settings:
    path = path or settings_path()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return Settings()
    except (OSError, ValueError) as exc:
        log.warning("settings file unreadable, using defaults: %s (%s)", path, exc)
        return Settings()
    return _clean(raw) if isinstance(raw, dict) else Settings()


def save(settings: Settings, path: Path | None = None) -> bool:
    """Write the settings; False (and a log line) if the folder cannot be written."""
    path = path or settings_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(asdict(settings), indent=2), encoding="utf-8")
        os.replace(tmp, path)
        return True
    except OSError as exc:
        log.warning("could not save settings to %s: %s", path, exc)
        return False
