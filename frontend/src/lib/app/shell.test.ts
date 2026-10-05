import { describe, expect, it } from "vitest";

import { Announcer } from "./announcer.svelte";
import { sessionPill } from "./session-pill";

describe("sessionPill", () => {
  it("names the session state for the header pill", () => {
    expect(sessionPill({ kind: "idle" })).toEqual({ label: "Idle", tone: "idle" });
    expect(sessionPill({ kind: "recording", sessionId: 3 })).toEqual({
      label: "Recording",
      tone: "recording",
    });
    expect(sessionPill({ kind: "reviewing", sessionId: 3 })).toEqual({
      label: "Replay",
      tone: "replay",
    });
  });
});

describe("Announcer", () => {
  it("alternates regions so a repeated text is read again", () => {
    const announcer = new Announcer();
    announcer.announce("Saved session 4");
    expect(announcer.regions).toEqual(["Saved session 4", ""]);
    announcer.announce("Saved session 4");
    expect(announcer.regions).toEqual(["", "Saved session 4"]);
    announcer.announce("Using fake devices");
    expect(announcer.regions).toEqual(["Using fake devices", ""]);
  });

  it("ignores an empty text", () => {
    const announcer = new Announcer();
    announcer.announce("Tracking");
    announcer.announce("");
    expect(announcer.regions).toEqual(["Tracking", ""]);
  });
});
