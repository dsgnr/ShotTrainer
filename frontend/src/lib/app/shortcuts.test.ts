import { describe, expect, it } from "vitest";

import { resolveShortcut, type ShortcutContext } from "./shortcuts";

function context(overrides: Partial<ShortcutContext> = {}): ShortcutContext {
  return {
    key: "",
    typing: false,
    modalOpen: false,
    replayEnabled: false,
    replayPlaying: false,
    shotCount: 0,
    selected: null,
    ...overrides,
  };
}

describe("resolveShortcut", () => {
  it("does nothing while typing in a field", () => {
    expect(resolveShortcut(context({ key: " ", replayEnabled: true, typing: true }))).toBeNull();
  });

  it("closes an open modal on Escape", () => {
    expect(resolveShortcut(context({ key: "Escape", modalOpen: true }))).toEqual({ kind: "closeModal" });
  });

  it("ignores Escape with no modal open", () => {
    expect(resolveShortcut(context({ key: "Escape" }))).toBeNull();
  });

  it("suppresses other shortcuts while a modal is open", () => {
    expect(resolveShortcut(context({ key: " ", replayEnabled: true, modalOpen: true }))).toEqual({
      kind: "none",
    });
  });

  it("toggles replay with Space when a window is loaded", () => {
    expect(resolveShortcut(context({ key: " ", replayEnabled: true, replayPlaying: false }))).toEqual({
      kind: "replayToggle",
      play: true,
    });
    expect(resolveShortcut(context({ key: " ", replayEnabled: true, replayPlaying: true }))).toEqual({
      kind: "replayToggle",
      play: false,
    });
  });

  it("ignores Space with no replay loaded", () => {
    expect(resolveShortcut(context({ key: " ", replayEnabled: false }))).toBeNull();
  });

  it("steps the shot selection with the arrow keys", () => {
    expect(resolveShortcut(context({ key: "ArrowDown", shotCount: 3, selected: null }))).toEqual({
      kind: "selectShot",
      index: 0,
    });
    expect(resolveShortcut(context({ key: "ArrowUp", shotCount: 3, selected: null }))).toEqual({
      kind: "selectShot",
      index: 2,
    });
    expect(resolveShortcut(context({ key: "ArrowDown", shotCount: 3, selected: 1 }))).toEqual({
      kind: "selectShot",
      index: 2,
    });
  });

  it("ignores the arrow keys with no shots", () => {
    expect(resolveShortcut(context({ key: "ArrowDown", shotCount: 0 }))).toBeNull();
  });

  it("ignores unmapped keys", () => {
    expect(resolveShortcut(context({ key: "x", replayEnabled: true }))).toBeNull();
  });
});
