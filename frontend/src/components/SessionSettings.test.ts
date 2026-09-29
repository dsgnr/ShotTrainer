// @vitest-environment jsdom
import { expect, it, vi } from "vitest";
import { flushSync, mount, unmount } from "svelte";
import SessionSettings from "./SessionSettings.svelte";
import { MOCK_PREFERENCES } from "../lib/bridge/mock";

// @ts-expect-error Svelte exposes types for its public entry, not this internal file.
vi.mock("svelte", () => import("../../node_modules/svelte/src/index-client.js"));

it("applies timing and target settings to the session without saving global preferences", async () => {
  const target = document.createElement("div");
  document.body.append(target);
  const send = vi.fn(async () => undefined);
  const component = mount(SessionSettings, { target, props: {
    prefs: MOCK_PREFERENCES, faces: [], locked: false, send,
  } });
  flushSync();
  const inputs = target.querySelectorAll<HTMLInputElement>("input");
  for (const [i, value] of [3000, 1200, 500, 900, 5.5].entries()) {
    inputs[i]!.value = String(value);
    inputs[i]!.dispatchEvent(new Event("input", { bubbles: true }));
  }
  target.querySelector("form")!.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
  flushSync();
  expect(send).toHaveBeenCalledExactlyOnceWith({ type: "setSessionSettings", prefs: {
    ...MOCK_PREFERENCES, preShotMs: 3000, postShotMs: 1200, releaseWindowMs: 500,
    shotRefractoryMs: 900, shotDiameterMm: 5.5,
  } });
  await unmount(component);
  const locked = mount(SessionSettings, { target, props: { prefs: MOCK_PREFERENCES, faces: [], locked: true, send } });
  flushSync();
  expect(target.querySelector<HTMLFieldSetElement>("fieldset")!.disabled).toBe(true);
  target.querySelector("form")!.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
  expect(send).toHaveBeenCalledTimes(1);
  await unmount(locked);
  target.remove();
});
