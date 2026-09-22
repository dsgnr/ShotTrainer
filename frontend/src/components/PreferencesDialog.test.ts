// @vitest-environment jsdom
import { expect, it, vi } from "vitest";
import { flushSync, mount, unmount } from "svelte";
import PreferencesDialog from "./PreferencesDialog.svelte";
import { AppState } from "../lib/stores/app.svelte";
import type { WireCommand } from "../lib/wire/types";
import { SAMPLE_EVENTS } from "../lib/wire/samples";

// Vitest uses Node export conditions; this DOM test needs Svelte's client entry.
// @ts-expect-error Svelte exposes types for its public entry, not this internal file.
vi.mock("svelte", () => import("../../node_modules/svelte/src/index-client.js"));

it("preserves a draft across detector updates and saves optimised image controls", async () => {
  const app = new AppState();
  app.dispatch(SAMPLE_EVENTS.preferences);
  const send = vi.fn(async (_command: WireCommand) => undefined);
  const container = document.createElement("div");
  document.body.append(container);
  const component = mount(PreferencesDialog, {
    target: container,
    props: { open: true, get preferences() { return app.preferences; }, cameras: [], microphones: [], faces: [], send, onclose: () => undefined },
  });
  flushSync();
  expect(send).toHaveBeenCalledWith({ type: "beginPreview", cameraId: app.preferences.prefs!.cameraId });
  const timing = container.querySelector<HTMLInputElement>('input[type="number"]')!;
  timing.value = "1234";
  timing.dispatchEvent(new Event("input", { bubbles: true }));
  app.dispatch(SAMPLE_EVENTS.detectorStatus);
  flushSync();
  expect(timing.value).toBe("1234");
  expect(send.mock.calls.filter(([command]) => command.type === "beginPreview")).toHaveLength(1);
  app.dispatch(SAMPLE_EVENTS.imageControls);
  flushSync();
  const sliders = container.querySelectorAll<HTMLInputElement>('input[type="range"]');
  expect(sliders[0]!.value).toBe("12");
  expect(sliders[1]!.value).toBe("1.5");
  const save = [...container.querySelectorAll("button")].find((button) => button.textContent === "Save")!;
  save.click();
  expect(send).toHaveBeenCalledWith(expect.objectContaining({
    type: "setPreferences",
    prefs: expect.objectContaining({ cameraBrightness: 12, cameraContrast: 1.5, shotRefractoryMs: 1234 }),
  }));
  await unmount(component);
  container.remove();
});
