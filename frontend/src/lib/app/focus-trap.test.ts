import { describe, expect, it } from "vitest";

import { nextFocusIndex } from "./focus-trap";

describe("nextFocusIndex", () => {
  it("moves forward and wraps past the last element", () => {
    expect(nextFocusIndex(0, 3, false)).toBe(1);
    expect(nextFocusIndex(2, 3, false)).toBe(0);
  });

  it("moves backward and wraps past the first element", () => {
    expect(nextFocusIndex(1, 3, true)).toBe(0);
    expect(nextFocusIndex(0, 3, true)).toBe(2);
  });

  it("starts at the first element forward when nothing is focused", () => {
    expect(nextFocusIndex(-1, 3, false)).toBe(0);
  });

  it("starts at the last element backward when nothing is focused", () => {
    expect(nextFocusIndex(-1, 3, true)).toBe(2);
  });

  it("has no target when there is nothing focusable", () => {
    expect(nextFocusIndex(0, 0, false)).toBeNull();
    expect(nextFocusIndex(-1, 0, true)).toBeNull();
  });
});
