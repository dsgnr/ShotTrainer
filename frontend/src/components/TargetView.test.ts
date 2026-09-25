// @vitest-environment jsdom
import { expect, it, vi } from "vitest";
import { flushSync, mount, unmount } from "svelte";
import TargetView from "./TargetView.svelte";
import { TargetModel } from "../lib/target/model";

// Vitest uses Node export conditions; this DOM test needs Svelte's client entry.
// @ts-expect-error Svelte exposes types for its public entry, not this internal file.
vi.mock("svelte", () => import("../../node_modules/svelte/src/index-client.js"));

it("invalidates the mounted canvas when the model changes without resizing", async () => {
  vi.stubGlobal("ResizeObserver", class { observe() {} unobserve() {} disconnect() {} });
  const context = vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue(null);
  const model = new TargetModel();
  const onextent = vi.fn();
  const container = document.createElement("div");
  document.body.append(container);
  const component = mount(TargetView, { target: container, props: { model, rings: [], onextent } });
  flushSync();
  const initialDraws = context.mock.calls.length;
  model.appendTracePoint(1, 2);
  flushSync();
  expect(context.mock.calls.length).toBeGreaterThan(initialDraws);
  const beforeZoom = context.mock.calls.length;
  model.setExtent(45);
  flushSync();
  expect(context.mock.calls.length).toBeGreaterThan(beforeZoom);
  container.querySelector("canvas")!.dispatchEvent(new WheelEvent("wheel", { deltaY: -120, cancelable: true }));
  expect(onextent).toHaveBeenLastCalledWith(40.5);
  model.setExtent(500);
  container.querySelector("canvas")!.dispatchEvent(new WheelEvent("wheel", { deltaY: 120, cancelable: true }));
  expect(onextent).toHaveBeenLastCalledWith(500);
  await unmount(component);
  const finalDraws = context.mock.calls.length;
  model.setExtent(10);
  flushSync();
  expect(context.mock.calls.length).toBe(finalDraws);
  container.remove();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});
