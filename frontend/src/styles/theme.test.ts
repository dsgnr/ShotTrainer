import { describe, expect, it } from "vitest";

import css from "./theme.css?raw";

type Tokens = Record<string, string>;

function tokensIn(block: string): Tokens {
  const tokens: Tokens = {};
  for (const match of block.matchAll(/--([\w-]+):\s*([^;]+);/g)) {
    const [, name, value] = match;
    if (name !== undefined && value !== undefined) {
      tokens[name] = value.trim();
    }
  }
  return tokens;
}

const lightStart = css.indexOf("@media (prefers-color-scheme: light)");
const motionStart = css.indexOf("@media (prefers-reduced-motion: reduce)");
const dark = tokensIn(css.slice(0, lightStart));
const light = { ...dark, ...tokensIn(css.slice(lightStart, motionStart)) };

function luminance(hex: string): number {
  const match = /^#([0-9a-f]{6})$/i.exec(hex);
  if (match?.[1] === undefined) {
    throw new Error(`${hex} is not a six digit hex colour`);
  }
  const value = Number.parseInt(match[1], 16);
  const [r, g, b] = [value >> 16, (value >> 8) & 0xff, value & 0xff].map((channel) => {
    const c = channel / 255;
    return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  }) as [number, number, number];
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

function contrast(foreground: string, background: string): number {
  const [high, low] = [luminance(foreground), luminance(background)].sort((a, b) => b - a) as [
    number,
    number,
  ];
  return (high + 0.05) / (low + 0.05);
}

// WCAG AA. Text needs 4.5, and graphics the user must see need 3.
const PAIRS: [string, string, number][] = [
  ["text", "bg", 4.5],
  ["text", "panel", 4.5],
  ["text-heading", "bg", 4.5],
  ["text-dim", "bg", 4.5],
  ["text-dim", "panel", 4.5],
  ["on-accent", "accent", 4.5],
  ["on-accent", "accent-hover", 4.5],
  ["focus", "bg", 3],
  ["focus", "panel", 3],
  ["tone-info", "bg", 4.5],
  ["tone-success", "bg", 4.5],
  ["tone-warning", "bg", 4.5],
  ["tone-error", "bg", 4.5],
  ["pill-idle", "bg", 4.5],
  ["pill-recording", "bg", 4.5],
  ["pill-replay", "bg", 4.5],
  ["target-ring", "target-face", 3],
  ["target-label", "target-face", 4.5],
  ["target-shot", "target-face", 3],
  ["target-live-aim", "target-face", 3],
  ["target-hold-zone", "target-face", 3],
  ["trace-approach", "target-face", 3],
  ["trace-release", "target-face", 3],
  ["trace-follow", "target-face", 3],
];

describe("theme tokens", () => {
  for (const [scheme, tokens] of [
    ["dark", dark],
    ["light", light],
  ] as const) {
    it.each(PAIRS)(`${scheme}: %s on %s reaches %d to 1`, (foreground, background, minimum) => {
      const fg = tokens[foreground];
      const bg = tokens[background];
      expect(fg, foreground).toBeDefined();
      expect(bg, background).toBeDefined();
      expect(contrast(fg ?? "", bg ?? "")).toBeGreaterThanOrEqual(minimum);
    });
  }

  it("gives the light scheme its own value for every colour", () => {
    const colours = Object.keys(dark).filter((name) => dark[name]?.startsWith("#"));
    const overridden = tokensIn(css.slice(lightStart, motionStart));
    expect(colours.filter((name) => !(name in overridden))).toEqual([]);
  });

  it("stops animations and transitions when reduced motion is asked for", () => {
    const motion = css.slice(motionStart);
    expect(motion).toContain("animation-duration: 0.01ms !important");
    expect(motion).toContain("transition-duration: 0.01ms !important");
  });
});
