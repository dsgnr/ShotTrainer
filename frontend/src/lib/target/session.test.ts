import { expect, it } from "vitest";
import { sessionViewport } from "./session";
import type { WireShot } from "../wire/types";

function shot(xMm: number | null, yMm: number | null): WireShot {
  return { timestamp: 0, xMm, yMm, score: null, shotId: null };
}
const rings = [{ diameterMm: 150, label: "1" }];

it("zooms a tight group without including the outer rings", () => {
  const view = sessionViewport(rings, [shot(-1, 1), shot(0, -1), shot(1, 0)], 4.5);
  expect(view.centre).toEqual([0, 0]);
  expect(view.extentMm).toBe(9);
});

it("centres an off-centre group on coordinate medians", () => {
  const view = sessionViewport(rings, [shot(20, -10), shot(22, -8), shot(24, -6)], 4.5);
  expect(view.centre).toEqual([22, -8]);
  expect(view.extentMm).toBe(9);
});

it("averages the middle coordinates for an even group and centres a single shot", () => {
  expect(sessionViewport(rings, [shot(20, 4), shot(24, 8)], 4.5).centre).toEqual([22, 6]);
  expect(sessionViewport(rings, [shot(30, -15)], 4.5)).toEqual({ centre: [30, -15], extentMm: 9 });
});

it("keeps outliers visible and zooms back in after removing them", () => {
  const group = [shot(0, 0), shot(1, 1), shot(2, 2)];
  const view = sessionViewport(rings, [...group, shot(300, -200), shot(null, 900)], 4.5);
  expect(view.centre).toEqual([1.5, 0.5]);
  expect(view.extentMm).toBeGreaterThan(300 - view.centre[0]);
  expect(sessionViewport(rings, group, 4.5).extentMm).toBeLessThan(view.extentMm);
});

it("fits the face when no shots have positions", () => {
  expect(sessionViewport(rings, [], 4.5)).toEqual({ centre: [0, 0], extentMm: 86.25 });
  expect(sessionViewport(rings, [shot(null, 20)], 4.5)).toEqual(sessionViewport(rings, [], 4.5));
});

it("leaves room for larger projectiles", () => {
  expect(sessionViewport(rings, [shot(0, 0)], 12).extentMm).toBe(24);
});
