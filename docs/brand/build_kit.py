"""Build the NEXUS logo kit (SVG masters) into docs/brand/ and the site's app icon.

Run from the repo root: uv run --with fonttools --with brotli python docs/brand/build_kit.py
"""

from pathlib import Path

from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs" / "brand"
FONT = ROOT / "film" / "composition" / "fonts" / "inter-tight-latin.woff2"

INK = "#101417"
PAPER = "#f4f4f5"
CORAL = "#eb6834"


def mark(fg: str, answer: str) -> str:
    # The N as a three-hop walk: open ring (question) → two entities → coral node (answer).
    # The path starts at the ring's edge so the ring stays hollow on any background.
    return (
        f'<path d="M16 40V16L48 48V16" fill="none" stroke="{fg}" stroke-width="5" '
        'stroke-linecap="round" stroke-linejoin="round"/>'
        f'<circle cx="16" cy="48" r="6" fill="none" stroke="{fg}" stroke-width="4"/>'
        f'<circle cx="16" cy="16" r="4.5" fill="{fg}"/>'
        f'<circle cx="48" cy="48" r="4.5" fill="{fg}"/>'
        f'<circle cx="48" cy="16" r="7" fill="{answer}"/>'
    )


def wordmark(text: str, size: float, tracking: float) -> tuple[str, float]:
    """Outlined glyph paths for `text` at `size` px (baseline at y=0) and the total advance."""
    font = TTFont(FONT)
    font = instantiateVariableFont(font, {"wght": 500})
    glyphs, cmap = font.getGlyphSet(), font.getBestCmap()
    scale = size / font["head"].unitsPerEm
    paths, x = [], 0.0
    for index, char in enumerate(text):
        name = cmap[ord(char)]
        pen = SVGPathPen(glyphs)
        glyphs[name].draw(TransformPen(pen, (scale, 0, 0, -scale, x, 0)))
        paths.append(pen.getCommands())
        x += glyphs[name].width * scale + (tracking * size if index < len(text) - 1 else 0)
    return " ".join(paths), x


def svg(width: float, height: float, body: str, title: str) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width:g} {height:g}" '
        f'width="{width:g}" height="{height:g}" role="img" aria-label="{title}">'
        f"<title>{title}</title>{body}</svg>\n"
    )


def lockup(fg: str) -> str:
    # Mark 64 high; cap height of the wordmark sits at about half the mark, tracked like the site nav.
    text, advance = wordmark("NEXUS", 30, 0.16)
    cap = 30 * 0.73
    gap, pad = 18, 4
    width = pad + 64 + gap + advance + pad
    baseline = 32 + cap / 2
    body = (
        f'<g transform="translate({pad} 0)">{mark(fg, CORAL)}</g>'
        f'<path transform="translate({pad + 64 + gap:.2f} {baseline:.2f})" d="{text}" fill="{fg}"/>'
    )
    return svg(round(width, 2), 64, body, "NEXUS")


def app_icon() -> str:
    body = f'<rect width="64" height="64" rx="14" fill="{INK}"/><g transform="translate(8 8) scale(.75)">{mark(PAPER, CORAL)}</g>'
    return svg(64, 64, body, "NEXUS")


FILES = {
    OUT / "nexus-mark-dark.svg": svg(64, 64, mark(PAPER, CORAL), "NEXUS"),
    OUT / "nexus-mark-light.svg": svg(64, 64, mark(INK, CORAL), "NEXUS"),
    OUT / "nexus-mark-mono.svg": svg(64, 64, mark("currentColor", "currentColor"), "NEXUS"),
    OUT / "nexus-lockup-dark.svg": lockup(PAPER),
    OUT / "nexus-lockup-light.svg": lockup(INK),
    OUT / "nexus-app-icon.svg": app_icon(),
    ROOT / "frontend" / "app" / "icon.svg": app_icon(),
}

for path, content in FILES.items():
    path.write_text(content, encoding="utf-8")
    print(path.relative_to(ROOT))
