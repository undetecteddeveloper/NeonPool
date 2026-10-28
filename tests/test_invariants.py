"""Project invariants (CLAUDE.md §1) that a machine can check."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PYGAME_IMPORT = re.compile(r"^\s*(import|from)\s+pygame\b", re.MULTILINE)


def test_physics_rules_and_config_do_not_import_pygame():
    offenders = []
    for folder in ("game/physics", "game/rules"):
        for path in (ROOT / folder).rglob("*.py"):
            if PYGAME_IMPORT.search(path.read_text(encoding="utf-8")):
                offenders.append(str(path.relative_to(ROOT)))
    config = ROOT / "game" / "config.py"
    if PYGAME_IMPORT.search(config.read_text(encoding="utf-8")):
        offenders.append("game/config.py")
    assert offenders == []


def test_no_random_module_in_physics_except_world_rng():
    for path in (ROOT / "game" / "physics").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        if path.name != "world.py":
            assert "import random" not in text, path
