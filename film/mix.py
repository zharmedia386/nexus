"""Place the kept VO takes from vo/schedule.json on the film clock -> vo/mix-raw.wav (48 kHz stereo); writes the site captions too.

Run with the earshot venv (numpy, scipy, soundfile). Loudness to -16 LUFS is done by ffmpeg loudnorm in render.sh.
"""
import json
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.signal import resample_poly

ROOT = Path(__file__).parent
SR = 48000
schedule = json.loads((ROOT / "vo/schedule.json").read_text())
mix = np.zeros(int(schedule["duration"] * SR) + SR)
cues = []


def stamp(seconds):
    return f"{int(seconds // 60):02d}:{seconds % 60:06.3f}"


for line in schedule["lines"]:
    audio, rate = sf.read(ROOT / "vo/takes" / f"{line['take']}.wav")
    audio = resample_poly(audio, SR, rate)
    start = int(line["t"] * SR)
    end = min(start + len(audio), len(mix))
    assert not mix[start:end].any() or np.abs(mix[start:end]).max() < 0.01, f"{line['take']} overlaps speech"
    mix[start:end] += audio[: end - start]
    voiced = np.flatnonzero(np.abs(audio) > 0.01)
    cues.append((line["t"] + voiced[0] / SR, line["t"] + voiced[-1] / SR + 0.25, line["text"]))

mix = mix[: int(schedule["duration"] * SR)]
sf.write(ROOT / "vo/mix-raw.wav", np.stack([mix, mix], axis=1), SR, subtype="PCM_24")

vtt = ["WEBVTT", ""]
for index, (start, end, text) in enumerate(cues, 1):
    vtt += [str(index), f"{stamp(start)} --> {stamp(end)}", text, ""]
(ROOT.parent / "frontend/public/film/nexus-demo.en.vtt").write_text("\n".join(vtt))
print(f"{len(cues)} cues, mix {len(mix) / SR:.2f}s")
