# NEXUS Design System

Design language derived from https://monveo.app (reverse-engineered 2026-11-24 from its compiled CSS + live computed styles). We adopt tokens, typography, layout rhythm and motion — **not** its name, logo, imagery or copy.

Source facts: Next.js + Tailwind (shadcn-style HSL vars); no JS animation library — all motion is CSS `@keyframes` triggered by `IntersectionObserver`; every animated element has a `prefers-reduced-motion` opt-out.

## 1. Color

Neutral zinc ramp, near-monochrome UI; colour only from one deep-blue accent and data.

| Token | Value | Use |
|---|---|---|
| `--paper` | `#ffffff` | page bg (light) |
| `--fog` | `#f4f4f5` | alternate section / panel bg |
| `--mist` | `#e4e4e7` | borders, table stripes |
| `--ash` | `#a1a1aa` | muted icons, disabled |
| `--graphite` | `#3f3f46` | secondary text on light |
| `--carbon` | `#18181b` | primary text, dark surfaces |
| `--black` | `#0a0a0a` | deepest surface |
| `--ink-night` | `#101417` | dark band (testimonial-style) |
| `--accent` | `#17445f` | hero / focus band, primary accent |
| `--accent-deep` | `#173d58` | accent hover / final band |
| `--muted-fg` | `hsl(240 3.8% 45%)` | body-secondary text |
| `--ring` | `hsl(215 25% 27%)` | focus ring |

Evidence tokens (NEXUS additions, AA-checked on their chip backgrounds):

| Token | Light | Dark | Use |
|---|---|---|---|
| `--verdict-ok` / `--verdict-ok-bg` | `#1f6142` / `#dcece2` | `#8fd3ac` / `#1d3428` | citation chip, claim supported |
| `--verdict-bad` / `--verdict-bad-bg` | `#9b2f22` / `#f5dfda` | `#f4a597` / `#43231e` | citation chip, claim unsupported |
| (unverified) | dashed `--ash` border, `--fg-2` text | same | claim null or citation not in hits |
| `--highlight` | `#7fb2d638` | `#7fb2d642` | cited `[start_char,end_char)` span in the evidence drawer |

Data colours (graph node types, mode series) are NEXUS additions — choose with the `dataviz` skill, validated for both themes; keep saturation low to sit inside the zinc UI.

Graph node types (dataviz slots 1–3; `validate_palette.js --pairs all` passes on `#ffffff` light and `#101417` dark — CVD ΔE ≥ 9.2, normal ≥ 20.9). Five types cannot all clear the all-pairs floors, so the two context types are neutral and hollow; every type also has its own shape:

| Token | Light | Dark / `[data-surface="dark"]` | Type · shape |
|---|---|---|---|
| `--node-company` | `#2a78d6` | `#3987e5` | Company · rounded square |
| `--node-person` | `#eb6834` | `#d95926` | Person · circle |
| `--node-group` | `#1baf7a` | `#199e70` | Group · diamond |
| (neutral) | `--ash` outline | same | Sector · hollow diamond; Location · hollow circle |

The graph canvas is always dark, so it always takes the dark steps. Light group green is 2.8:1 on paper; it only appears as a swatch next to a text label.

Dark theme: swap `paper↔black`, `fog↔carbon`, text `carbon↔paper`; accent unchanged. Light is default; toggle persisted per viewer.

## 2. Typography

| Role | Family | Size / line-height | Weight | Tracking |
|---|---|---|---|---|
| display | Inter Tight | 66 / 1.0 (56 on small) | 400 | -0.02em |
| heading-lg | Inter Tight | 45 / 1.13 | 400 | -0.02em |
| heading | Inter Tight | 30 / 1.2 | 400 | -0.01em |
| heading-sm | Inter Tight | 22 / 1.25 | 400 | 0 |
| subheading | Inter Tight | 19 / 1.4 | 400 | 0 |
| body-lg | Inter Tight | 17 / 1.4 | 400 | 0 |
| body | Inter Tight | 15 / 1.5 | 400 | 0 |
| ui | Inter Tight | 13 / 1.4 | 400–500 | 0 |
| caption | Inter Tight | 11 / 1.5 | 400 | 0 |
| mono | IBM Plex Mono | 13 / 1.5 | 400 | 0 |

Signature: **large, light (400) headings** — never bold display. Medium 500 only for small emphasis (table column titles, active nav). Mono for chunk IDs, entity IDs, Cypher, scores, latency numbers. Load both via `next/font/google`.

## 3. Shape, space, depth

- Radii: pill `999px` (buttons, chips, toggles) · card `20px` · inner panel `14–16px` · control `12px` · small `9px`.
- Section padding `104px` top on desktop; headline-left + supporting paragraph-right split header (≈ 60/40) above content.
- Content width ≈ 1140px; app shell full-bleed with 12px outer inset rounded frame (hero style) where it fits.
- Shadows soft and large: `0 18px 48px #0f172a24`, `0 24px 80px …`; cards mostly flat with no border on light bg.
- **Glass panel** (overlays on graph canvas, floating nav, mode toggle):
  `backdrop-filter: blur(22px) saturate(125%); background: #0e0e0e47; border: 1px solid #ffffff2e; border-radius: 16px; box-shadow: inset 0 1px #ffffff29, 0 16px 36px #00000021;`
  Floating nav variant: `blur(28px) saturate(135%)`, `linear-gradient(135deg, #ffffff2e, #1111118a)`, pill radius.

## 4. Components (mapped to NEXUS)

| Monveo pattern | NEXUS use |
|---|---|
| Pill buttons, white on dark / carbon on light, `0 22px` padding, 15px | primary actions (Ask, Run eval) |
| Glass list card over imagery ("Today's spending" rows) | retrieved-evidence list floating over graph canvas |
| Goal-progress rows with ring % | eval metric rows (recall@k, F1) with ring gauge |
| **Comparison table with highlighted dark column** | **RAG vs Hybrid vs GraphRAG** results table; winning/selected mode = dark column |
| Dashed network lines with travelling dashes | graph edges / highlighted multi-hop path animation |
| Overlapping circles (Venn) chips | community / theme overlap view |
| AI prompt pill with blinking cursor | Ask input + streaming answer caret |
| Bento grid of feature cards | Home dashboard (Ask · Explore · Themes · Eval entry cards) |
| Vertical marquee testimonials | (skip) |
| FAQ auto-advance with progress bar (`scaleX` timer) | (skip unless needed) |

## 5. Motion

Primary easing — ease-out-expo: `--ease-out: cubic-bezier(.16,1,.3,1)`.
Secondary: `--ease-soft: cubic-bezier(.2,.8,.2,1)` (nav/content reveals), `--ease-in-out: cubic-bezier(.65,0,.35,1)` (loops), `--ease-std: cubic-bezier(.4,0,.2,1)` (hover).

| Name | Keyframes | Timing | NEXUS use |
|---|---|---|---|
| `fadeUp` | opacity 0→1, translateY 18→0 | .7s both | section / panel entry |
| `navReveal` | opacity 0→1, translateY -14→0 | .8s ease-soft .1s | top nav on load |
| `contentReveal` | opacity 0→1, translateY 12→0 | 1s ease-soft .25s | page header |
| `overlayIn` | opacity 0→1, translateY 22→0 | .72s ease-out (+70ms stagger) | glass overlays, answer cards |
| `itemIn` | opacity 0→1, translateY -9→0, scale .98→1 | .52s ease-out | streamed evidence rows, list inserts |
| `itemReveal` | opacity 0→1(or .76 muted), translateY 16→0, scale .97→1 | .58s ease-out | metric rows, muted vs active |
| `heroSettle` | opacity 0→1, scale 1.05→1 | ~1s ease-out | graph canvas first paint |
| `flowTravel` | `stroke-dashoffset` → -52px | 7s linear infinite | active path edges (dashed, `stroke #ffffff6b`, 1.25px, round caps) |
| `flowPulse` | opacity .38↔1, scale .76↔1.18 | 2.4s ease-out infinite | path nodes being traversed |
| `cursorBlink` | opacity 1 (0–45%) / 0 | .78s step-end infinite | streaming answer caret |
| `timer` | scaleX 0→1 | linear | eval run progress bar |

Durations for hover/state: 150ms (default), 200, 300, 500ms. Reveal on enter-viewport via `IntersectionObserver` (one shared hook), not scroll libraries. Every animation listed above sets `animation: none` under `prefers-reduced-motion: reduce`.

App-level micro-interactions (thinking state, reasoning stream, streaming text, skeleton reveal, sliding tabs, toasts) come from the `transitions-dev` skill, re-tokenised to the easings above.

## 6. Imagery

Monveo uses cinematic photo backgrounds. NEXUS does not copy those; its "hero image" is the live knowledge graph itself (dark canvas, light nodes, dashed animated paths), with glass panels floating over it.
