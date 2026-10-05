import { describe, expect, it } from "vitest";

import type { WireSessionState } from "../wire/types";
import { primaryLabel, secondaryDisabled } from "./session-controls";

describe("primaryLabel", () => {
  it("offers Start when idle", () => {
    expect(primaryLabel({ kind: "idle" })).toBe("Start session");
  });

  it("offers Stop while recording", () => {
    expect(primaryLabel({ kind: "recording", sessionId: 1 })).toBe("Stop session");
  });

  it("offers Start while reviewing a saved session", () => {
    expect(primaryLabel({ kind: "reviewing", sessionId: 1 })).toBe("Start session");
  });
});

describe("secondaryDisabled", () => {
  it("disables the name, category and clear while recording", () => {
    expect(secondaryDisabled({ kind: "recording", sessionId: 1 })).toBe(true);
  });

  it("enables them when not recording", () => {
    expect(secondaryDisabled({ kind: "idle" })).toBe(false);
    expect(secondaryDisabled({ kind: "reviewing", sessionId: 1 })).toBe(false);
  });
});
