"""Mọi test chạy không cửa sổ, không âm thanh."""

import os
import tempfile

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
# never read or write the player's real settings: each test run gets its own empty folder
os.environ["NEONPOOL_SETTINGS"] = os.path.join(tempfile.mkdtemp(prefix="neonpool-"), "s.json")
