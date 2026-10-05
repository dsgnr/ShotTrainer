import { describe, expect, it } from "vitest";

import type { WireRing, WireShotStats, WireTraceStats } from "../wire/types";
import {
  diagnosticRings,
  groupFigure,
  timeOnTargetFigure,
  totalScoreFigure,
  tremorFigure,
} from "./hero";

const RINGS: WireRing[] = [
  { diameterMm: 100, label: "1" },
  { diameterMm: 60, label: "5" },
  { diameterMm: 20, label: "X" },
];

describe("totalScoreFigure", () => {
  it("dashes when there are no scores", () => {
    expect(totalScoreFigure(null, 0)).toBe("-");
  });

  it("formats a positive total compactly", () => {
    expect(totalScoreFigure(97.5, 10)).toBe("97.5");
  });

  it("falls back to the shot count when nothing scored", () => {
    expect(totalScoreFigure(0, 3)).toBe("3 shots");
  });
});

describe("groupFigure", () => {
  it("dashes with no shots", () => {
    const stats: WireShotStats = {
      count: 0,
      meanXMm: 0,
      meanYMm: 0,
      extremeSpreadMm: 0,
      meanRadiusMm: 0,
    };
    expect(groupFigure(stats)).toEqual({ value: "-", tooltip: "" });
  });

  it("shows extreme spread with the mean radius on the tooltip", () => {
    const stats: WireShotStats = {
      count: 3,
      meanXMm: 1,
      meanYMm: 2,
      extremeSpreadMm: 12.34,
      meanRadiusMm: 5.67,
    };
    const figure = groupFigure(stats);
    expect(figure.value).toBe("12.3\u202fmm");
    expect(figure.tooltip).toContain("Extreme spread: 12.3 mm");
    expect(figure.tooltip).toContain("Mean radius from group centre: 5.7 mm");
  });
});

describe("tremorFigure", () => {
  it("dashes with no trace", () => {
    expect(tremorFigure(null)).toBe("-");
  });

  it("dashes with no samples", () => {
    const stats: WireTraceStats = {
      samples: 0,
      holdTremorMm: 0,
      traceLengthMm: 0,
      meanXMm: 0,
      meanYMm: 0,
    };
    expect(tremorFigure(stats)).toBe("-");
  });

  it("formats the hold tremor", () => {
    const stats: WireTraceStats = {
      samples: 10,
      holdTremorMm: 1.23,
      traceLengthMm: 50,
      meanXMm: 0,
      meanYMm: 0,
    };
    expect(tremorFigure(stats)).toBe("1.2\u202fmm");
  });
});

describe("diagnosticRings", () => {
  it("picks the smallest ring and a mid-sized one", () => {
    const chosen = diagnosticRings(RINGS);
    expect(chosen.map((r) => r.diameterMm)).toEqual([20, 60]);
  });

  it("returns the single ring when only one is given", () => {
    expect(diagnosticRings([RINGS[1]!]).map((r) => r.diameterMm)).toEqual([60]);
  });

  it("is empty with no rings", () => {
    expect(diagnosticRings([])).toEqual([]);
  });
});

describe("timeOnTargetFigure", () => {
  it("names the diagnostic ring in the caption", () => {
    const figure = timeOnTargetFigure([], RINGS);
    expect(figure.caption).toBe("TIME INSIDE X");
  });

  it("falls back to a generic caption with no rings", () => {
    expect(timeOnTargetFigure([], []).caption).toBe("TIME ON TARGET");
  });

  it("dashes the value with no trace or no rings", () => {
    expect(timeOnTargetFigure([], RINGS).value).toBe("-");
    expect(
      timeOnTargetFigure(
        [
          [0, 0],
          [1, 1],
        ],
        [],
      ).value,
    ).toBe("-");
  });

  it("reports the fraction of trace within the smallest ring radius", () => {
    // Smallest ring is 20 mm diameter, so a 10 mm radius. Two of four points
    // fall inside.
    const figure = timeOnTargetFigure(
      [
        [0, 0],
        [5, 0],
        [50, 0],
        [60, 0],
      ],
      RINGS,
    );
    expect(figure.value).toBe("50%");
  });
});
