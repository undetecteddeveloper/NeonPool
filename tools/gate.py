"""Cổng kiểm tra một lệnh: ruff check, ruff format --check, pytest, smoke headless.

    .venv\\Scripts\\python.exe tools\\gate.py          # đầy đủ
    .venv\\Scripts\\python.exe tools\\gate.py --quick  # bỏ smoke (việc vặt)

Exit code 0 chỉ khi mọi bước đã CHẠY và xanh. Bước không chạy được thì báo rõ, không im lặng.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

# Console Windows hay là cp1252: ép UTF-8 để in tiếng Việt không sập.
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
PY = sys.executable
SMOKE_NO_APP = 3  # tools/smoke.py trả mã này khi chưa có game/app.py


def run(name: str, cmd: list[str]) -> int:
    print(f"\n=== {name}: {' '.join(cmd)}", flush=True)
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    code = subprocess.run(cmd, cwd=ROOT, env=env).returncode
    print(f"--- {name}: exit {code}", flush=True)
    return code


def main() -> int:
    quick = "--quick" in sys.argv
    steps = [
        ("ruff check", [PY, "-m", "ruff", "check", "."]),
        ("ruff format", [PY, "-m", "ruff", "format", "--check", "."]),
        ("pytest", [PY, "-m", "pytest", "-q"]),
    ]
    if not quick:
        steps.append(("smoke", [PY, "tools/smoke.py", "--frames", "300"]))

    results: list[tuple[str, str]] = []
    for name, cmd in steps:
        code = run(name, cmd)
        if code == 0:
            results.append((name, "XANH"))
        elif name == "smoke" and code == SMOKE_NO_APP:
            results.append((name, "CHƯA CHẠY (chưa có game/app.py — dự án chưa có app)"))
        else:
            results.append((name, f"ĐỎ (exit {code})"))

    print("\n=== TỔNG KẾT")
    for name, status in results:
        print(f"  {name:12} {status}")
    if quick:
        print("  smoke        BỎ QUA (--quick)")
    red = [n for n, s in results if s.startswith("ĐỎ")]
    print("KẾT QUẢ:", "ĐỎ — " + ", ".join(red) if red else "XANH")
    return 1 if red else 0


if __name__ == "__main__":
    sys.exit(main())
