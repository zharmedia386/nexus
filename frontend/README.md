# NEXUS frontend

Single-page Next.js 16 / React 19 / Tailwind 4 UI (hero, Ask, Explore, Themes, Eval) over the NEXUS FastAPI backend. See the [root README](../README.md) for the whole system.

## Setup

Needs Node >= 22 (developed on Node 26; on macOS use `export PATH=/opt/homebrew/bin:$PATH`).

```bash
cp .env.example .env.local   # optional
npm i && npm run dev         # http://localhost:3000
```

| Variable | Default |
| --- | --- |
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` |
| `NEXT_PUBLIC_TENANT` | `demo` |

The API must allow the UI origin via its `CORS_ORIGINS` setting (default `http://localhost:3000,http://127.0.0.1:3000`).

## Checks

```bash
npm run lint && npm run typecheck && npm run test && npm run build
```

## End-to-end

Needs the API on :8000. Playwright starts `npm run start` on :3000 (or reuses it), so build first.

```bash
npx playwright install chromium   # first run only
npm run e2e
```

The run also rewrites the screenshots in `../docs/screenshots`.
