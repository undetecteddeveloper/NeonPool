"""Vietnamese + English strings. Every on-screen word goes through t("key") (invariant 5)."""

from __future__ import annotations

import json
import logging
from pathlib import Path

log = logging.getLogger("neonpool")

LANG_DIR = Path(__file__).resolve().parent.parent / "lang"
LANGS = ("vi", "en")
DEFAULT_LANG = "vi"

_current = DEFAULT_LANG
_tables: dict[str, dict[str, str]] = {}
_warned: set[str] = set()


def table(lang: str) -> dict[str, str]:
    if lang not in _tables:
        with open(LANG_DIR / f"{lang}.json", encoding="utf-8") as f:
            _tables[lang] = json.load(f)
    return _tables[lang]


def set_lang(lang: str) -> None:
    global _current
    if lang not in LANGS:
        raise ValueError(f"unknown language {lang!r}")
    _current = lang


def get_lang() -> str:
    return _current


def t(key: str, **fmt: object) -> str:
    """Text for `key` in the current language; falls back to the other language, then the key."""
    for lang in (_current, *(x for x in LANGS if x != _current)):
        text = table(lang).get(key)
        if text is not None:
            return text.format(**fmt) if fmt else text
    if key not in _warned:
        _warned.add(key)
        log.warning("missing translation key: %s", key)
    return key
