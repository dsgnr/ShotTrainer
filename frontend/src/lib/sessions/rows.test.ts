import { describe, expect, it } from "vitest";

import type { WireSessionSummary } from "../wire/types";
import { filterSessions, scoreBadge, sessionMeta } from "./rows";

function summary(overrides: Partial<WireSessionSummary> = {}): WireSessionSummary {
  return {
    id: 1,
    name: "Evening",
    startedAt: "2026-02-03T14:05:00",
    endedAt: "2026-02-03T14:21:30",
    shotCount: 10,
    totalScore: 98.5,
    category: "practice",
    ...overrides,
  };
}

describe("sessionMeta", () => {
  it("joins the date, shot count and duration", () => {
    expect(sessionMeta(summary())).toBe("3 Feb 2026, 14:05  \u00b7  10 shots  \u00b7  16m 30s");
  });

  it("uses the singular for one shot", () => {
    expect(sessionMeta(summary({ shotCount: 1 }))).toContain("1 shot  \u00b7");
  });

  it("shows seconds only for a short session", () => {
    expect(sessionMeta(summary({ endedAt: "2026-02-03T14:05:08" }))).toContain("8s");
  });

  it("reports a session still in progress", () => {
    expect(sessionMeta(summary({ endedAt: null }))).toContain("in progress");
  });
});

describe("scoreBadge", () => {
  it("shows the points when the session scored", () => {
    expect(scoreBadge(summary())).toBe("98.5 pts");
  });

  it("is empty with no shots or no score", () => {
    expect(scoreBadge(summary({ shotCount: 0 }))).toBe("");
    expect(scoreBadge(summary({ totalScore: 0 }))).toBe("");
  });
});

describe("filterSessions", () => {
  const sessions = [
    summary({ id: 1, name: "Morning practice", category: "practice" }),
    summary({ id: 2, name: "Club match", category: "match" }),
    summary({ id: 3, name: "Sighters", category: "sighter" }),
  ];

  it("returns all with an empty query and no category", () => {
    expect(filterSessions(sessions, "", "").map((s) => s.id)).toEqual([1, 2, 3]);
  });

  it("matches the name case-insensitively", () => {
    expect(filterSessions(sessions, "MATCH", "").map((s) => s.id)).toEqual([2]);
  });

  it("filters by category", () => {
    expect(filterSessions(sessions, "", "sighter").map((s) => s.id)).toEqual([3]);
  });

  it("combines the name and category filters", () => {
    expect(filterSessions(sessions, "club", "match").map((s) => s.id)).toEqual([2]);
    expect(filterSessions(sessions, "club", "practice")).toEqual([]);
  });
});
