// Camera overlay positions in view pixels.
import { finiteOr, finitePair, isFiniteNumber } from "../wire/numbers";
import type { Pair, WireMarker } from "../wire/types";

export interface Rect {
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface Point {
  x: number;
  y: number;
}

export interface Circle extends Point {
  radius: number;
}

/** Markers stay visible however small the camera view is. */
export const MIN_MARKER_RADIUS = 6;

/**
 * Where a frame lands when scaled to fit the view without changing its
 * shape and centred, as `object-fit: contain` draws it. `null` while either
 * size is unknown.
 */
export function fitFrame(
  frameWidth: number,
  frameHeight: number,
  viewWidth: number,
  viewHeight: number,
): Rect | null {
  if (!(frameWidth > 0 && frameHeight > 0 && viewWidth > 0 && viewHeight > 0)) {
    return null;
  }
  const scale = Math.min(viewWidth / frameWidth, viewHeight / frameHeight);
  const width = frameWidth * scale;
  const height = frameHeight * scale;
  return { x: (viewWidth - width) / 2, y: (viewHeight - height) / 2, width, height };
}

/** A point in frame pixels, in view pixels. `null` when it is missing or not finite. */
export function pointInView(fit: Rect, frameWidth: number, point: Pair | null): Point | null {
  const pair = finitePair(point);
  if (pair === null) {
    return null;
  }
  const scale = fit.width / frameWidth;
  return { x: fit.x + pair[0] * scale, y: fit.y + pair[1] * scale };
}

export function markerInView(fit: Rect, frameWidth: number, marker: WireMarker | null): Circle | null {
  if (marker === null || !isFiniteNumber(marker.xPx) || !isFiniteNumber(marker.yPx)) {
    return null;
  }
  const scale = fit.width / frameWidth;
  return {
    x: fit.x + marker.xPx * scale,
    y: fit.y + marker.yPx * scale,
    radius: Math.max(MIN_MARKER_RADIUS, finiteOr(marker.radiusPx, 0) * scale),
  };
}

/** The centre crosshair, with the gap its arms leave around the centre. */
export function reticle(fit: Rect): Circle & { gap: number } {
  const radius = Math.max(20, Math.min(fit.width, fit.height) * 0.05);
  return { x: fit.x + fit.width / 2, y: fit.y + fit.height / 2, radius, gap: radius * 0.35 };
}

/**
 * The dashed tracking region, the given fraction of the frame clamped to
 * between 5 % and the whole. `null` when it covers the whole frame.
 */
export function trackingRegion(fit: Rect, fraction: number): Rect | null {
  const clamped = Math.min(1, Math.max(0.05, fraction));
  if (clamped >= 0.999) {
    return null;
  }
  const width = fit.width * clamped;
  const height = fit.height * clamped;
  return {
    x: fit.x + (fit.width - width) / 2,
    y: fit.y + (fit.height - height) / 2,
    width,
    height,
  };
}
