import type { WireRing, WireShot } from "../wire/types";
import { extentForRings } from "./geometry";

/** Fit all positioned shots, including projectile width and marker headroom. */
export function sessionExtent(rings: WireRing[], shots: WireShot[], diameterMm: number): number {
  let extent = extentForRings(rings);
  for (const shot of shots) {
    if (shot.xMm !== null && shot.yMm !== null) {
      extent = Math.max(extent, Math.abs(shot.xMm), Math.abs(shot.yMm));
    }
  }
  return (extent + diameterMm) * 1.2;
}
