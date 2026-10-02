// @vitest-environment jsdom
import { expect, it, vi } from "vitest";
import { flushSync, mount, unmount } from "svelte";
import { UpdateManager } from "../lib/app/updates.svelte";
import UpdateBanner from "./UpdateBanner.svelte";

// @ts-expect-error Svelte exposes types for its public entry, not this internal file.
vi.mock("svelte", () => import("../../node_modules/svelte/src/index-client.js"));

it("blocks installation during recording and offers manual downloads for package installs", async () => {
  for (const selfInstall of [true, false]) {
    const openReleases = vi.fn(async () => undefined);
    const updates = new UpdateManager({ check: async () => ({ version: "0.2.0", selfInstall, download: async () => undefined, install: async () => undefined, close: async () => undefined }), prepare: async () => undefined, openReleases }, () => true, async () => undefined);
    await updates.check();
    const target = document.createElement("div");
    const component = mount(UpdateBanner, { target, props: { updates, recording: true } });
    flushSync();
    expect(target.textContent).toContain("Version 0.2.0");
    const button = target.querySelector<HTMLButtonElement>("button.primary")!;
    if (selfInstall) {
      expect(button.disabled).toBe(true);
      expect(target.textContent).toContain("Stop recording");
    } else {
      expect(button.textContent).toBe("Download");
      button.click();
      expect(openReleases).toHaveBeenCalledOnce();
    }
    await unmount(component);
  }
});
