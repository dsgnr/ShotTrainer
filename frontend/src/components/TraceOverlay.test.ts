// @vitest-environment jsdom
import { expect, it, vi } from "vitest";
import { flushSync, mount, unmount } from "svelte";
import TraceOverlay from "./TraceOverlay.svelte";

// @ts-expect-error Svelte exposes types for its public entry, not this internal file.
vi.mock("svelte", () => import("../../node_modules/svelte/src/index-client.js"));

vi.stubGlobal("ResizeObserver", class { observe(): void {} unobserve(): void {} disconnect(): void {} });

const shots = [0, 1, 2].map(i => ({
  timestamp: i, xMm: 0, yMm: 0, score: "5", shotId: i, seriesIndex: i < 2 ? 0 : 1,
}));

it("requests the traces and lets the series be chosen", async () => {
  const send = vi.fn().mockResolvedValue(undefined);
  const target = document.createElement("div");
  document.body.append(target);
  const component = mount(TraceOverlay, { target, props: {
    shots, traces: [{ points: [[0, 0], [1, 1]], releaseIndex: 1, splitIndex: 1 }], rings: [], shotsPerSeries: 2, shotDiameterMm: 4.5, send, onclose: vi.fn(),
  } });
  flushSync();
  expect(send).toHaveBeenCalledWith({ type: "loadShotTraces" });
  const trigger = target.querySelector<HTMLButtonElement>('button[aria-label="Series"]')!;
  expect(trigger.textContent).toContain("All series");
  trigger.click();
  flushSync();
  const items = [...target.querySelectorAll('[role="menuitemradio"]')].map(item => item.textContent);
  expect(items).toEqual(["All series", "Series 1", "Series 2"]);
  await unmount(component);
  target.remove();
});
