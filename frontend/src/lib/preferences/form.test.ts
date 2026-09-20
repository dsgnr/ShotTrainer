import { describe, expect, it } from "vitest";

import { SAMPLE_PREFERENCES } from "../wire/samples";
import type { WirePreferences } from "../wire/types";
import { NUMBER_RANGES, ROTATIONS, clampPreferences } from "./form";

describe("NUMBER_RANGES", () => {
  it("pins each field to the controller's validated range", () => {
    expect(NUMBER_RANGES).toEqual({
      cameraBrightness: [-100, 100],
      cameraContrast: [0.5, 2],
      audioGain: [0.1, 10],
      shotThreshold: [0.01, 1],
      shotRefractoryMs: [50, 5000],
      preShotMs: [0, 10000],
      postShotMs: [0, 10000],
      releaseWindowMs: [50, 2000],
      shotDiameterMm: [0.5, 25],
      trackingRegionFraction: [0.1, 1],
      circleDiameterMm: [5, 1000],
    });
  });
});

describe("clampPreferences", () => {
  it("leaves valid preferences unchanged", () => {
    expect(clampPreferences(SAMPLE_PREFERENCES)).toEqual(SAMPLE_PREFERENCES);
  });

  it("keeps a null camera as no camera", () => {
    const prefs: WirePreferences = { ...SAMPLE_PREFERENCES, cameraId: null };
    expect(clampPreferences(prefs).cameraId).toBeNull();
  });

  it("clamps a camera id to zero or above", () => {
    expect(clampPreferences({ ...SAMPLE_PREFERENCES, cameraId: -4 }).cameraId).toBe(0);
  });

  it("clamps each numeric field to its range", () => {
    const low: WirePreferences = {
      ...SAMPLE_PREFERENCES,
      cameraBrightness: -1000,
      cameraContrast: 0,
      audioGain: 0,
      shotThreshold: 0,
      shotRefractoryMs: 0,
      preShotMs: -10,
      postShotMs: -10,
      releaseWindowMs: 0,
      shotDiameterMm: 0,
      trackingRegionFraction: 0,
      circleDiameterMm: 0,
    };
    const clamped = clampPreferences(low);
    for (const [field, [min]] of Object.entries(NUMBER_RANGES)) {
      expect(clamped[field as keyof WirePreferences], field).toBe(min);
    }
  });

  it("clamps high values to the maximum", () => {
    const high: WirePreferences = {
      ...SAMPLE_PREFERENCES,
      cameraBrightness: 1000,
      cameraContrast: 100,
      audioGain: 100,
      shotThreshold: 100,
      shotRefractoryMs: 999999,
      preShotMs: 999999,
      postShotMs: 999999,
      releaseWindowMs: 999999,
      shotDiameterMm: 999,
      trackingRegionFraction: 9,
      circleDiameterMm: 999999,
    };
    const clamped = clampPreferences(high);
    for (const [field, [, max]] of Object.entries(NUMBER_RANGES)) {
      expect(clamped[field as keyof WirePreferences], field).toBe(max);
    }
  });

  it("keeps an allowed rotation and falls back to zero otherwise", () => {
    expect(ROTATIONS).toEqual([0, 90, 180, 270]);
    expect(clampPreferences({ ...SAMPLE_PREFERENCES, cameraRotation: 180 }).cameraRotation).toBe(180);
    expect(clampPreferences({ ...SAMPLE_PREFERENCES, cameraRotation: 45 }).cameraRotation).toBe(0);
    expect(clampPreferences({ ...SAMPLE_PREFERENCES, cameraRotation: 999 }).cameraRotation).toBe(0);
  });
});
