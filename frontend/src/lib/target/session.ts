import type { WireRing, WireShot } from "../wire/types";
import { extentForRings } from "./geometry";

export interface SessionViewport {
  centre: readonly [number, number];
  extentMm: number;
}

function median(values: number[]): number {
  values.sort((a, b) => a - b);
  const middle = Math.floor(values.length / 2);
  return values.length % 2 === 0
    ? (values[middle - 1]! + values[middle]!) / 2
    : values[middle]!;
}

/** Centre on the coordinate medians and fit every positioned shot with padding. */
export function sessionViewport(rings: WireRing[], shots: WireShot[], diameterMm: number): SessionViewport {
  const positions = shots.flatMap((shot) =>
    shot.xMm !== null && shot.yMm !== null ? [[shot.xMm, shot.yMm] as const] : [],
  );
  if (positions.length === 0) return { centre: [0, 0], extentMm: extentForRings(rings) };
  const centre = [median(positions.map(([x]) => x)), median(positions.map(([, y]) => y))] as const;
  let radius = 0;
  for (const [x, y] of positions) {
    radius = Math.max(radius, Math.abs(x - centre[0]), Math.abs(y - centre[1]));
  }
  return { centre, extentMm: Math.max(5, diameterMm * 2, (radius + diameterMm / 2) * 1.3) };
}
