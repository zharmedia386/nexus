# NEXUS site redesign: product site, demo film, README

Date: 2026-11-26 · Status: draft for approval

## Intent

NEXUS is a portfolio piece for AI-engineering roles. Today the frontend is one long page (hero → Ask → Explore → Themes → Eval). It works but reads like a demo dashboard, not a product. The owner wants it to feel like a real product site, modelled on the user flow of isometricon.com: a single-page landing that shows the product working, real inner pages, a footer, and a 1–2 minute motion film embedded on the landing page. The GitHub README should match graphify's level of detail. Everything stays local-only.

Success: a reviewer opening the repo or the running site understands in under a minute what NEXUS does, sees it working on real data, and finds the depth (methods, benchmarks, docs) one click away.

## Goals

- Landing page `/`: one page, product showcase, embedded film, isometricon-style animated walkthrough of the real flow.
- App pages as separate routes: Ask, Explore, Themes, Eval (moved out of the landing).
- Inner content pages: How it works, Benchmarks, Docs.
- Site-wide footer.
- 1–2 min demo film (hybrid: real app footage inside a motion piece), English voiceover, rendered locally to MP4, embedded on `/`.
- Outstanding UI and motion, reviewed with the owner's design skills (unslop / antislop, impeccable, design-taste-frontend, emil-design-eng, scroll-craft / gsap).
- README rewritten in the graphify structure.

## Non-goals

- Login, registration, accounts, SQLite auth. Dropped by the owner (2026-11-26): a local-only tool has nothing to gate.
- Pricing, testimonials, "for X persona" pages. A free local project has no pricing; invented testimonials would undermine credibility.
- Any change to retrieval, graph or eval behaviour. This is presentation only.
- Hosting / deployment.

## Anti-goals (failure even if it "works")

- A film or walkthrough that shows mocked answers. Every answer, citation and number shown must come from the real system or the committed eval report.
- Generic AI-template look (gradient blobs, glassmorphism cards, emoji feature grids, "Revolutionize your…" copy).
- Landing that breaks when the LLM gateway / Milvus is offline. The landing must render fully from static, committed assets.
- Motion that hurts usability: no scroll-jacking, respects `prefers-reduced-motion`, no layout shift.
- Brand imitation of isometricon or monveo: borrow flow and structure, not logos, copy or assets.

## Constraints

- Existing stack: Next.js 16 (app router), React 19, Tailwind 4, tokens in `docs/design-system.md` (monveo-derived look, no monveo branding). Keep that system; extend, don't replace.
- No new dependencies without asking the owner. GSAP is approved; anything else needs an explicit yes.
- The backend API (`:8000`) is needed only by app pages; content pages and landing must be static.
- Video toolchain on this Mac: Kokoro TTS (English, voice `af_heart`), earshot for scoring every voice take (owner rule), HyperFrames / GSAP for the motion piece, Playwright for capture, ffmpeg (no `drawtext`/`soxr`).
- Fictional-data disclaimer stays visible (footer).
- Owner rules: commit only when told, one clean commit; secrets only in `.env`.

## Approaches considered (film)

| | How | Trade-off |
|---|---|---|
| A. Pure motion graphics | Redraw the UI in HTML/GSAP, render to MP4 | Most cinematic, but shows a redrawn, not real, app |
| B. Screen recording | Record real app with Playwright, add captions | Fully real, looks unfinished |
| **C. Hybrid (chosen)** | Real Playwright clips composited into a motion film: title cards, zoom/punch-ins, callouts, animated graph path, counting numbers, English VO | Real and polished; most work |

Owner picked C with English voiceover.

## Information architecture

Public, no auth:

| Route | Purpose |
|---|---|
| `/` | Landing (single page, anchor nav within it) |
| `/ask` | Ask: run up to three modes side by side (existing `AskView`) |
| `/explore` | Entity graph explorer (existing `ExploreView`) |
| `/themes` | Community summaries (existing `ThemesSection`) |
| `/eval` | Live eval dashboard (existing `EvalSection`) |
| `/how-it-works` | Pipeline and the four retrieval modes explained with diagrams |
| `/benchmarks` | Narrative eval report (from committed `docs/report/eval-report.{md,json}`), headline chart, method, caveats |
| `/docs` | Setup, quickstart, CLI reference, config, troubleshooting |

Nav: logo · How it works · Benchmarks · Docs · GitHub · primary button "Open app" (→ `/ask`). App pages get a secondary app-nav (Ask / Explore / Themes / Eval).

Footer (every page): product links (Ask, Explore, Themes, Eval), learn links (How it works, Benchmarks, Docs), GitHub repo link, "All companies and people are fictional" note, stack line (Neo4j · Milvus · Postgres · LangGraph · FastAPI · Next.js), run id of the current report.

## Landing page (`/`), top to bottom

1. **Hero**: headline in the existing voice ("Answers that show their path."), one-line subhead, two CTAs (Watch the film · Open app), a live-ish stat strip from the committed report (e.g. graph_local 0.70 vs hybrid 0.52 answer match; 375 entities, 1,142 relations; 136 questions). Background: the existing network hero, refined.
2. **Film**: the 1–2 min MP4 in a framed player with poster frame, captions track (VTT from the VO script), plays on click (no autoplay with sound).
3. **Walkthrough** (isometricon's "prompt → generating → result" equivalent): a scroll-triggered, looping replay of a real saved answer, three steps:
   1. Question typed: the Cahaya Teguh spouse question.
   2. Graph lights up hop by hop (Zaenab Thamrin → Raden Prasasta → PT Karya Semesta) beside "hybrid: documents do not contain this".
   3. Cited answer with citation chips that open the source sentence.
   Data comes from a committed JSON fixture captured from the real API, so it renders offline.
4. **Three ways to retrieve**: rag / hybrid / graph, what each sees, when each wins. Short, visual, links to How it works.
5. **Proof**: the answer-match-by-question-type chart (same data as the published report), one-sentence findings incl. the thematic loss stated honestly. Links to Benchmarks.
6. **Under the hood**: pipeline strip (world → docs → chunks → Milvus / Neo4j → modes → verifier → eval) with the local stack.
7. **Run it yourself**: three commands, link to Docs and GitHub.
8. Footer.

## Film

- Length 75–110 s, 1920×1080, 30 fps, H.264 MP4 + poster PNG + VTT captions, committed under `frontend/public/film/` (keep file < ~25 MB; if larger, owner decides git-LFS vs. external).
- Beats (draft, refined at plan time):
  1. Cold open (0–8 s): a multi-hop question; plain RAG says "documents do not contain this".
  2. Problem (8–20 s): the three facts live in three different documents.
  3. NEXUS (20–55 s): real Ask clip; graph path animates hop by hop; cited answer; click a citation to open the source sentence.
  4. Explore and Themes (55–75 s): real clips, quick.
  5. Proof (75–95 s): the eval chart builds, +0.18 [0.09, 0.28] lands, thematic loss acknowledged.
  6. Close (95–110 s): local stack, "runs on your machine", GitHub URL.
- Footage: Playwright scripted runs against the live local app at 2x device scale, recorded per beat; no mocked responses.
- VO: Kokoro EN; every take scored with earshot and compared against the Kokoro baseline before use; script written for the ear, then checked with the humanizer skill.
- Motion: built with the motionmaxxing / HyperFrames workflow; music optional, quiet, license-free or generated; captions burned only in the social cut, not the site cut.

## README (graphify structure)

Centered logo/title, badge row (license, Python, Node, tests), one-line pitch + three bold bullets, hero image/GIF from the film, Get started (prereqs, install, `.env`, ingest/graph/eval commands, file tree of outputs), See it in action (real `curl /query` output), What it does (capability table), When to reach for which mode (situation → mode table), Benchmarks (headline number in the heading, table, link to report), Architecture (Mermaid pipeline diagram), Configuration table, Project layout, Privacy / local-only stance, Troubleshooting (`<details>`), Limitations, License. Callouts in GitHub Note/Tip/Important syntax.

## Decided by the owner

- No login/registration; footer added.
- Film approach C (hybrid), English voiceover.
- Landing single page; app and content pages are separate routes.
- GSAP (with ScrollTrigger) approved as a frontend dependency for landing motion; existing reduced-motion e2e guarantee must still hold.
- License: MIT (add `LICENSE`, badge and section).
- Final repo URL: `https://github.com/zharmedia386/nexus` (used in nav, footer, README, film closing card).
- Follow isometricon's flow; use the owner's GitHub-star skills for reverse engineering (clone-website for flow study), anti-slop review, UI/UX and motion.

## Left to the builder (my calls, correctable)

- Exact route names above; app pages at top level (`/ask`) rather than under `/app/...` since there is no auth boundary.
- Landing walkthrough and Proof sections read committed fixtures, never the live API.
- Copy tone: existing voice from `docs/design-system.md`, short declarative sentences, numbers over adjectives.
- Graph stats on the landing (375 entities, 1,142 relations) are the live extracted Neo4j counts after the doc_027 fix, not the ground-truth world (429 / 1,434). Capture them once with a script into a committed fixture and label them "extracted graph"; the frontend eval fixture is refreshed from run `96950f8a` at the same time.
- No CI workflow; README badges are static facts (license, Python, Node), no "tests passing" badge that nothing checks.
- Old redirects `/ask` → `/#ask` etc. are replaced by the real pages.
- Build order: site first, then record the film against the finished site.
- Testing: keep existing vitest + Playwright suites green, update e2e for the new routes, add a smoke test per route and an offline test that the landing renders with the API down.
