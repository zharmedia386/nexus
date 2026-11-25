# NEXUS Plan 5 — Next.js UI (Ask/Compare · Graph Explorer · Themes · Evidence · Eval)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A polished local web UI that makes graph reasoning and evidence visible: ask one question across modes side by side, explore entities and multi-hop paths with their source quotes, browse community themes, and read the evaluation results.

**Architecture:** `frontend/` is a Next.js App Router app (TypeScript, Tailwind 4) talking to the existing FastAPI service (`http://localhost:8000`, header `X-Tenant: demo`). Small backend API additions first (Task 1). Visual language strictly from `docs/design-system.md` (Monveo-derived tokens, Inter Tight + IBM Plex Mono, ease-out-expo motion, glass panels, comparison table with highlighted dark column, travelling-dash path edges). Graph rendering is custom SVG laid out with `d3-force` so edges/paths animate exactly as the design system specifies.

**Tech Stack:** Next.js 16.4, React 19.3, Tailwind 4.3, `d3-force` 3 (layout only), Vitest 5 (+ Testing Library) for component logic, Playwright 1.65 for an end-to-end smoke + screenshots. Node from `/opt/homebrew/bin` (v26). **New npm deps need user OK (listed above).**

**Spec:** `docs/superpowers/specs/2026-11-24-nexus-design.md` §8 (UI) · `docs/design-system.md` (visual spec)

**Builds on:** `3a8f843` (API: /query all modes, /graph/entity, /graph/path, /communities; eval report json at `docs/report/eval-report.json`).

## Global Constraints

- Design tokens, type scale, radii, shadows, glass recipe, keyframes and easings exactly as `docs/design-system.md`; light default + dark theme; every animation disabled under `prefers-reduced-motion`.
- NEXUS's own name and copy; no Monveo branding, assets or photos. Hero visual = the live graph.
- Accessibility: keyboard reachable controls, visible focus ring (`--ring`), WCAG AA contrast in both themes, graph has a text alternative (list of nodes/edges).
- Responsive: usable at 390px width (graph canvas becomes full-width with a list view toggle).
- API base URL from `NEXT_PUBLIC_API_URL` (default `http://localhost:8000`); tenant `demo` via env too. No secrets in the frontend.
- Typed API client: TypeScript types mirror backend Pydantic models by hand in one file; no `any`.
- 2-space indentation, ES modules, async/await (user style). Frontend checks: `npm run lint`, `npm run typecheck`, `npm run test`, `npm run build` green per task.
- No git commits by implementers.

## Review Focus

1. **Backend down / slow query (graph_local ~5–30 s)** → per-mode loading state with elapsed timer and cancel; failures shown inline per mode, other modes still render. → Task 3 `compare shows per-mode error without blanking others`.
2. **Citation id not in hits / chunk fetch 404** → citation chip rendered as unverified, no crash. → Task 3 `unknown citation renders unverified chip`.
3. **Entity with 100+ neighbours** → neighbourhood capped (API limit 40) with "+N more" and list view; layout stays readable. → Task 4 `neighbourhood cap renders more-indicator`.
4. **No path between two entities** → explicit empty state, not a blank canvas. → Task 4 `path finder shows no-path state`.
5. **Reduced motion** → no travelling dashes / reveal animations. → Task 7 Playwright check with `reducedMotion: "reduce"`.

---

### Task 1: Backend API additions for the UI

**Files:** Modify `backend/nexus/graph/neo4j_store.py`, `backend/nexus/api/app.py`, `backend/nexus/retrieval/orchestrator.py`, `backend/nexus/retrieval/graph_global.py`; Tests in `backend/tests/api/`, `backend/tests/graph/`.

**Interfaces:**
- `GraphPath` gains `hops: list[PathHop]` where `PathHop(src_id, src_name, rel_type, dst_id, dst_name, chunk_ids: list[str], quotes: list[str], doc_ids: list[str])`; existing flat fields kept for compatibility.
- `GET /graph/search?q=<text>&limit=10` → `[{id, name, type, aliases, match}]` (normalized prefix/substring match over name+aliases via the cached lexicon; min 2 chars).
- `GET /communities?level=` items gain `member_ids: list[str]`, `member_names: list[str]` (cap 50), `summary_chunk_ids`.
- `Answer.communities: list[str]` — community ids graph_global drew on (empty for other modes).
- `GET /eval/report` → serves `docs/report/eval-report.json` (404 if missing).
- `GraphStore` lazy driver creation guarded by a lock (Plan 3 deferred minor).
- [ ] Tests: hop evidence aligned per hop; search finds ticker alias and is tenant-scoped; communities include members; graph_global answer lists communities; /eval/report 200/404.

### Task 2: Frontend scaffold, design tokens, shell

**Files:** Create `frontend/` (Next.js app): `app/layout.tsx`, `app/page.tsx` (home bento: Ask · Explore · Themes · Eval), `app/globals.css` (tokens from design-system.md as CSS variables + Tailwind 4 `@theme`), `lib/api.ts` (typed client), `lib/types.ts`, `components/ui/*` (Button pill, GlassPanel, Card, Chip, Tabs with sliding pill, ThemeToggle, Reveal hook using IntersectionObserver + keyframes), `vitest.config.ts`, `playwright.config.ts`, `.env.example`.
- Fonts via `next/font/google` (Inter Tight, IBM Plex Mono). Top nav = floating glass pill (design-system nav variant).
- [ ] Tests: api client sends X-Tenant and parses errors; theme toggle persists + respects system; Reveal adds no animation under reduced motion.

### Task 3: Ask / Compare + Evidence drawer

**Files:** `app/ask/page.tsx`, `components/ask/*`.
- Prompt pill input with blinking caret; mode selector (rag · hybrid · graph_local · graph_global · auto), compare up to 3 modes side by side (default hybrid vs graph_local).
- Each answer card: text with citation chips coloured by claim verdict (supported / unsupported / unverified), latency, LLM calls, routed mode for auto; graph_local shows the path strip (hop chips, dashed travelling edge animation) with per-hop quotes; graph_global lists communities used.
- Evidence drawer (glass side panel): click a citation → `/chunks/{id}` + `/documents/{doc_id}`, document text with the cited span highlighted and scrolled into view.
- Example questions row (from a small static list of eval questions incl. one multi-hop where graph_local wins).
- [ ] Tests: compare renders per-mode error without blanking others; unknown citation renders unverified chip; verdict colours map correctly; drawer highlights `[start_char,end_char)`.

### Task 4: Graph Explorer

**Files:** `app/explore/page.tsx`, `components/graph/*`.
- Entity search (debounced `/graph/search`), neighbourhood view (SVG + d3-force, node colour by type from a dataviz palette validated for both themes, edge label on hover), click edge → quote + doc link (opens Evidence drawer).
- Path finder: pick two entities → `/graph/path` → highlighted path with travelling dashes, hop list with quotes; empty state when no path.
- List/table view toggle (text alternative + mobile).
- [ ] Tests: neighbourhood cap renders more-indicator; path finder shows no-path state; layout deterministic given seed (positions snapshot within tolerance).

### Task 5: Themes

**Files:** `app/themes/page.tsx`, `components/themes/*`.
- Level-0 communities as cards (title, size, summary with citation chips → Evidence drawer), expand to level-1 children and member chips (→ Explore with entity preselected).
- [ ] Tests: renders summary citations as chips; member chip links to explore with query param.

### Task 6: Eval dashboard

**Files:** `app/eval/page.tsx`, `components/eval/*`.
- Reads `/eval/report`. Headline comparison table in the design-system "highlighted dark column" pattern (modes × categories answer_match with CI; graph_local column highlighted), Δ vs hybrid with significance markers, cost table (p50/p95, LLM calls), graph quality tiles (ring gauges), judge results, caveats block always visible. Every number from the JSON; no hard-coded figures.
- [ ] Tests: table renders values + CI from fixture JSON; caveats present; missing judge section shows "not run".

### Task 7: Polish, accessibility, e2e

**Files:** `frontend/e2e/*.spec.ts`, README updates (run instructions, screenshots).
- Playwright smoke against running backend (desktop 1440 and mobile 390, light and dark): home → ask (hybrid vs graph_local on a multi-hop example) → open evidence → explore path → themes → eval. Screenshots saved to `docs/screenshots/`. Reduced-motion run asserts no running animations.
- Contrast check of tokens (both themes) and keyboard-only pass.
- README: how to start backend + frontend, restart API after `graph build` (Plan 3 lexicon note), screenshots.
- [ ] Controller reviews screenshots visually before sign-off.
