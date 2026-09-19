import { describe, expect, it } from "vitest";

import { formatSeconds, timeLabel } from "./format";

describe("formatSeconds", () => {
  it("formats zero", () => {
    expect(formatSeconds(0)).toBe("0:00.0");
  });

  it("rounds to a tenth of a second", () => {
    expect(formatSeconds(1234)).toBe("0:01.2");
    expect(formatSeconds(1250)).toBe("0:01.3");
  });

  it("rolls minutes over", () => {
    expect(formatSeconds(75_000)).toBe("1:15.0");
  });

  it("clamps a negative value to zero", () => {
    expect(formatSeconds(-500)).toBe("0:00.0");
  });
});

describe("timeLabel", () => {
  it("shows the placeholder with no window", () => {
    expect(timeLabel(0.5, null)).toBe("0:00.0 / 0:00.0");
  });

  it("shows the offset through the window", () => {
    expect(timeLabel(0.5, 10_000)).toBe("0:05.0 / 0:10.0");
  });
});
