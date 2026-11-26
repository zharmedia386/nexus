"""Render VO lines of film/vo/lines.txt with Kokoro af_heart -> film/vo/takes/LNN{VO_TAG}.wav (24 kHz mono).

Usage: VO_SPEED=0.95 VO_TAG=-s95 python tts.py L04 L10   (no ids = every line)
"""
import os
import sys
from pathlib import Path

import certifi

os.environ.setdefault("SSL_CERT_FILE", certifi.where())

import numpy as np  # noqa: E402
import soundfile as sf  # noqa: E402
from kokoro import KPipeline  # noqa: E402

ROOT = Path(__file__).parent / "vo"
OUT = ROOT / "takes"
OUT.mkdir(parents=True, exist_ok=True)
only = set(sys.argv[1:])
speed = float(os.environ.get("VO_SPEED", "1.0"))
tag = os.environ.get("VO_TAG", "")

pipeline = KPipeline(lang_code="a")
for row in (ROOT / "lines.txt").read_text().splitlines():
    if not row.strip() or row.startswith("#"):
        continue
    line_id, text = row.split("\t", 1)
    if only and line_id not in only:
        continue
    audio = np.concatenate([chunk.audio.numpy() for chunk in pipeline(text, voice="af_heart", speed=speed)])
    sf.write(OUT / f"{line_id}{tag}.wav", audio, 24000)
    print(f"{line_id}\t{len(audio) / 24000:.2f}s\t{text}")
