import { expect, it } from "vitest";
import { simulatedAim } from "./simulated-aim";

it("gives each shot its own trace", () => {
  const second = (shot: number) => simulatedAim(shot * 10 - 3);
  const points = [1, 2, 3, 4, 5, 6, 7].map(second);
  for (const [i, a] of points.entries()) {
    for (const b of points.slice(i + 1)) expect(Math.hypot(a[0] - b[0], a[1] - b[1])).toBeGreaterThan(0.5);
  }
});

it("recoils well away from the shot point after every shot", () => {
  for (let shot = 1; shot < 8; shot++) {
    const start = simulatedAim(shot * 10);
    const furthest = Math.max(...Array.from({length: 110}, (_, frame) => {
      const [x, y] = simulatedAim(shot * 10 + frame / 60);
      return Math.hypot(x - start[0], y - start[1]);
    }));
    expect(furthest).toBeGreaterThan(80);
  }
});

it("moves continuously through the shot", () => {
  for (let shot = 0; shot < 10; shot++) {
    const before = simulatedAim(shot * 10 + 10 - 0.00001);
    const after = simulatedAim(shot * 10 + 10 + 0.00001);
    expect(Math.hypot(after[0] - before[0], after[1] - before[1])).toBeLessThan(0.1);
  }
});
