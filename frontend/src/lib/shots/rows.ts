import { isFiniteNumber } from "../wire/numbers";
import type { WireShot } from "../wire/types";

const THIN = "\u202f";

export interface ShotRow {
  number: number;
  score: string;
  offset: string;
}

/** The display rows for the shot list, newest handling left to the caller. */
export function shotRows(shots: WireShot[]): ShotRow[] {
  return shots.map((shot, i) => ({
    number: i + 1,
    score: shot.score ?? "-",
    offset: formatOffset(shot.xMm, shot.yMm),
  }));
}

function formatOffset(xMm: WireShot["xMm"], yMm: WireShot["yMm"]): string {
  if (!isFiniteNumber(xMm) || !isFiniteNumber(yMm)) {
    return "Position unavailable";
  }
  return `${signed(xMm)}, ${signed(yMm)}${THIN}mm`;
}

function signed(value: number): string {
  return `${value >= 0 ? "+" : ""}${value.toFixed(1)}`;
}

/**
 * The index after stepping the selection by `delta`. With nothing selected a
 * downward step picks the first shot and an upward step the last. `null` when
 * the list is empty.
 */
export function stepSelection(current: number | null, delta: number, count: number): number | null {
  if (count === 0) {
    return null;
  }
  if (current === null) {
    return delta > 0 ? 0 : count - 1;
  }
  return Math.max(0, Math.min(count - 1, current + delta));
}
