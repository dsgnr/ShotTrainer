import type { WireShot } from "../wire/types";

export function seriesIndex(shot: WireShot, index: number, size = 10): number {
  return shot.seriesIndex ?? Math.floor(index / Math.max(1, size));
}

export function currentSeries(shots: WireShot[], selected: number | null, size = 10) {
  const entries = shots.map((shot, index) => ({ shot, index, series: seriesIndex(shot, index, size) }));
  const active = entries[selected ?? -1]?.series ?? entries.at(-1)?.series ?? 0;
  return { active, entries: entries.filter(entry => entry.series === active) };
}
