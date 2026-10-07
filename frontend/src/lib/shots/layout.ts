import type { WireShot } from "../wire/types";
import { seriesIndex } from "./series";

/** Row heights in pixels. The shot list sets the matching CSS custom properties from these. */
export const ROW_HEIGHT = 28;
export const SERIES_HEIGHT = 28;

/** Items rendered beyond each edge of the viewport. */
const OVERSCAN = 10;

export type ListItem =
  /** `index` is the first shot of the series. */
  | { kind: "series"; index: number; series: number; top: number }
  | { kind: "shot"; index: number; top: number };

export interface ShotLayout {
  items: ListItem[];
  /** The top offset of each shot's row, by shot index. */
  shotTops: number[];
  height: number;
}

export function itemHeight(item: ListItem): number {
  return item.kind === "series" ? SERIES_HEIGHT : ROW_HEIGHT;
}

/** A series header precedes the first shot of each run of shots with the same series. */
export function layoutShots(shots: WireShot[], size: number): ShotLayout {
  const items: ListItem[] = [];
  const shotTops: number[] = [];
  let top = 0;
  let previous: number | null = null;
  shots.forEach((shot, index) => {
    const series = seriesIndex(shot, index, size);
    if (series !== previous) {
      items.push({ kind: "series", index, series, top });
      top += SERIES_HEIGHT;
      previous = series;
    }
    items.push({ kind: "shot", index, top });
    shotTops.push(top);
    top += ROW_HEIGHT;
  });
  return { items, shotTops, height: top };
}

/** The half-open range of `items` to render for the viewport, widened by the overscan. */
export function visibleRange(
  items: ListItem[],
  scrollTop: number,
  viewport: number,
): { start: number; end: number } {
  let lo = 0;
  let hi = items.length;
  while (lo < hi) {
    const mid = (lo + hi) >> 1;
    const item = items[mid]!;
    if (item.top + itemHeight(item) <= scrollTop) lo = mid + 1;
    else hi = mid;
  }
  const first = lo;
  const bottom = scrollTop + viewport;
  hi = items.length;
  while (lo < hi) {
    const mid = (lo + hi) >> 1;
    if (items[mid]!.top < bottom) lo = mid + 1;
    else hi = mid;
  }
  return { start: Math.max(0, first - OVERSCAN), end: Math.min(items.length, lo + OVERSCAN) };
}
