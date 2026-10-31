"""Build the game into one Windows program: dist/NeonPool.exe (fonts and texts are inside it).

    .venv/Scripts/python.exe tools/build_exe.py [--folder]

Without --folder everything is packed in ONE file (starts a little slower: it unpacks to a temp
folder first). With --folder you get dist/NeonPool/ with NeonPool.exe and its files beside it
(starts faster). Settings are still kept in %APPDATA%/NeonPool, not next to the program.
Exit: 0 = built; 1 = PyInstaller failed or the program is missing.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--folder", action="store_true", help="a folder instead of one file")
    args = parser.parse_args()
    cmd = [
        sys.executable, "-m", "PyInstaller", "main.py",
        "--name", "NeonPool",
        "--windowed",  # no black console window behind the game
        "--onedir" if args.folder else "--onefile",
        "--noconfirm", "--clean",
        "--add-data", f"{ROOT / 'assets'};assets",
        "--add-data", f"{ROOT / 'lang'};lang",
        "--distpath", str(ROOT / "dist"),
        "--workpath", str(ROOT / "build"),
        "--specpath", str(ROOT / "build"),
    ]  # fmt: skip
    if subprocess.run(cmd, cwd=ROOT).returncode != 0:
        print("PyInstaller báo lỗi.")
        return 1
    exe = ROOT / "dist" / ("NeonPool/NeonPool.exe" if args.folder else "NeonPool.exe")
    if not exe.exists():
        print(f"Không thấy {exe}.")
        return 1
    print(f"Đã build {exe} ({exe.stat().st_size / 1e6:.1f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
