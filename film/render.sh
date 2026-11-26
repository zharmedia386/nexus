#!/usr/bin/env bash
# Render the NEXUS demo film: picture (motionmaxxing render.mjs) + VO mix -> frontend/public/film/.
# Usage: film/render.sh [crf]   (default 24 after the first 20-CRF encode came out at 33.6 MB; R16 allows one re-encode at a higher CRF if the file exceeds 25 MB)
set -euo pipefail
export PATH=/opt/homebrew/bin:$PATH

FILM="$(cd "$(dirname "$0")" && pwd)"
OUT="$FILM/../frontend/public/film"
RENDER="${MOTIONMAXXING:-$HOME/.claude/skills/motionmaxxing}/scripts/render.mjs"
EARSHOT_PY="${EARSHOT_PY:?set EARSHOT_PY to the earshot venv python}"
CRF="${1:-24}"
POSTER_AT=36.7

mkdir -p "$FILM/build" "$OUT"

# 1. VO on the film clock, plus captions from the same schedule.
"$EARSHOT_PY" "$FILM/mix.py"
ffmpeg -hide_banner -loglevel error -y -i "$FILM/vo/mix-raw.wav" \
  -af loudnorm=I=-16:TP=-1.5:LRA=11 -ar 48000 "$FILM/build/mix.wav"

# 2. Picture, frame by frame (videos are seeked per frame, so the clips stay in sync).
node "$RENDER" "$FILM/composition/index.html" "$FILM/build/picture.mp4" --crf 14 --preset medium

# 3. Final encode: H.264 1080p30, AAC, +faststart.
ffmpeg -hide_banner -loglevel error -y -i "$FILM/build/picture.mp4" -i "$FILM/build/mix.wav" \
  -map 0:v -map 1:a -c:v libx264 -preset slow -crf "$CRF" -pix_fmt yuv420p -r 30 -profile:v high \
  -c:a aac -b:a 160k -shortest -movflags +faststart "$OUT/nexus-demo.mp4"

# 4. Poster: the real graph_local answer arriving in the Ask capture.
ffmpeg -hide_banner -loglevel error -y -ss "$POSTER_AT" -i "$FILM/build/picture.mp4" -frames:v 1 "$OUT/nexus-demo-poster.png"

ls -la "$OUT"
ffprobe -v error -show_entries format=duration,size -of default=nw=1 "$OUT/nexus-demo.mp4"
