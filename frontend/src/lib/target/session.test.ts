import { expect, it } from "vitest";
import { sessionExtent } from "./session";
import type { WireShot } from "../wire/types";

it("fits outliers and shrinks after removal without mapping missing positions", () => {
  const shots: WireShot[] = [
    { timestamp: 0, xMm: 300, yMm: -200, score: "1", shotId: 1 },
    { timestamp: 1, xMm: null, yMm: 900, score: null, shotId: 2 },
  ];
  const rings = [{ diameterMm: 100, label: "1" }];
  expect(sessionExtent(rings, shots, 4.5)).toBeGreaterThan(300);
  expect(sessionExtent(rings, shots.slice(1), 4.5)).toBeLessThan(100);
  expect(sessionExtent([], [], 4.5)).toBeGreaterThan(0);
});
