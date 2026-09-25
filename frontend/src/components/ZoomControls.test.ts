// @vitest-environment jsdom
import { expect, it, vi } from "vitest";
import { flushSync, mount, unmount } from "svelte";
import ZoomControls from "./ZoomControls.svelte";
import { ZOOM_MIN_MM, ZOOM_MAX_MM } from "../lib/target/geometry";

// @ts-expect-error Svelte exposes types for its public entry, not this internal file.
vi.mock("svelte", () => import("../../node_modules/svelte/src/index-client.js"));

it("uses the same bounded extent for slider, buttons and fitted percentage", async () => {
  const container = document.createElement("div");
  document.body.append(container);
  for (const extent of [90, ZOOM_MIN_MM, ZOOM_MAX_MM]) {
    const onextent = vi.fn();
    const component = mount(ZoomControls, { target: container, props: { extentMm: extent, referenceExtentMm: 90, onextent } });
    flushSync();
    const zoomIn = container.querySelector<HTMLButtonElement>('[aria-label="Zoom in"]')!;
    const zoomOut = container.querySelector<HTMLButtonElement>('[aria-label="Zoom out"]')!;
    expect(zoomIn.disabled).toBe(extent === ZOOM_MIN_MM);
    expect(zoomOut.disabled).toBe(extent === ZOOM_MAX_MM);
    if (extent === 90) {
      zoomIn.click();
      expect(onextent.mock.lastCall![0]).toBeLessThan(extent);
      zoomOut.click();
      expect(onextent.mock.lastCall![0]).toBeGreaterThan(extent);
      expect(container.querySelector('[aria-label="Reset target zoom"]')?.textContent).toBe("100%");
    }
    const slider = container.querySelector<HTMLInputElement>('input[type="range"]')!;
    slider.value = "1000";
    slider.dispatchEvent(new Event("input", { bubbles: true }));
    expect(onextent.mock.lastCall![0]).toBeCloseTo(ZOOM_MIN_MM);
    slider.value = "0";
    slider.dispatchEvent(new Event("input", { bubbles: true }));
    expect(onextent.mock.lastCall![0]).toBeCloseTo(ZOOM_MAX_MM);
    container.querySelector<HTMLButtonElement>('[aria-label="Reset target zoom"]')!.click();
    expect(onextent.mock.lastCall![0]).toBe(90);
    await unmount(component);
  }
  container.remove();
});
