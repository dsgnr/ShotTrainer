// Target-space geometry: the visible extent, the pixel scale and the zoom range.
import type { WireRing } from "../wire/types";

/** Default half-width of the view in mm when no rings are set. */
export const DEFAULT_EXTENT_MM = 90;

/** Zoom range in mm, from fully zoomed in to fully zoomed out. */
export const ZOOM_MIN_MM = 5;
export const ZOOM_MAX_MM = 500;

/** The visible extent that fits the largest ring with 15 % headroom. */
export function extentForRings(rings: WireRing[]): number {
  let largest = 0;
  for (const ring of rings) {
    if (ring.diameterMm !== null && ring.diameterMm > largest) {
      largest = ring.diameterMm;
    }
  }
  return largest > 0 ? (largest / 2) * 1.15 : DEFAULT_EXTENT_MM;
}

/** Pixels per mm for a square view of `size` pixels, with 8 px padding each side. */
export function targetScale(size: number, extentMm: number): number {
  return (size - 16) / (2 * extentMm);
}

/** The extent in mm for a slider ratio from 0 (zoomed in) to 1 (zoomed out). */
export function extentFromRatio(ratio: number): number {
  return ZOOM_MIN_MM * (ZOOM_MAX_MM / ZOOM_MIN_MM) ** ratio;
}

/** The slider ratio for an extent, clamped to the zoom range first. */
export function ratioFromExtent(extentMm: number): number {
  const clamped = Math.min(ZOOM_MAX_MM, Math.max(ZOOM_MIN_MM, extentMm));
  return Math.log(clamped / ZOOM_MIN_MM) / Math.log(ZOOM_MAX_MM / ZOOM_MIN_MM);
}

/** The multiplier a wheel step applies to the extent. Scroll up zooms in. */
export function wheelFactor(deltaY: number): number {
  return deltaY > 0 ? 0.9 : 1.1;
}
