# NEXUS demo film

The 103.6 s narrated film on the landing page: `frontend/public/film/nexus-demo.mp4` (+ `nexus-demo-poster.png`,
`nexus-demo.en.vtt`). Every UI frame is the real app recorded against the live stack; nothing is mocked.
Script, beats and on-screen text: [`script.md`](script.md).

## What is real and what is drawn

| Shot | Source |
|---|---|
| Ask (rag abstain), Ask (hybrid + graph_local, path strip, evidence drawer), Explore, Themes, Benchmarks | Playwright recordings of http://localhost:3000 with the API, gateway and Milvus up (`capture/beats.spec.ts`, no `page.route`). The graph_local wait (about 22 s) is shortened with a visible jump cut; its timer stays on screen. |
| Themes and Benchmarks push-ins | The 2x (`deviceScaleFactor: 2`) screenshots taken by the same tests at the same scroll position, swapped in on an identical frame so the zoom stays sharp. |
| Three documents | Verbatim text of the three chunks the answer cites, from `/chunks/{id}` and `/documents/{id}`. |
| Graph field | Illustrative layout. Node colours and type counts (207 people, 150 companies, 8 groups, 10 other) and the 375 / 1,142 totals come from `/graph/stats`; positions are seeded noise. |
| The walk | Drawn by the composition. Nodes and chunk ids are the `graph_paths` the API returned for this question. The API's relation types are only `SERVES_AS`, `FAMILY_OF`, `SERVES_AS`; the on-screen labels (Direktur Utama · since 2015, spouse, Komisaris Utama · since 2019) are read from each hop's stored quote, e.g. "Raden Prasasta adalah pasangan suami/istri dari Zaenab Thamrin." |
| Callouts | Values from the committed report (run 96950f8a), placed next to the same values in the Benchmarks capture. |
| Cursor | Added in the edit at the click coordinates Playwright logged (`capture/raw/*.marks.json`); Playwright videos do not record a pointer. |

## Rebuild

```bash
# 1. Footage (API :8000 and site :3000 up). Writes capture/raw/{beat}.webm, .marks.json, shots/*.png
cd frontend && NODE_PATH=$PWD/node_modules npx playwright test -c ../film/capture/playwright.config.ts
# 2. Clips for the composition (30 fps H.264, short GOP so per-frame seeks are exact)
cd ../film/capture/raw && for b in a-abstain b-ask c-explore d-themes e-benchmarks; do
  ffmpeg -y -i $b.webm -vf fps=30 -c:v libx264 -crf 16 -g 10 -pix_fmt yuv420p -an ../../composition/clips/$b.mp4; done
cp shots/e-benchmarks-chart.png ../../composition/plates/benchmarks-chart.png
cp shots/d-themes-cards-scrolled.png ../../composition/plates/themes-cards.png
# 3. Voice: Kokoro af_heart, one take per line (SSL_CERT_FILE is set from certifi inside tts.py)
#    KOKORO_PY = python of a venv with kokoro installed; EARSHOT_PY = python of the earshot venv (render.sh reads it too)
cd ../.. && "$KOKORO_PY" tts.py
VO_SPEED=1.05 VO_TAG=-s105 "$KOKORO_PY" tts.py L17
for f in vo/takes/*.wav; do "$(dirname "$EARSHOT_PY")/earshot" describe --json $f > vo/scores/$(basename $f .wav).json; done
# 4. Mix + captions + picture + encode + poster
./render.sh
```

`render.sh` runs `mix.py` (places the kept takes from `vo/schedule.json`, writes the VTT from the same times),
normalises to -16 LUFS / -1.5 dBTP with ffmpeg `loudnorm`, renders `composition/index.html` frame by frame with the
motionmaxxing `render.mjs` (each `<video>` is seeked per frame), and encodes H.264 High + AAC with `+faststart`.
The composition is plain HTML on the motionmaxxing GSAP runtime (`composition/runtime/`, GSAP 3.12.5 vendored) rather
than a HyperFrames project: `render.mjs` already gives frame-exact video seeking, which this film depends on.
Fonts are the site's own Inter Tight and IBM Plex Mono, copied from the Next build; their SIL OFL 1.1 text is
`composition/fonts/OFL.txt`. The vendored runtime carries the motionmaxxing `LICENSE` (Apache-2.0) and `NOTICE`.

Gitignored (regenerate with the steps above): `capture/raw/`, `vo/takes/`, `vo/scores/`, `vo/*.wav`,
`composition/clips/`, `composition/plates/`, `build/`, `look/`. The final mix exists only inside the MP4 (a 24-bit WAV
of it is 30 MB).

## Voice takes (earshot `describe --json`)

Gate: AudioSet "Speech synthesizer" probability ≤ 0.2 and noise floor ≤ -60 dBFS. Kokoro baseline from the brief:
synth ≈ 0.1, noise ≈ -71 dBFS. Five full lines failed the synth gate at three speeds; splitting them into shorter
sentences passed every time, so the kept set is 23 takes. A first 120 s draft of the script was cut before any take
was scored.

| Take | Length s | Synth | Noise dBFS | Use |
|---|---|---|---|---|
| L01 | 6.05 | 0.178 | -87.2 | kept |
| L02 | 4.10 | 0.178 | -93.2 | kept |
| L03 | 3.35 | 0.118 | -93.2 | kept |
| L04 | 6.72 | 0.263 | -81.2 | rejected |
| L04-s105 | 6.62 | 0.252 | -82.5 | rejected |
| L04-s95 | 7.03 | 0.324 | -83.4 | rejected |
| L04a | 2.48 | 0.000 | -93.3 | kept |
| L04b | 1.95 | 0.094 | -93.3 | kept |
| L04c | 2.77 | 0.130 | -93.3 | kept |
| L05 | 3.15 | 0.000 | -93.4 | kept |
| L06 | 5.03 | 0.195 | -93.0 | kept |
| L07 | 4.25 | 0.066 | -93.1 | kept |
| L08 | 4.15 | 0.143 | -93.1 | kept |
| L09 | 2.77 | 0.075 | -93.4 | kept |
| L10 | 7.33 | 0.289 | -81.3 | rejected |
| L10-s105 | 7.05 | 0.246 | -80.3 | rejected |
| L10-s95 | 7.40 | 0.240 | -82.4 | rejected |
| L10a | 2.50 | 0.054 | -93.5 | kept |
| L10b | 4.92 | 0.141 | -93.0 | kept |
| L11 | 4.28 | 0.126 | -93.0 | kept |
| L12 | 5.20 | 0.151 | -92.8 | kept |
| L13 | 4.05 | 0.099 | -93.1 | kept |
| L14 | 8.25 | 0.443 | -84.8 | rejected |
| L14-s105 | 7.97 | 0.323 | -85.0 | rejected |
| L14-s95 | 8.55 | 0.492 | -85.4 | rejected |
| L14a | 6.72 | 0.200 | -86.3 | kept (at the limit) |
| L14b | 1.90 | 0.074 | -93.4 | kept |
| L15 | 7.17 | 0.086 | -78.4 | kept |
| L16 | 6.50 | 0.280 | -83.7 | rejected |
| L16-s105 | 6.25 | 0.319 | -83.2 | rejected |
| L16-s95 | 6.65 | 0.328 | -84.1 | rejected |
| L16a | 1.98 | 0.075 | -93.2 | kept |
| L16b | 4.80 | 0.166 | -92.9 | kept |
| L17 | 6.28 | 0.203 | -84.9 | rejected |
| L17-s105 | 6.20 | 0.182 | -85.5 | kept |
| L17-s95 | 6.62 | 0.238 | -87.4 | rejected |
| L18 | 3.75 | 0.107 | -93.2 | kept |

Kept takes: synth 0.000–0.200 (mean 0.11), noise -78.4 to -93.5 dBFS, all at or under the baseline noise.

Final mix (audio track of the MP4, 103.6 s): -16.0 LUFS integrated, -1.4 dBTP, LRA 3.5 LU (ffmpeg `ebur128`).
earshot on the whole mix: synth 0.831, noise floor -200 dBFS (digital silence between lines). A whole-file score is
not comparable with per-take scores: the same voice's 18 unselected full-line takes, concatenated and normalised the
same way (99.6 s), score 0.858. No music bed: the film runs on voice and picture only.
