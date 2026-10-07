import { expect, it } from "vitest";
import { ROW_HEIGHT, SERIES_HEIGHT, itemHeight, layoutShots, visibleRange } from "./layout";
import type { WireShot } from "../wire/types";

function shots(count: number): WireShot[] {
  return Array.from({ length: count }, (_, i) => ({ timestamp: i, xMm: 0, yMm: 0, score: "9", shotId: i }));
}

it("places a series header before the first shot of each series", () => {
  const layout = layoutShots(shots(5), 2);
  expect(layout.items.map(item => `${item.kind}${item.index}`)).toEqual(
    ["series0", "shot0", "shot1", "series2", "shot2", "shot3", "series4", "shot4"]);
  expect(layout.shotTops).toEqual([
    SERIES_HEIGHT,
    SERIES_HEIGHT + ROW_HEIGHT,
    2 * SERIES_HEIGHT + 2 * ROW_HEIGHT,
    2 * SERIES_HEIGHT + 3 * ROW_HEIGHT,
    3 * SERIES_HEIGHT + 4 * ROW_HEIGHT,
  ]);
  expect(layout.height).toBe(3 * SERIES_HEIGHT + 5 * ROW_HEIGHT);
});

it("starts a new header when stored series indexes change, not on a fixed size", () => {
  const stored = [0, 0, 3, 3, 0].map((seriesIndex, i) => ({ ...shots(5)[i]!, seriesIndex }));
  const layout = layoutShots(stored, 10);
  expect(layout.items.filter(item => item.kind === "series").map(item => item.index)).toEqual([0, 2, 4]);
  expect(new Set(layout.items.map(item => `${item.kind}${item.index}`)).size).toBe(layout.items.length);
});

it("lays out no items for no shots", () => {
  expect(layoutShots([], 10)).toEqual({ items: [], shotTops: [], height: 0 });
  expect(visibleRange([], 0, 400)).toEqual({ start: 0, end: 0 });
});

it("renders the viewport with an overscan and no more", () => {
  const { items, height } = layoutShots(shots(3000), 10);
  const viewport = 10 * ROW_HEIGHT;

  const top = visibleRange(items, 0, viewport);
  expect(top.start).toBe(0);
  expect(top.end).toBeLessThan(40);

  const middle = visibleRange(items, height / 2, viewport);
  expect(middle.start).toBeGreaterThan(0);
  expect(middle.end - middle.start).toBeLessThan(45);
  const first = items[middle.start]!;
  const last = items[middle.end - 1]!;
  expect(first.top + itemHeight(first)).toBeLessThanOrEqual(height / 2);
  expect(last.top).toBeGreaterThanOrEqual(height / 2 + viewport);

  const bottom = visibleRange(items, height - viewport, viewport);
  expect(bottom.end).toBe(items.length);
});

it("keeps the item at the scroll offset inside the range", () => {
  const { items, shotTops } = layoutShots(shots(500), 10);
  for (const index of [0, 1, 9, 10, 250, 499]) {
    const { start, end } = visibleRange(items, shotTops[index]!, ROW_HEIGHT);
    const rendered = items.slice(start, end).some(item => item.kind === "shot" && item.index === index);
    expect(rendered).toBe(true);
  }
});
