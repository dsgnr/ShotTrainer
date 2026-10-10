import { expect, it } from "vitest";
import { RECORDED_AIM } from "./recorded-aim";
import { simulatedAim } from "./simulated-aim";

const SHOT_AT = 8.067;

it("repeats the recording exactly for every shot", () => {
  for (const [time, x, y] of RECORDED_AIM) {
    const cycle = 30;
    const seconds = cycle + (time < SHOT_AT ? time + 10 - SHOT_AT : 10 + time - SHOT_AT);
    const [ax, ay] = simulatedAim(seconds);
    expect(ax).toBeCloseTo(x, 6);
    expect(ay).toBeCloseTo(y, 6);
  }
});

it("recoils above and to the left of the target after the shot", () => {
  const follow = Array.from({length: 120}, (_, frame) => simulatedAim(10 + frame / 60));
  expect(Math.min(...follow.map(point => point[1]))).toBeLessThan(-100);
  expect(Math.min(...follow.map(point => point[0]))).toBeLessThan(-100);
});

it("moves continuously through the shot", () => {
  for (let shot = 0; shot < 10; shot++) {
    const before = simulatedAim(shot * 10 + 10 - 0.00001);
    const after = simulatedAim(shot * 10 + 10 + 0.00001);
    expect(Math.hypot(after[0] - before[0], after[1] - before[1])).toBeLessThan(0.1);
  }
});
