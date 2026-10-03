import { expect, it } from "vitest";
import { simulatedAim } from "./simulated-aim";

it("settles into a compact hold after an off-target approach and recoils rapidly", () => {
  const shots = Array.from({length: 10}, (_, shot) => {
    const t = shot * 10;
    const trigger = simulatedAim(t + 10);
    const distance = (point: [number, number]) => Math.hypot(point[0] - trigger[0], point[1] - trigger[1]);
    const entry = simulatedAim(t + (shot === 0 ? 0 : 1.5));
    expect(Math.hypot(...entry)).toBeGreaterThan(85);
    expect(entry[0]).toBeLessThan(-60);
    expect(entry[1]).toBeGreaterThan(60);
    expect(distance(entry)).toBeLessThan(110);
    expect(entry[1]).toBeGreaterThan(trigger[1] + 25);
    for (let frame = 0; frame <= 30; frame++) {
      expect(distance(simulatedAim(t + 9.5 + frame / 60))).toBeLessThan(10);
    }
    const holdX = Array.from({length: 121}, (_, frame) => simulatedAim(t + 7 + frame / 60)[0]);
    expect(Math.max(...holdX) - Math.min(...holdX)).toBeGreaterThan(4);
    const release = Array.from({length: 16}, (_, frame) => distance(simulatedAim(t + 9.75 + frame / 60)));
    expect(Math.max(...release)).toBeGreaterThan(3);
    expect(distance(simulatedAim(t + 10.025))).toBeGreaterThan(10);
    expect(Math.hypot(...simulatedAim(t + 2.5))).toBeGreaterThan(38);
    expect(distance(simulatedAim(t + 3))).toBeGreaterThan(40);
    expect(distance(simulatedAim(t + 5))).toBeGreaterThan(8);
    const entryX = Array.from({length: 61}, (_, frame) => simulatedAim(t + 2 + frame / 20)[0]);
    expect(Math.max(...entryX) - Math.min(...entryX)).toBeGreaterThan(5);
    const follow = Array.from({length: 61}, (_, frame) => distance(simulatedAim(t + 10 + frame / 60)));
    expect(Math.max(...follow)).toBeGreaterThan(100);
    expect(Math.max(...follow)).toBeLessThan(220);
    for (const boundary of [10, 11, 11.5]) {
      const before = simulatedAim(t + boundary - 0.00001);
      const after = simulatedAim(t + boundary + 0.00001);
      expect(Math.hypot(after[0] - before[0], after[1] - before[1])).toBeLessThan(0.05);
    }
    for (let frame = 151; frame < 600; frame++) {
      const before = simulatedAim(t + (frame - 1) / 60);
      const after = simulatedAim(t + frame / 60);
      expect(Math.hypot(after[0] - before[0], after[1] - before[1])).toBeLessThan(12);
    }
    return trigger;
  });
  expect(new Set(shots.map(shot => JSON.stringify(shot))).size).toBe(10);
});
