# NEXUS logo

The mark is the letter N drawn as a three-hop walk through the graph: an open ring (the question), two entities, and a coral node (the answer). It is the same shape as the path NEXUS shows for every multi-hop answer.

| File | Use |
|---|---|
| `nexus-lockup-light.svg` / `nexus-lockup-dark.svg` | Mark + wordmark, for light / dark backgrounds |
| `nexus-mark-light.svg` / `nexus-mark-dark.svg` | Mark only |
| `nexus-mark-mono.svg` | One colour (`currentColor`), for single-ink use |
| `nexus-app-icon.svg`, `nexus-app-icon-512.png`, `nexus-app-icon-1024.png` | Rounded app icon on ink |

The site uses `frontend/app/icon.svg`, `favicon.ico` (16/32/48) and `apple-icon.png` (180), and draws the mark inline in `components/site/logo-mark.tsx`.

## Tagline

**Answers that show their path.** Used as the landing hero headline, under the README logo and beside the mark in the site footer.

## Colours and type

| Role | Value |
|---|---|
| Ink | `#101417` |
| Paper | `#f4f4f5` |
| Answer node | `#eb6834` |

The wordmark is Inter Tight 500, tracked at 0.16 em, outlined to paths so it renders without the font installed.

## Rules

- Keep clear space of at least the coral node's diameter around the mark.
- The coral node is the only colour accent; don't recolour the rest of the mark beyond ink, paper or one colour.
- Below 24 px, use the mark without the wordmark.

## Rebuild

```bash
uv run --with fonttools --with brotli python docs/brand/build_kit.py
```

This regenerates the SVGs and `frontend/app/icon.svg`. The PNG icons and `favicon.ico` are rendered from `nexus-app-icon.svg`.
