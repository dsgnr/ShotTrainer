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
  const brightness = container.querySelector<HTMLInputElement>('input[type="range"]')!;
  brightness.value = "23";
  brightness.dispatchEvent(new Event("input", { bubbles: true }));
  app.dispatch(SAMPLE_EVENTS.detectorStatus);
  flushSync();
  expect(brightness.value).toBe("23");
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
    prefs: expect.objectContaining({ cameraBrightness: 12, cameraContrast: 1.5 }),
  }));
  await unmount(component);
  container.remove();
});

it("uses themed device choices while preserving preview and saved values", async () => {
  const app = new AppState();
  app.dispatch(SAMPLE_EVENTS.preferences);
  const send = vi.fn(async (_command: WireCommand) => undefined);
  const onclose = vi.fn();
  const container = document.createElement("div");
  document.body.append(container);
  const component = mount(PreferencesDialog, { target: container, props: {
    open: true, preferences: app.preferences, cameras: [{ index: 2, name: "USB camera" }],
    microphones: ["USB microphone"], faces: [{ key: "test", label: "Test target", rings: [],
      shotDiameterMm: 4.5, faceDiameterMm: 100, scoringDirection: "inward" }], send, onclose,
  } });
  flushSync();
  expect(container.querySelector("select")).toBeNull();
  const choose = (label: string, option: string) => {
    container.querySelector<HTMLButtonElement>(`[aria-label="${label}"][aria-haspopup="menu"]`)!.click();
    flushSync();
    [...container.querySelectorAll<HTMLButtonElement>('[role="menuitemradio"]')]
      .find((item) => item.textContent === option)!.click();
    flushSync();
  };
  choose("Camera", "USB camera");
  expect(send).toHaveBeenCalledWith({ type: "previewCamera", cameraId: 2 });
  choose("Camera", "None");
  expect(send).toHaveBeenCalledWith({ type: "previewCamera", cameraId: null });
  choose("Rotation", "90°");
  expect(send).toHaveBeenCalledWith(expect.objectContaining({ type: "previewTransform", rotationDegrees: 90 }));
  choose("Microphone", "USB microphone");
  expect(container.querySelector('[aria-label="Target face"]')).toBeNull();
  [...container.querySelectorAll("button")].find((button) => button.textContent === "Save")!.click();
  expect(send).toHaveBeenCalledWith(expect.objectContaining({ type: "setPreferences",
    prefs: expect.objectContaining({ cameraId: null, cameraRotation: 90, audioDevice: "USB microphone" }),
  }));
  await unmount(component);
  container.remove();
});
