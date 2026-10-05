import { afterEach, describe, expect, it } from "vitest";

import { createBridge } from "./index";
import { MockBridge } from "./mock";
import { TauriBridge } from "./tauri";

const global = globalThis as { isTauri?: boolean };

afterEach(() => {
  delete global.isTauri;
});

describe("createBridge", () => {
  it("uses the mock in a plain browser", () => {
    expect(createBridge()).toBeInstanceOf(MockBridge);
  });

  it("uses Tauri inside the shell", () => {
    global.isTauri = true;
    expect(createBridge()).toBeInstanceOf(TauriBridge);
  });
});
