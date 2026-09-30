import { expect, it } from "vitest";
import { currentSeries } from "./series";
import { initialShots, reduceShots } from "../stores/shots";
import type { WireShot } from "../wire/types";
const shots: WireShot[] = [0, 0, 1, 1, 2].map((seriesIndex, index) => ({
  seriesIndex, timestamp: index, xMm: index, yMm: 0, score: "9", shotId: index,
}));
it("shows the latest series until a shot in another series is selected", () => {
  expect(currentSeries(shots, null).entries.map(e => e.index)).toEqual([4]);
  expect(currentSeries(shots, 2).entries.map(e => e.index)).toEqual([2, 3]);
  expect(currentSeries(shots, 0).entries.map(e => e.index)).toEqual([0, 1]);
});
it("preserves recorded membership after deleting shots", () => {
  expect(currentSeries(shots.slice(1), 1).entries.map(e => e.shot.shotId)).toEqual([2, 3]);
});
it("groups legacy shots using the session size and tolerates an empty list", () => {
  const legacy = shots.map(({ seriesIndex: _, ...shot }) => shot);
  expect(currentSeries(legacy, null, 2).entries.map(e => e.index)).toEqual([4]);
  expect(currentSeries([], null)).toEqual({ active: 0, entries: [] });
});
it("returns to the latest series when a new shot arrives", () => {
  const state = { ...initialShots, shots: shots.slice(0, 4), selected: 0 };
  const next = reduceShots(state, { type: "shots", shots, group: { count: 5, meanXMm: 0, meanYMm: 0, extremeSpreadMm: 0, meanRadiusMm: 0 }, totalScore: 45 });
  expect(next.selected).toBeNull();
  expect(currentSeries(next.shots, next.selected).active).toBe(2);
});
