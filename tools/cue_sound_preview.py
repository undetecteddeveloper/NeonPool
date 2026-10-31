"""Ghi tiếng nhấc và đặt bi cái (đúng như trong game) ra file .wav để người dùng nghe lại (Claude
không nghe được).

    .venv\\Scripts\\python.exe tools\\cue_sound_preview.py [--out tools\\_out\\<thư mục của việc>]

File bi_cai.wav: tiếng rê nút (blip) làm mốc độ to, nghỉ, rồi nhấc – nghỉ – đặt, hai lần liền,
đúng âm lượng trong game. Exit: 0 = đã ghi; 1 = lỗi.
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
PAUSE_S = 0.6  # after the yardstick and between the two goes
HOLD_S = 0.5  # the ball is in the air this long


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="tools/_out/cue_sounds")
    args = parser.parse_args()

    from game import audio
    from game.config import SAMPLE_RATE

    out = Path(args.out)
    out = out if out.is_absolute() else ROOT / out
    out.mkdir(parents=True, exist_ok=True)

    def silence(seconds: float) -> np.ndarray:
        return np.zeros(int(SAMPLE_RATE * seconds), dtype=np.int16)

    def scaled(samples: np.ndarray, volume: float) -> np.ndarray:
        return (samples * volume).astype(np.int16)

    # the volumes are the ones Audio.play_cue_pick / play_cue_put use
    once = [
        scaled(audio.synth_ball_pick(), 0.45),
        silence(HOLD_S),
        scaled(audio.synth_ball_put(), 0.55),
    ]
    blip = scaled(audio.synth_blip(), 0.30)  # the quietest button sound: the yardstick
    wav = np.concatenate([blip, silence(PAUSE_S), *once, silence(PAUSE_S), *once, silence(0.3)])
    path = out / "bi_cai.wav"
    with wave.open(str(path), "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(SAMPLE_RATE)
        f.writeframes(wav.tobytes())
    print(f"{path}  nhấc rồi đặt bi cái, hai lần liền")
    return 0


if __name__ == "__main__":
    sys.exit(main())
