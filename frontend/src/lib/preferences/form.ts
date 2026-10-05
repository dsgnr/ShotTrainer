// Preferences validation. The controller validates preferences too, so these
// ranges keep the dialog from sending a value the controller would reject and
// replace with a default.
import type { WirePreferences } from "../wire/types";

/** Allowed camera rotations in degrees, clockwise. */
export const ROTATIONS = [0, 90, 180, 270] as const;

type NumberField =
  | "cameraBrightness"
  | "cameraContrast"
  | "audioGain"
  | "shotThreshold"
  | "shotRefractoryMs"
  | "preShotMs"
  | "postShotMs"
  | "releaseWindowMs"
  | "shotDiameterMm"
  | "trackingRegionFraction"
  | "circleDiameterMm";

/** Inclusive `[min, max]` ranges for each numeric preference. */
export const NUMBER_RANGES: Record<NumberField, [number, number]> = {
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
};

function clamp(value: number, [min, max]: [number, number]): number {
  return Math.min(max, Math.max(min, value));
}

/** The preferences with every value brought into its valid range. */
export function clampPreferences(prefs: WirePreferences): WirePreferences {
  const next: WirePreferences = { ...prefs };
  for (const field of Object.keys(NUMBER_RANGES) as NumberField[]) {
    next[field] = clamp(prefs[field], NUMBER_RANGES[field]);
  }
  next.cameraId = prefs.cameraId === null ? null : Math.max(0, Math.round(prefs.cameraId));
  next.cameraRotation = (ROTATIONS as readonly number[]).includes(prefs.cameraRotation)
    ? prefs.cameraRotation
    : 0;
  return next;
}
