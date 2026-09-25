// @vitest-environment jsdom
import { expect, it, vi } from "vitest";
import { flushSync, mount, unmount } from "svelte";
import ReplayControls from "./ReplayControls.svelte";
import { initialReplay } from "../lib/stores/replay";
import { SAMPLE_EVENTS } from "../lib/wire/samples";

// @ts-expect-error Svelte exposes types for its public entry, not this internal file.
vi.mock("svelte", () => import("../../node_modules/svelte/src/index-client.js"));

it("keeps replay actions and disabled states behind labelled transport controls", async () => {
  const container = document.createElement("div");
  document.body.append(container);
  const send = vi.fn(async () => undefined);
  const disabled = mount(ReplayControls, { target: container, props: { replay: initialReplay, send } });
  flushSync();
  expect(container.querySelector<HTMLButtonElement>('[aria-label="Play replay"]')!.disabled).toBe(true);
  await unmount(disabled);
  for (const playing of [false, true]) {
    const replay = { ...initialReplay, loaded: { ...SAMPLE_EVENTS.replayLoaded, enabled: true }, playing };
    const component = mount(ReplayControls, { target: container, props: { replay, send } });
    flushSync();
    container.querySelector<HTMLButtonElement>(`[aria-label="${playing ? "Pause" : "Play"} replay"]`)!.click();
    expect(send).toHaveBeenLastCalledWith({ type: playing ? "replayPause" : "replayPlay" });
    container.querySelector<HTMLButtonElement>('[aria-label="Reset replay"]')!.click();
    expect(send).toHaveBeenLastCalledWith({ type: "replayReset" });
    const slider = container.querySelector<HTMLInputElement>("input")!;
    slider.value = "500";
    slider.dispatchEvent(new Event("input", { bubbles: true }));
    expect(send).toHaveBeenLastCalledWith({ type: "replaySeek", fraction: 0.5 });
    await unmount(component);
  }
  container.remove();
});
