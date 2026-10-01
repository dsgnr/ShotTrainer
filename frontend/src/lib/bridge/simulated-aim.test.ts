import { expect, it } from "vitest";
import { simulatedAim } from "./simulated-aim";
it("approaches mostly straight with varied speed and rapid recoil", () => {
  const shots = Array.from({length: 10}, (_, i) => {
    const t = i * 5;
    const approach = simulatedAim(t + 1.51);
    const shot = simulatedAim(t + 5);
    const entryPhase = i === 0 ? 0 : 1.5;
    const entry = simulatedAim(t + entryPhase);
    expect(Math.abs(entry[0])).toBeLessThan(28);
    expect(entry[1]).toBeGreaterThan(100);
    expect(Math.hypot(...shot)).toBeLessThan(8);
    expect(simulatedAim(t + entryPhase + 0.2)[1]).toBeLessThan(entry[1] - 0.5);
    const axis: [number, number] = [entry[0] - shot[0], entry[1] - shot[1]];
    for (let frame = 0; frame < 101; frame++) {
      const point = simulatedAim(t + entryPhase + (4.85 - entryPhase) * frame / 100);
      const lateral = Math.abs((point[0] - shot[0]) * axis[1] - (point[1] - shot[1]) * axis[0]) / Math.hypot(...axis);
      expect(lateral).toBeLessThan(40);
    }
    const fastStart = simulatedAim(t + 3.9);
    const early = simulatedAim(t + 4.1);
    const lateStart = simulatedAim(t + 4.6);
    const lateEnd = simulatedAim(t + 4.8);
    expect(Math.abs(fastStart[1] - early[1])).toBeGreaterThan(2 * Math.abs(lateStart[1] - lateEnd[1]));
    expect(Math.hypot(approach[0] - shot[0], approach[1] - shot[1])).toBeGreaterThan(20);
    for (let n = 0; n < 8; n++) {
      const hold = simulatedAim(t + 4.75 + n / 32);
      expect(Math.hypot(hold[0] - shot[0], hold[1] - shot[1])).toBeLessThan(7);
    }
    const kick = simulatedAim(t + 5.02);
    expect(Math.hypot(kick[0] - shot[0], kick[1] - shot[1])).toBeGreaterThan(70);
    const loop = Array.from({length: 13}, (_, n) => simulatedAim(t + 5.015 + n * 0.03));
    expect(loop.some(point => Math.hypot(point[0] - shot[0], point[1] - shot[1]) > 200)).toBe(true);
    expect(loop.some(point => Math.abs(point[0] - shot[0]) > 35)).toBe(true);
    expect(loop.some(point => point[1] > shot[1] + 50)).toBe(true);
    const settled = simulatedAim(t + 5.8);
    expect(Math.hypot(settled[0] - shot[0], settled[1] - shot[1])).toBeLessThan(8);
    for (const boundary of [5, 6, 6.5]) {
      const before = simulatedAim(t + boundary - 0.00001);
      const after = simulatedAim(t + boundary + 0.00001);
      expect(Math.hypot(after[0] - before[0], after[1] - before[1])).toBeLessThan(0.02);
    }
    return shot;
  });
  expect(new Set(shots.map(shot => JSON.stringify(shot))).size).toBe(10);
});
