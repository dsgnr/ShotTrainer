// @vitest-environment jsdom
import { expect, it, vi } from "vitest";
import { flushSync, mount, unmount } from "svelte";
import SessionBrowser from "./SessionBrowser.svelte";

// @ts-expect-error Svelte exposes types for its public entry, not this internal file.
vi.mock("svelte", () => import("../../node_modules/svelte/src/index-client.js"));

it("offers a new session on the page and disables it during recording", async () => {
  for (const recording of [false, true]) {
    const target = document.createElement("div");
    const onnew = vi.fn();
    const send = vi.fn(async () => undefined);
    const component = mount(SessionBrowser, { target, props: {
      open: true, sessions: [], recording, send, onnew, onopen: vi.fn(),
    } });
    flushSync();
    expect(send).toHaveBeenCalledWith({ type: "listSessions" });
    expect(target.querySelector('[role="dialog"]')).toBeNull();
    const button = target.querySelector<HTMLButtonElement>("header button")!;
    expect(button.disabled).toBe(recording);
    button.click();
    expect(onnew).toHaveBeenCalledTimes(recording ? 0 : 1);
    await unmount(component);
  }
});
