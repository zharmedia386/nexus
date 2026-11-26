# NEXUS Site Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the single-page NEXUS frontend into a product site (landing + app pages + content pages + footer), produce a 75–110 s hybrid demo film with English voiceover embedded on the landing, and rewrite the README in the graphify structure.

**Architecture:** App sections become real Next.js routes (`/ask`, `/explore`, `/themes`, `/eval`) that keep their query-string state; cross-links navigate between routes instead of scrolling. The landing and content pages are static and read only committed fixtures under `frontend/lib/showcase/`, captured once from the live API by a script. Landing motion uses GSAP + ScrollTrigger behind a reduced-motion guard. The film is built outside the app (Playwright footage + HyperFrames/GSAP composition + Kokoro VO) and committed as `frontend/public/film/*`.

**Tech Stack:** Next.js 16.4.6 (app router, `cacheComponents`), React 19.3, Tailwind 4.3, GSAP 3 (new, approved), d3-force, vitest 5 + Testing Library, Playwright 1.65; film: Playwright, HyperFrames (`npx --prefix ~/tools/openmotion hyperframes`), Kokoro TTS, earshot, ffmpeg.

**Spec:** `docs/superpowers/specs/2026-11-26-nexus-site-redesign-design.md`

## Global Constraints

- Next.js here has breaking changes: read the relevant guide in `frontend/node_modules/next/dist/docs/` before writing routing/layout code (`frontend/AGENTS.md`).
- Only new dependency allowed: `gsap` (includes ScrollTrigger). Anything else needs the owner's explicit yes.
- Keep the existing design system (`docs/design-system.md`, tokens in `frontend/app/globals.css`); extend, never replace. No monveo or isometricon branding, logos or copy.
- No login, registration, accounts, pricing, testimonials or persona pages.
- Landing (`/`) and content pages (`/how-it-works`, `/benchmarks`, `/docs`) must render fully with the API (`:8000`) down: they import only committed fixtures.
- Every answer, citation and number shown on the landing, content pages and film comes from the real system or the committed report (run `96950f8a`). No mocked answers.
- Graph stats shown are the extracted graph: 375 entities, 1,142 relations (label "extracted graph"). Headline: graph_local 0.70 vs hybrid 0.52 answer match, paired diff +0.18 [0.09, 0.28], 112 answerable / 136 questions; thematic loss stated.
- Repo URL (final): `https://github.com/zharmedia386/nexus`. License: MIT.
- `prefers-reduced-motion: reduce` → no running animations after load (existing e2e guarantee); no scroll-jacking; no layout shift from motion.
- Film: 1920×1080, 30 fps, H.264 MP4, 75–110 s, poster PNG, English VTT captions, files in `frontend/public/film/`; if MP4 > 25 MB stop and ask the owner.
- VO: Kokoro EN voice `af_heart` (venv `~/tools/video/kokoro/.venv`, set `SSL_CERT_FILE` from certifi); score every take with earshot (`~/tools/earshot`, `describe --json`) against the Kokoro baseline (synth ≈ 0.1, noise ≈ -71 dBFS) and report the numbers.
- Comments: one line, why not what. 2-space indent, ES modules, async/await.
- Commits: the owner commits only when told, as one clean squashed commit. Task "Checkpoint" steps mean `git add` of that task's files only (no `git commit`), so each task's diff stays reviewable with `git diff --cached`. Never commit or push without the owner saying so.

## Review Focus

1. **API down while browsing `/`, `/how-it-works`, `/benchmarks`, `/docs`**: pages render completely, no error states, no network calls to `:8000`. Test owned by Task 3 (`e2e/offline.spec.ts`).
2. **Old bookmarks `/?q=x#ask`, `/#explore`, `/?c=c1#themes`**: land on the matching route with the query kept (`/ask?q=x`). Test owned by Task 1.
3. **Reduced motion on the GSAP landing**: no running animations, walkthrough shows its final state statically. Test owned by Task 4.
4. **Phone width (375 px)**: no horizontal page scroll on any route; nav collapses to a menu. Test owned by Task 2.
5. **Film before it exists / slow network**: the film section shows the poster and a usable control, no autoplay with sound, captions track present. Test owned by Task 5.

---

## File Structure

| Path | Responsibility |
|---|---|
| `frontend/lib/routes.ts` (new, replaces `lib/sections.ts`) | `APP_PAGES`, `CONTENT_PAGES`, `writeParams`, `legacyHashTarget` |
| `frontend/app/(app)/layout.tsx` + `ask/page.tsx`, `explore/page.tsx`, `themes/page.tsx`, `eval/page.tsx` | App routes with app sub-nav |
| `frontend/app/(site)/how-it-works/page.tsx`, `benchmarks/page.tsx`, `docs/page.tsx` | Static content pages |
| `frontend/app/page.tsx` | Landing composition only |
| `frontend/components/site/site-nav.tsx`, `site-footer.tsx`, `app-nav.tsx`, `legacy-hash-redirect.tsx` | Chrome |
| `frontend/components/landing/*` | Landing sections (hero, film, walkthrough, modes, proof, pipeline, run-it) |
| `frontend/lib/motion.ts` | GSAP registration + reduced-motion guard |
| `frontend/lib/showcase/*.json` + `frontend/lib/showcase/index.ts` | Committed fixtures + typed accessors |
| `frontend/scripts/capture-showcase.ts` | One-off capture from live API + copy of `docs/report/eval-report.json` |
| `film/` (repo root, new) | Film source: `script.md`, `vo/`, `capture/*.spec.ts`, `composition/`, `render.sh` |
| `README.md`, `LICENSE` | Docs |

Deleted: `app/ask/route.ts`, `app/explore/route.ts`, `app/themes/route.ts`, `app/eval/route.ts`, `lib/sections.ts`, `components/lazy-section.tsx` (+ its test), `components/section.tsx`, `components/home-bento.tsx`, `components/site-nav.tsx` (moved), `components/site-nav.test.tsx` (rewritten under `components/site/`).

---

### Task 1: App pages become routes

**Files:**
- Create: `frontend/lib/routes.ts`, `frontend/lib/routes.test.ts`, `frontend/app/(app)/layout.tsx`, `frontend/app/(app)/{ask,explore,themes,eval}/page.tsx`, `frontend/components/site/legacy-hash-redirect.tsx`
- Modify: `components/ask/ask-view.tsx`, `components/ask/answer-card.tsx:8,143-146`, `components/graph/explore-view.tsx:15,148`, `components/themes/themes-section.tsx:9,57-58,172`, `components/ask/ask.test.tsx:258-270`, `components/graph/explore.test.tsx:198-208`, `components/themes/themes.test.tsx:65-73`, `e2e/app.spec.ts`, `e2e/ask.spec.ts`, `e2e/explore.spec.ts`, `e2e/helpers.ts` (drop `loadAllSections`)
- Delete: `app/{ask,explore,themes,eval}/route.ts`, `lib/sections.ts`, `components/lazy-section.tsx`, `components/lazy-section.test.tsx`, `components/section.tsx`

**Interfaces:**
- Produces:
  - `APP_PAGES: readonly { href: "/ask" | "/explore" | "/themes" | "/eval"; label: "Ask" | "Explore" | "Themes" | "Eval"; keys: readonly string[] }[]` (keys as in old `SECTIONS`)
  - `writeParams(updates: Record<string, string | null>): void` (same behaviour as today, but never touches the hash)
  - `legacyHashTarget(hash: string, search: string): string | null` → `"#ask"` + `"?q=x"` → `"/ask?q=x"`; unknown hash → `null`
  - `<LegacyHashRedirect />` client component: on mount, `router.replace(legacyHashTarget(...))` when non-null
- Consumes: existing `AskView`, `ExploreView`, `ThemesSection`, `EvalSection` unchanged except cross-links.

- [ ] **Step 1: Write failing unit tests in `lib/routes.test.ts`**

```ts
expect(legacyHashTarget("#ask", "?q=x&modes=rag")).toBe("/ask?q=x&modes=rag");
expect(legacyHashTarget("#explore", "?e=c0&from=a")).toBe("/explore?e=c0&from=a");
expect(legacyHashTarget("#themes", "")).toBe("/themes");
expect(legacyHashTarget("#nope", "?q=x")).toBeNull();
expect(legacyHashTarget("", "")).toBeNull();
expect(APP_PAGES.map((page) => page.href)).toEqual(["/ask", "/explore", "/themes", "/eval"]);
```
Plus: `writeParams({ q: "x" })` on `/ask#foo` leaves `pathname` `/ask`, sets `q`, keeps other keys.

- [ ] **Step 2: Run** `npx vitest run lib/routes.test.ts` → FAIL (module missing).
- [ ] **Step 3: Implement `lib/routes.ts`** and route pages. Each `app/(app)/<name>/page.tsx` renders a page header (eyebrow `01 · Ask` etc., title and intro copied from the current `<Section>` props in `app/page.tsx`) and the existing view. `(app)/layout.tsx` renders `<AppNav />` from Task 2 (stub a plain `<nav>` until Task 2 lands, or do Task 2 first if executing out of order). Cross-links: themes member chip → `router.push("/explore?e=" + id)`; answer-card community link `href="/themes?c=…"` as a normal `<Link>`. Mount `<LegacyHashRedirect />` in `app/page.tsx`.
- [ ] **Step 4: Update unit tests** that asserted hashes (`#explore`, `#themes`, `#ask`) to assert the new pathname/query instead; delete the LazySection and `sectionRedirect` tests.
- [ ] **Step 5: Update e2e**: `ask.spec.ts` and `explore.spec.ts` `goto("/ask")`, `goto("/explore")`, `goto("/themes")`; replace the old-route redirect test with:

```ts
test("legacy hash bookmark lands on the route", async ({ page }) => {
  await page.goto("/?q=x#ask");
  await expect(page).toHaveURL(/\/ask\?q=x/);
  await expect(page.locator("#question")).toHaveValue("x");
});
```
- [ ] **Step 6: Run** `npm run typecheck && npm test && npm run lint` → all pass; with the API up `npx playwright test e2e/ask.spec.ts e2e/explore.spec.ts e2e/app.spec.ts` → pass.
- [ ] **Step 7: Checkpoint**: `git add` this task's files (intended message: `refactor(frontend): split app sections into routes`).

---

### Task 2: Site chrome: nav, app nav, footer

**Files:**
- Create: `components/site/site-nav.tsx`, `components/site/app-nav.tsx`, `components/site/site-footer.tsx`, `components/site/site-chrome.test.tsx`, `e2e/layout.spec.ts`
- Modify: `app/layout.tsx` (use new nav + footer), `app/(app)/layout.tsx` (use `AppNav`)
- Delete: `components/site-nav.tsx`, `components/site-nav.test.tsx`

**Interfaces:**
- Consumes: `APP_PAGES` (Task 1); add `CONTENT_PAGES = [{ href: "/how-it-works", label: "How it works" }, { href: "/benchmarks", label: "Benchmarks" }, { href: "/docs", label: "Docs" }] as const` and `REPO_URL = "https://github.com/zharmedia386/nexus"` to `lib/routes.ts`.
- Produces: `SiteNav()`, `AppNav()`, `SiteFooter({ runId }: { runId: string })`.

- [ ] **Step 1: Failing tests (`site-chrome.test.tsx`)**: SiteNav links = `CONTENT_PAGES` hrefs + GitHub (`REPO_URL`, `rel="noreferrer"`, opens new tab) + "Open app" → `/ask`; on `/ask` pathname the AppNav item Ask has `aria-current="page"`; footer contains every APP_PAGES and CONTENT_PAGES href, `REPO_URL`, the text `All companies and people are fictional.`, and the run id passed in; below `md` the nav renders a menu button with `aria-expanded` toggling and `Escape` closing it.
- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement.** Keep the existing glass pill nav look and theme toggle; mobile: collapsible sheet. Footer: four columns (Product, Learn, Project, note) on `md+`, stacked on mobile; stack line `Neo4j · Milvus · Postgres · LangGraph · FastAPI · Next.js`; run id from `lib/showcase` (Task 3; pass `"96950f8a"` until then).
- [ ] **Step 4: e2e `layout.spec.ts`** (no API needed, so it must not use the API-gated `test` from helpers; import from `@playwright/test`): for each of `/`, `/ask`, `/how-it-works`, `/benchmarks`, `/docs` at 375×812, `document.documentElement.scrollWidth <= 375`; footer visible.
- [ ] **Step 5: Run** unit + `npx playwright test e2e/layout.spec.ts` → pass.
- [ ] **Step 6: Checkpoint**: `git add` this task's files (intended message: `feat(frontend): site nav, app nav and footer`).

---

### Task 3: Showcase fixtures and offline guarantee

**Files:**
- Create: `frontend/scripts/capture-showcase.ts`, `frontend/lib/showcase/{walkthrough.json,graph-stats.json,report.json,index.ts,showcase.test.ts}`, `frontend/e2e/offline.spec.ts`
- Modify: `frontend/package.json` (script `"capture:showcase": "node --experimental-strip-types scripts/capture-showcase.ts"`), `components/eval/eval-report.fixture.json` (refresh from run `96950f8a`, trimmed the same way as today)

**Interfaces:**
- Produces (`lib/showcase/index.ts`):
  - `WALKTHROUGH: { question: string; graph: Answer; baseline: Answer }` (graph = `graph_local`, baseline = `hybrid`)
  - `GRAPH_STATS: GraphStats`
  - `REPORT: EvalReport` (copy of `docs/report/eval-report.json`)
  - `RUN_ID: string` (first 8 chars of `REPORT.run_id`)
- Consumes: `Answer`, `GraphStats`, `EvalReport` from `lib/types.ts`.

- [ ] **Step 1: Failing test `showcase.test.ts`**

```ts
expect(WALKTHROUGH.question).toBe("At which company does the spouse of the Direktur Utama of Cahaya Teguh since 2015 currently serve as Komisaris Utama since 2019?");
expect(WALKTHROUGH.graph.mode).toBe("graph_local");
expect(WALKTHROUGH.graph.text).toContain("PT Karya Semesta");
expect(WALKTHROUGH.graph.graph_paths[0].node_names).toEqual(expect.arrayContaining(["Zaenab Thamrin", "Raden Prasasta", "PT Karya Semesta"]));
expect(WALKTHROUGH.baseline.abstained).toBe(true);
expect(GRAPH_STATS.nodes).toBe(375);
expect(GRAPH_STATS.relationships).toBe(1142);
expect(RUN_ID).toBe("96950f8a");
```
- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement `capture-showcase.ts`**: POST `/query` for the question in modes `graph_local` and `hybrid` (verify true), GET `/graph/stats`, copy `../docs/report/eval-report.json`; write pretty JSON; abort with a clear message if the API is down or if any assertion in Step 1 would fail (so a bad capture is never committed). Run it once with the backend up (needs gateway + Milvus reachable) and commit the JSON.
- [ ] **Step 4: e2e `offline.spec.ts`** (plain `@playwright/test`, no API gate): `page.route("http://localhost:8000/**", (route) => route.abort())`, then for `/`, `/how-it-works`, `/benchmarks`, `/docs` assert no request to `:8000` was attempted (`page.on("request")` collector is empty) and the H1 is visible. Only meaningful once Tasks 5–6 exist; add it now with `/` only and extend it in Task 6.
- [ ] **Step 5: Run** unit + offline e2e → pass.
- [ ] **Step 6: Checkpoint**: `git add` this task's files (intended message: `feat(frontend): committed showcase fixtures`).

---

### Task 4: Motion foundation (GSAP)

**Files:**
- Create: `frontend/lib/motion.ts`, `frontend/lib/motion.test.ts`
- Modify: `frontend/package.json` (`npm i gsap@3` — exact version pinned by npm), `e2e/motion.spec.ts`

**Interfaces:**
- Produces:
  - `prefersReducedMotion(): boolean`
  - `useGsap(scope: RefObject<HTMLElement | null>, build: (ctx: { gsap: typeof gsap; ScrollTrigger: typeof ScrollTrigger; reduced: boolean }) => void, deps?: unknown[]): void` — registers ScrollTrigger once, runs `build` inside `gsap.context(…, scope)`, reverts on unmount; when `reduced`, `build` must set end states only (`gsap.set`), never tweens.

- [ ] **Step 1: Failing test** (`motion.test.ts`, jsdom, `matchMedia` mocked to reduce): a component using `useGsap` with a `build` that calls `gsap.to(el, { opacity: 0.5 })` when not reduced and `gsap.set(el, { opacity: 1 })` when reduced renders with `opacity: 1` and `gsap.globalTimeline.getChildren().length === 0`; unmount reverts (`ctx.revert` called).
- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement** (read the owner's `gsap-react` and `gsap-scrolltrigger` skills first; follow their cleanup pattern).
- [ ] **Step 4: Extend `e2e/motion.spec.ts`**: with `reducedMotion: "reduce"`, load `/`, scroll to the bottom in 400 px steps, wait 1 s; assert `document.getAnimations()` has no running entries and every walkthrough step (`[data-walkthrough-step]`) has computed `opacity` `1` and is visible (final state shown without motion).
- [ ] **Step 5: Run** → pass.
- [ ] **Step 6: Checkpoint**: `git add` this task's files (intended message: `feat(frontend): gsap motion foundation with reduced-motion guard`).

---

### Task 5: Landing page

**Files:**
- Create: `components/landing/{hero.tsx,film.tsx,walkthrough.tsx,modes.tsx,proof.tsx,pipeline.tsx,run-it.tsx,landing.test.tsx}`
- Modify: `app/page.tsx` (composition only), `components/network-hero.tsx` (refine, still decorative), `e2e/app.spec.ts` (home test)
- Delete: `components/home-bento.tsx`

**Interfaces:**
- Consumes: `WALKTHROUGH`, `GRAPH_STATS`, `REPORT`, `RUN_ID` (Task 3); `useGsap` (Task 4); `PathStrip`, `AnswerText`, `CitationChip` (existing Ask components, rendered with fixture data, `onCite` opens an inline quote popover using the hit text in the fixture, never the API); `ModeTable`, `ScoreCell`, `DiffCell`, `summaryRow`, `diffRow`, `MODE_LABEL`, `CATEGORY_LABEL` (existing eval code).
- Produces: `Film({ src, poster, captions }: { src: string; poster: string; captions: string })` reused by nothing else.

Section content and order are fixed by the spec §"Landing page"; copy follows `docs/design-system.md` voice. Load the owner's `unslop`, `antislop-copywriting`, `design-taste-frontend` and `emil-design-eng` skills before writing markup and copy.

- [ ] **Step 1: Failing tests (`landing.test.tsx`)**:
  - hero shows `0.70`, `0.52`, `375`, `1,142`, `136` and the label `extracted graph`; CTAs "Watch the film" (`href="#film"`) and "Open app" (`href="/ask"`).
  - Film: `<video>` has `controls`, `preload="metadata"`, `poster="/film/nexus-demo-poster.png"`, no `autoplay`, a `<track kind="captions" srclang="en" default>` with `src="/film/nexus-demo.en.vtt"`; when the video errors, a fallback paragraph with a link to the GitHub README renders.
  - Walkthrough renders the fixture question, the three node names in path order, the hybrid baseline text `The documents do not contain this information.`, and a citation chip whose activation shows the cited sentence from the fixture without any `fetch` call (`vi.spyOn(globalThis, "fetch")` not called).
  - Proof renders the graph_local vs hybrid diff `+0.18` with `[0.09, 0.28]` and a thematic row showing graph_local below hybrid.
  - Run-it shows the three commands from the README quickstart and a link to `/docs`.
- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement sections.** Walkthrough: pinned-free scroll reveal (no scroll-jacking): three steps stacked; ScrollTrigger `scrub: false`, `once: true` per step; graph hops draw in sequence (stroke-dashoffset), answer types in per sentence; reduced motion → final state. Film placeholder: until Task 8 ships, `public/film/nexus-demo-poster.png` is a static frame rendered from the landing hero (export via Playwright screenshot) and the MP4 path 404s → fallback paragraph shows.
- [ ] **Step 4: Update e2e home test** in `app.spec.ts` (H1 `Answers that show their path`, nav links, no in-page section ids) and extend `offline.spec.ts` (Task 3) — `/` already covered.
- [ ] **Step 5: Run** unit, typecheck, lint, `npx playwright test` (API up) → pass.
- [ ] **Step 6: Checkpoint**: `git add` this task's files (intended message: `feat(frontend): product landing page`).

---

### Task 6: Content pages

**Files:**
- Create: `app/(site)/how-it-works/page.tsx`, `app/(site)/benchmarks/page.tsx`, `app/(site)/docs/page.tsx`, `components/content/{prose.tsx,pipeline-diagram.tsx,content.test.tsx}`
- Modify: `e2e/offline.spec.ts` (add the three routes)

**Interfaces:**
- Consumes: `REPORT`, `GRAPH_STATS` (Task 3); eval chart components; `pipeline.tsx` diagram may be shared with Task 5 — if so export `PipelineDiagram()` from `components/content/pipeline-diagram.tsx` and import it in the landing.

Content:
- **How it works**: corpus generation (world → LLM docs, fictional), ingestion (chunks → Postgres, dense + BM25 in Milvus), graph build (schema-guided extraction with verbatim-quote check, entity resolution, Neo4j with per-edge provenance), communities (Leiden + cited summaries), the four modes (rag, hybrid, graph_local, graph_global) + auto router, citation verifier. Facts come from `docs/superpowers/specs/2026-11-24-nexus-design.md` and the code; each mode gets "what the LLM sees" in one sentence (pinned provenance chunks for graph_local; community summaries for graph_global).
- **Benchmarks**: headline (0.70 vs 0.52, +0.18 [0.09, 0.28]), answer-match-by-category table with CIs, graph extraction quality (relation F1 0.9506, FAMILY_OF recall 0.969), judge results on thematic, caveats verbatim from `REPORT.caveats` / report §Limitations, link to the full `docs/report/eval-report.md` on GitHub.
- **Docs**: prerequisites, setup (`.env` keys from `.env.example`, Postgres, Neo4j, Milvus prefix rule), pipeline commands (README quickstart), API endpoints table (from `backend/nexus/api/app.py`), troubleshooting (gateway down, Milvus unreachable, restart API after `graph build`).

- [ ] **Step 1: Failing tests (`content.test.tsx`)**: each page renders its H1; Benchmarks shows `+0.18` and `[0.09, 0.28]` and every string in `REPORT.caveats`; Docs lists every endpoint path in `["/query", "/documents/{doc_id}", "/chunks/{chunk_id}", "/graph/entity/{entity_id}", "/graph/path", "/graph/search", "/graph/stats", "/eval/report", "/communities", "/health"]`; How it works names all five modes.
- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement** as server components (static, no client fetch).
- [ ] **Step 4: Extend `offline.spec.ts`** with the three routes; **run** all → pass.
- [ ] **Step 5: Checkpoint**: `git add` this task's files (intended message: `feat(frontend): how it works, benchmarks and docs pages`).

---

### Task 7: Design and motion review pass

**Files:** any under `frontend/components/`, `frontend/app/`; screenshots to `docs/screenshots/`.

- [ ] **Step 1:** Run the owner's review skills over every route (desktop 1440, phone 375; light and dark): `unslop`, `antislop` (+ `antislop-ui`, `antislop-human` incl. its contrast checker), `impeccable` critique/audit, `emil-design-eng` for motion. Record findings as a checklist in the task report.
- [ ] **Step 2:** Fix every finding rated important; list the rest with reasons.
- [ ] **Step 3:** Regenerate screenshots (`e2e` `shoot` helper, updated to route names: `main`, `ask`, `explore`, `themes`, `eval`, `how-it-works`, `benchmarks`, `docs`).
- [ ] **Step 4:** Run full unit + e2e + `npm run build` → pass; Lighthouse-style sanity in Playwright: no console errors on any route.
- [ ] **Step 5: Checkpoint**: `git add` this task's files (intended message: `style(frontend): design review fixes`).

---

### Task 8: Demo film

**Files:**
- Create: `film/script.md`, `film/vo/*.wav` (gitignored except final mix), `film/capture/playwright.config.ts`, `film/capture/beats.spec.ts`, `film/composition/` (HyperFrames project), `film/render.sh`, `film/README.md`
- Output: `frontend/public/film/nexus-demo.mp4`, `nexus-demo-poster.png`, `nexus-demo.en.vtt`
- Modify: `.gitignore` (film raw captures and takes)

Load the owner's `motionmaxxing` skill first and follow its workflow (idea → world → build → self-review gates); use `gsap-timeline` for the composition and `humanizer` on the script.

- [ ] **Step 1: Script** (`film/script.md`): six beats from the spec §Film with timings; VO lines written for the ear (≤ 160 wpm), every number matching Global Constraints; on-screen text list. Humanizer pass.
- [ ] **Step 2: VO**: render each line with Kokoro `af_heart`; score every take with earshot `describe --json`; keep takes with synth score ≤ 0.2 and noise ≤ -60 dBFS; record the numbers in `film/README.md`.
- [ ] **Step 3: Footage**: `beats.spec.ts` drives the finished site (API + gateway up) at 1920×1080, `deviceScaleFactor: 2`, `recordVideo`, one test per beat: (a) Ask with rag mode on the Cahaya Teguh question showing the abstain, (b) Ask graph_local + hybrid side by side, open the path strip, click a citation, (c) Explore Zaenab Thamrin neighbourhood, (d) Themes card, (e) Benchmarks chart. Real responses only (no `page.route` mocks).
- [ ] **Step 4: Composition**: HyperFrames/GSAP project placing the clips with title cards, punch-ins, callouts, the hop-by-hop path animation, number count-ups, closing card with `github.com/zharmedia386/nexus` and "Runs on your machine"; audio = VO (+ optional quiet music bed, license-free).
- [ ] **Step 5: Render** via `film/render.sh` to 1920×1080 30 fps H.264, `-movflags +faststart`; poster = frame at the answer reveal; VTT from the script timings. Check: duration 75–110 s (`ffprobe`), size ≤ 25 MB (else stop and ask), audio loudness ≈ -16 LUFS, earshot on the final mix.
- [ ] **Step 6: Wire**: landing Film test from Task 5 now passes with the real files (fallback no longer shown); watch the film end to end in the browser and report.
- [ ] **Step 7: Checkpoint**: `git add` this task's files (intended message: `feat: NEXUS demo film`).

---

### Task 9: README and license

**Files:**
- Create: `LICENSE` (MIT, year 2026, holder as in the owner's git `user.name`), `docs/media/nexus-hero.gif` (≤ 8 MB, 10–15 s cut from the film: question → path → answer)
- Modify: `README.md`

Structure per spec §README (graphify order): centered title + static badges (license MIT, Python 3.12, Node ≥ 22), pitch + three bold bullets, `> [!NOTE]` fictional data, hero GIF, Get started (prereqs table, install, `.env`, the pipeline commands already in the current README, output file tree), See it in action (real `curl /query` output for the Cahaya Teguh question, trimmed), What it does (capability table), When to reach for which mode (situation → mode table), Benchmarks (headline in heading, category table from the report, link), Architecture (Mermaid flowchart of the pipeline), Configuration (every `.env.example` key with meaning), Project layout, Privacy / local-only, Troubleshooting (`<details>`), Limitations (from report caveats), License.

- [ ] **Step 1:** Write it; every number copied from the committed report or fixtures.
- [ ] **Step 2: Verify**: `grep -nE "192\.168\.|nexus-local-dev" README.md` → nothing; every relative link resolves (`ls` each path); Mermaid renders (paste into GitHub preview locally via `gh markdown-preview` if installed, else mermaid-cli is NOT to be installed — eyeball syntax).
- [ ] **Step 3: Checkpoint**: `git add` this task's files (intended message: `docs: graphify-style README and MIT license`).

---

### Task 10: Final verification

- [ ] Backend: `cd backend && uv run pytest -q && uv run ruff check .` → pass (unchanged).
- [ ] Frontend: `npm run typecheck && npm run lint && npm test && npm run build` → pass; `npx playwright test` with API up → pass; `offline.spec.ts` and `layout.spec.ts` with API down → pass.
- [ ] Secrets/IP scan over the branch diff: `git diff main --stat` reviewed; `git grep -nE "192\.168\.|nexus-local-dev|sk-[A-Za-z0-9]{16,}"` → nothing.
- [ ] Report to the owner with screenshots and the film link; wait for "commit" before squashing onto `main`.
