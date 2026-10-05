import type { F64, Pair } from "./types";

export function isFiniteNumber(value: F64 | undefined): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

/** The pair as two finite numbers, or `null` when either is missing. */
export function finitePair(pair: Pair | null | undefined): [number, number] | null {
  if (pair === null || pair === undefined) {
    return null;
  }
  const [x, y] = pair;
  return isFiniteNumber(x) && isFiniteNumber(y) ? [x, y] : null;
}

export function finiteOr(value: F64 | undefined, fallback: number): number {
  return isFiniteNumber(value) ? value : fallback;
}
