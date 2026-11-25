import { describe, expect, it } from "vitest";

type Rgb = [number, number, number];

const hex = (value: string): Rgb => [1, 3, 5].map((start) => parseInt(value.slice(start, start + 2), 16)) as Rgb;

function hsl(hue: number, saturation: number, lightness: number): Rgb {
  const s = saturation / 100;
  const l = lightness / 100;
  const k = (n: number) => (n + hue / 30) % 12;
  const a = s * Math.min(l, 1 - l);
  return [0, 8, 4].map((n) => Math.round(255 * (l - a * Math.max(-1, Math.min(k(n) - 3, 9 - k(n), 1))))) as Rgb;
}

const over = (top: Rgb, alpha: number, bottom: Rgb): Rgb => top.map((channel, index) => channel * alpha + bottom[index] * (1 - alpha)) as Rgb;

function luminance(color: Rgb) {
  const [red, green, blue] = color.map((channel) => {
    const unit = channel / 255;
    return unit <= 0.03928 ? unit / 12.92 : ((unit + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * red + 0.7152 * green + 0.0722 * blue;
}

function ratio(foreground: Rgb, background: Rgb) {
  const [light, dark] = [luminance(foreground), luminance(background)].sort((a, b) => b - a);
  return (light + 0.05) / (dark + 0.05);
}

// Values mirror app/globals.css; a token edit there must be reflected here.
const PAPER = hex("#ffffff");
const FOG = hex("#f4f4f5");
const ASH = hex("#a1a1aa");
const GRAPHITE = hex("#3f3f46");
const CARBON = hex("#18181b");
const BLACK = hex("#0a0a0a");
const INK_NIGHT = hex("#101417");
const MIST = hex("#e4e4e7");
const LIGHT_MUTED = hsl(240, 3.8, 45);

// Nav glass: ink-night at 82% plus a 14% white sheen, worst case over a white page.
const NAV_GLASS = over(PAPER, 0.14, over(INK_NIGHT, 0xd1 / 255, PAPER));

type Pair = { name: string; foreground: Rgb; background: Rgb; min?: number };

const LIGHT: Pair[] = [
  { name: "body text on bg", foreground: CARBON, background: PAPER },
  { name: "body text on surface", foreground: CARBON, background: FOG },
  { name: "secondary text on bg", foreground: GRAPHITE, background: PAPER },
  { name: "secondary text on surface", foreground: GRAPHITE, background: FOG },
  { name: "muted on bg", foreground: LIGHT_MUTED, background: PAPER },
  // tone-fog sections swap muted-fg to fg-2, so muted on fog is only reached by cards on paper sections.
  { name: "muted on surface", foreground: LIGHT_MUTED, background: FOG },
  { name: "verdict ok chip", foreground: hex("#1f6142"), background: hex("#dcece2") },
  { name: "verdict bad chip", foreground: hex("#9b2f22"), background: hex("#f5dfda") },
  { name: "nav text (paper/75) on glass", foreground: over(PAPER, 0.75, NAV_GLASS), background: NAV_GLASS },
  { name: "nav active text on glass", foreground: PAPER, background: over(PAPER, 0.15, NAV_GLASS) },
  { name: "dark panel muted (paper/60) on ink-night", foreground: over(PAPER, 0.6, INK_NIGHT), background: INK_NIGHT },
  { name: "dark panel secondary (paper/80) on ink-night", foreground: over(PAPER, 0.8, INK_NIGHT), background: INK_NIGHT },
  { name: "evidence text (paper/65) on glass-strong over white", foreground: over(PAPER, 0.65, over(INK_NIGHT, 0xe6 / 255, PAPER)), background: over(INK_NIGHT, 0xe6 / 255, PAPER) },
  { name: "ask placeholder (graphite/75) on paper", foreground: over(GRAPHITE, 0.75, PAPER), background: PAPER },
];

const DARK: Pair[] = [
  { name: "body text on bg", foreground: PAPER, background: BLACK },
  { name: "body text on surface", foreground: PAPER, background: CARBON },
  { name: "secondary text on bg", foreground: MIST, background: BLACK },
  { name: "secondary text on surface", foreground: MIST, background: CARBON },
  { name: "muted on bg", foreground: ASH, background: BLACK },
  { name: "muted on surface", foreground: ASH, background: CARBON },
  { name: "verdict ok chip", foreground: hex("#8fd3ac"), background: hex("#1d3428") },
  { name: "verdict bad chip", foreground: hex("#f4a597"), background: hex("#43231e") },
  { name: "nav text (paper/75) on glass", foreground: over(PAPER, 0.75, over(PAPER, 0.14, over(INK_NIGHT, 0xd1 / 255, BLACK))), background: over(PAPER, 0.14, over(INK_NIGHT, 0xd1 / 255, BLACK)) },
];

describe.each([
  ["light", LIGHT],
  ["dark", DARK],
])("%s theme text contrast", (_theme, pairs) => {
  it.each(pairs)("$name >= 4.5:1", ({ foreground, background, min = 4.5 }) => {
    expect(ratio(foreground, background)).toBeGreaterThanOrEqual(min);
  });
});

describe("ratio", () => {
  it("matches the WCAG reference values", () => {
    expect(ratio(hex("#000000"), PAPER)).toBeCloseTo(21, 5);
    expect(ratio(PAPER, PAPER)).toBeCloseTo(1, 5);
  });
});
