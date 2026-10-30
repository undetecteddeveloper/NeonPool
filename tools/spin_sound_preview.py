"""Ghi các tiếng chỉnh xoáy ra file .wav để người dùng nghe thử (Claude không nghe được).

    .venv\\Scripts\\python.exe tools\\spin_sound_preview.py [--out tools\\_out\\spin_sounds]

Mỗi file: tiếng bíp rê nút làm mốc độ to, nghỉ, rồi chín nốt đi lên (đánh thấp -> cao) và đi
xuống, đúng âm lượng trong game. Exit: 0 = đã ghi; 1 = lỗi.
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
GAP_S = 0.22  # between two steps of the dial, as when the wheel is rolled steadily
PAUSE_S = 0.6


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="tools/_out/spin_sounds")
    args = parser.parse_args()

    from game import audio
    from game.config import SAMPLE_RATE

    out = Path(args.out)
    out = out if out.is_absolute() else ROOT / out
    out.mkdir(parents=True, exist_ok=True)

    def silence(seconds: float) -> np.ndarray:
        return np.zeros(int(SAMPLE_RATE * seconds), dtype=np.int16)

    def step(samples: np.ndarray, volume: float) -> np.ndarray:
        tail = silence(max(0.0, GAP_S - samples.size / SAMPLE_RATE))
        return np.concatenate([(samples * volume).astype(np.int16), tail])

    blip = step(audio.synth_blip(), 0.30)  # the quietest button sound: the yardstick
    for name, (lowest, volume) in audio.SPIN_SOUNDS.items():
        notes = [step(audio.synth_spin(f), volume) for f in audio.spin_notes(lowest)]
        wav = np.concatenate([blip, silence(PAUSE_S), *notes, silence(PAUSE_S), *notes[::-1]])
        path = out / f"xoay_{name}.wav"
        with wave.open(str(path), "wb") as f:
            f.setnchannels(1)
            f.setsampwidth(2)
            f.setframerate(SAMPLE_RATE)
            f.writeframes(wav.tobytes())
        lo, hi = audio.spin_notes(lowest)[0], audio.spin_notes(lowest)[-1]
        mark = " (đang dùng)" if name == audio.DEFAULT_SPIN_SOUND else ""
        print(f"{path}  {lo}–{hi} Hz, âm lượng {volume}{mark}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
