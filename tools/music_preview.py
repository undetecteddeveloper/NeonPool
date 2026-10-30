"""Ghi các bản nhạc nền ra file .wav để người dùng nghe thử (Claude không nghe được nhạc).

    .venv\\Scripts\\python.exe tools\\music_preview.py [--times 2] [--out tools\\_out\\music]

Mỗi bản được ghi lặp `--times` lần để nghe chỗ nối vòng lặp. Exit: 0 = đã ghi; 1 = lỗi.
"""

from __future__ import annotations

import argparse
import sys
import wave
from pathlib import Path

import numpy as np

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--times", type=int, default=2, help="how many times each loop repeats")
    parser.add_argument("--out", default="tools/_out/music")
    args = parser.parse_args()

    from game import music
    from game.config import SAMPLE_RATE

    out = Path(args.out)
    out = out if out.is_absolute() else ROOT / out
    out.mkdir(parents=True, exist_ok=True)
    for name, style in music.STYLES.items():
        loop = music.render(style)
        path = out / f"{name}.wav"
        with wave.open(str(path), "wb") as f:
            f.setnchannels(1)
            f.setsampwidth(2)
            f.setframerate(SAMPLE_RATE)
            f.writeframes(np.tile(loop, args.times).tobytes())
        used = [k for k, s in music.TRACKS.items() if s is style]
        note = f" (đang dùng cho: {used[0]})" if used else ""
        print(f"{path}  {style.loop_s * args.times:.0f} giây, {style.bpm:.0f} BPM{note}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
