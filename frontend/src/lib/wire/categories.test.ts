import { describe, expect, it } from "vitest";

import { DEFAULT_SESSION_CATEGORY, SESSION_CATEGORIES, categoryLabel } from "./categories";

describe("session categories", () => {
  it("lists the stored values in order", () => {
    expect(SESSION_CATEGORIES).toEqual(["practice", "sighter", "match"]);
  });

  it("defaults to practice", () => {
    expect(DEFAULT_SESSION_CATEGORY).toBe("practice");
    expect(SESSION_CATEGORIES).toContain(DEFAULT_SESSION_CATEGORY);
  });

  it("capitalises a category for display", () => {
    expect(categoryLabel("practice")).toBe("Practice");
    expect(categoryLabel("match")).toBe("Match");
  });
});
