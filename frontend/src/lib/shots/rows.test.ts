import { describe, expect, it } from "vitest";

import type { WireShot } from "../wire/types";
import { shotRows, stepSelection } from "./rows";

function shot(xMm: WireShot["xMm"], yMm: WireShot["yMm"], score: string | null = null): WireShot {
  return { timestamp: 0, xMm, yMm, score, shotId: null };
}

describe("shotRows", () => {
  it("numbers each shot from one", () => {
    const rows = shotRows([shot(1, 2), shot(3, 4)]);
    expect(rows.map((r) => r.number)).toEqual([1, 2]);
  });

  it("shows the score or a dash", () => {
    expect(shotRows([shot(0, 0, "10.4")])[0]?.score).toBe("10.4");
    expect(shotRows([shot(0, 0, null)])[0]?.score).toBe("-");
  });

  it("formats the offset with a sign and one decimal", () => {
    expect(shotRows([shot(5.12, -2.07)])[0]?.offset).toBe("+5.1, -2.1\u202fmm");
  });

  it("reports an unavailable position when a coordinate is missing", () => {
    expect(shotRows([shot(null, 2)])[0]?.offset).toBe("Position unavailable");
    expect(shotRows([shot(1, null)])[0]?.offset).toBe("Position unavailable");
  });
});

describe("stepSelection", () => {
  it("picks the first shot stepping down from nothing", () => {
    expect(stepSelection(null, 1, 4)).toBe(0);
  });

  it("picks the last shot stepping up from nothing", () => {
    expect(stepSelection(null, -1, 4)).toBe(3);
  });

  it("clamps within the list", () => {
    expect(stepSelection(0, -1, 4)).toBe(0);
    expect(stepSelection(3, 1, 4)).toBe(3);
    expect(stepSelection(1, 1, 4)).toBe(2);
  });

  it("returns null for an empty list", () => {
    expect(stepSelection(null, 1, 0)).toBeNull();
    expect(stepSelection(2, -1, 0)).toBeNull();
  });
});
