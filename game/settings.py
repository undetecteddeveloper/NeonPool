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
from dataclasses import asdict, dataclass, field
from pathlib import Path

from game.achievements import IDS as ACHIEVEMENT_IDS
from game.config import NET_NAME_MAX, PRACTICE_LEVELS, PRACTICE_MODES

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
    practice_level: str = "easy"  # the level last played in Practice (config.PRACTICE_LEVELS)
    # The best of each practice drill and level (0..15), never drops. The three older fields are
    # the HARD bests (kept, so no record already made is lost); the easy ones are apart.
    practice_best: int = 0  # "the Ghost", hard: best streak
    practice_best_call: int = 0  # "Call the Pocket", hard
    practice_best_sprint: int = 0  # "Sprint", hard (balls potted before time ran out)
    practice_best_easy: int = 0  # "the Ghost", easy
    practice_best_call_easy: int = 0
    practice_best_sprint_easy: int = 0
    # Achievements (game/achievements.py): the ones earned, in the order they were, and the three
    # counters the others are worked out from. Never reset by the game.
    achievements: list[str] = field(default_factory=list)
    ach_wins: int = 0  # Free-play games won
    ach_clean_streak: int = 0  # Free-play wins in a row with no foul (a loss or a foul ends it)
    ach_duo_wins: int = 0  # two-player games won


# Which setting holds the best of each practice mode and level (config.PRACTICE_MODES, _LEVELS).
PRACTICE_BEST_FIELD = {
    ("ghost", "hard"): "practice_best",
    ("call", "hard"): "practice_best_call",
    ("sprint", "hard"): "practice_best_sprint",
    ("ghost", "easy"): "practice_best_easy",
    ("call", "easy"): "practice_best_call_easy",
    ("sprint", "easy"): "practice_best_sprint_easy",
}
assert set(PRACTICE_BEST_FIELD) == {(m, lv) for m in PRACTICE_MODES for lv in PRACTICE_LEVELS}


def best_field(mode: str, level: str) -> str:
    """The name of the setting that keeps the best of this practice mode and level."""
    return PRACTICE_BEST_FIELD[(mode, level)]


def best_for(settings: Settings, mode: str, level: str = "hard") -> int:
    """The best result kept for this practice mode and level."""
    return getattr(settings, best_field(mode, level))


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
    if raw.get("practice_level") in PRACTICE_LEVELS:
        s.practice_level = raw["practice_level"]
    for name in PRACTICE_BEST_FIELD.values():
        best = raw.get(name)
        if isinstance(best, int) and not isinstance(best, bool):
            setattr(s, name, max(0, min(15, best)))
    earned = raw.get("achievements")
    if isinstance(earned, list):  # only known ones, each once, in order
        s.achievements = list(dict.fromkeys(a for a in earned if a in ACHIEVEMENT_IDS))
    for name in ("ach_wins", "ach_clean_streak", "ach_duo_wins"):
        n = raw.get(name)
        if isinstance(n, int) and not isinstance(n, bool):
            setattr(s, name, max(0, min(1_000_000, n)))
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
