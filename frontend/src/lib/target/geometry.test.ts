import { describe, expect, it } from "vitest";

import {
  ZOOM_MAX_MM,
  ZOOM_MIN_MM,
  extentForRings,
  extentFromRatio,
  ratioFromExtent,
  targetScale,
  wheelFactor,
} from "./geometry";

describe("extentForRings", () => {
  it("fits the largest ring with 15 % headroom", () => {
    expect(extentForRings([{ diameterMm: 100, label: null }])).toBeCloseTo(57.5);
  });

  it("falls back to the default extent for no rings", () => {
    expect(extentForRings([])).toBe(90);
  });
});

describe("logarithmic zoom", () => {
  it("maps the slider ends to the extent range", () => {
    expect(extentFromRatio(0)).toBeCloseTo(ZOOM_MIN_MM);
    expect(extentFromRatio(1)).toBeCloseTo(ZOOM_MAX_MM);
  });

  it("maps the midpoint to the geometric mean", () => {
    expect(extentFromRatio(0.5)).toBeCloseTo(Math.sqrt(ZOOM_MIN_MM * ZOOM_MAX_MM));
  });

  it("round-trips an extent through its ratio", () => {
    for (const extent of [ZOOM_MIN_MM, 42, 150, ZOOM_MAX_MM]) {
      expect(extentFromRatio(ratioFromExtent(extent))).toBeCloseTo(extent);
    }
  });

  it("clamps an out-of-range extent before taking its ratio", () => {
    expect(ratioFromExtent(1)).toBe(0);
    expect(ratioFromExtent(9000)).toBe(1);
  });
});

describe("targetScale", () => {
  it("gives pixels per mm for the padded square", () => {
    expect(targetScale(216, 90)).toBeCloseTo((216 - 16) / (2 * 90));
  });
});

describe("wheelFactor", () => {
  it("zooms in on a scroll up and out on a scroll down", () => {
    expect(wheelFactor(120)).toBe(0.9);
    expect(wheelFactor(-120)).toBe(1.1);
  });
});
