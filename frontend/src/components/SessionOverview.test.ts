// @vitest-environment jsdom
import { expect, it, vi } from "vitest";
import { flushSync, mount, unmount } from "svelte";
import SessionOverview from "./SessionOverview.svelte";

// @ts-expect-error Svelte exposes types for its public entry, not this internal file.
vi.mock("svelte", () => import("../../node_modules/svelte/src/index-client.js"));

it("shows numbered selection controls only for mapped shots", async () => {
  vi.stubGlobal("ResizeObserver", class { observe() {} unobserve() {} disconnect() {} });
  vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue(null);
  const send = vi.fn(async () => undefined);
  const container = document.createElement("div");
  document.body.append(container);
  const component = mount(SessionOverview, { target: container, props: {
    shots: [
      { timestamp: 0, xMm: null, yMm: null, score: null, shotId: 1 },
      { timestamp: 1, xMm: 2, yMm: -3, score: "9", shotId: 2 },
    ], selected: 1, rings: [], shotDiameterMm: 4.5, send,
  } });
  flushSync();
  const markers = container.querySelectorAll("button");
  expect(markers.length).toBe(1);
  expect(markers[0]?.getAttribute("aria-label")).toBe("Select shot 2");
  expect(markers[0]?.getAttribute("aria-pressed")).toBe("true");
  markers[0]?.click();
  expect(send).toHaveBeenCalledWith({ type: "selectShot", index: 1 });
  await unmount(component);
  const single = mount(SessionOverview, { target: container, props: {
    shots: [{ timestamp: 1, xMm: 1, yMm: 2, score: "9", shotId: 1 }],
    selected: null, rings: [], shotDiameterMm: 4.5, send,
  } });
  flushSync();
  expect(container.querySelectorAll("button")).toHaveLength(1);
  await unmount(single);
  const many = mount(SessionOverview, { target: container, props: {
    shots: Array.from({ length: 100 }, (_, i) => ({ timestamp: i, xMm: i, yMm: -i, score: "9", shotId: i })),
    selected: 99, rings: [], shotDiameterMm: 4.5, send,
  } });
  flushSync();
  expect(container.querySelectorAll("button")).toHaveLength(100);
  expect(container.querySelector('[aria-label="Select shot 100"]')?.getAttribute("aria-pressed")).toBe("true");
  await unmount(many);
  const empty = mount(SessionOverview, { target: container, props: {
    shots: [], selected: null, rings: [], shotDiameterMm: 4.5, send,
  } });
  flushSync();
  expect(container.textContent).toContain("No shots yet");
  expect(container.querySelector("canvas")).toBeNull();
  await unmount(empty);
  container.remove();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});
