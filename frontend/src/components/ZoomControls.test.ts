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
    const component = mount(ZoomControls, { target: container, props: { extentMm: extent, referenceExtentMm: 90, auto: false, onauto: vi.fn(), onextent } });
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
      expect(container.querySelector('[aria-haspopup="menu"]')!.textContent).toContain("100%");
    }
    const slider = container.querySelector<HTMLInputElement>('input[type="range"]')!;
    slider.value = "1000";
    slider.dispatchEvent(new Event("input", { bubbles: true }));
    expect(onextent.mock.lastCall![0]).toBeCloseTo(ZOOM_MIN_MM);
    slider.value = "0";
    slider.dispatchEvent(new Event("input", { bubbles: true }));
    expect(onextent.mock.lastCall![0]).toBeCloseTo(ZOOM_MAX_MM);
    container.querySelector<HTMLButtonElement>('[aria-haspopup="menu"]')!.click();
    flushSync();
    const fit = [...container.querySelectorAll<HTMLButtonElement>('[role="menuitemradio"]')].find((item) => item.textContent === "100%")!;
    fit.click();
    expect(onextent.mock.lastCall![0]).toBe(90);
    await unmount(component);
  }
  container.remove();
});

it("offers automatic framing in the percentage selector", async () => {
  const container = document.createElement("div");
  const onextent = vi.fn();
  const onauto = vi.fn();
  const component = mount(ZoomControls, { target: container, props: {
    extentMm: 9, auto: true, onauto, onextent,
  } });
  flushSync();
  const mode = container.querySelector<HTMLButtonElement>('[aria-haspopup="menu"]')!;
  expect(mode.textContent).toContain("Auto");
  mode.click();
  flushSync();
  container.querySelector<HTMLButtonElement>('[role="menuitemradio"][aria-checked="true"]')!.click();
  expect(onauto).toHaveBeenCalledOnce();
  expect(onextent).not.toHaveBeenCalled();
  container.querySelector<HTMLButtonElement>('[aria-label="Zoom out"]')!.click();
  expect(onextent).toHaveBeenCalledOnce();
  await unmount(component);
});

it("navigates the themed menu with arrow keys and dismisses with Escape or an outside click", async () => {
  const container = document.createElement("div");
  document.body.append(container);
  const onextent = vi.fn();
  const component = mount(ZoomControls, { target: container, props: {
    extentMm: 90, auto: true, onauto: vi.fn(), onextent,
  } });
  flushSync();
  const trigger = container.querySelector<HTMLButtonElement>('[aria-haspopup="menu"]')!;
  trigger.focus();
  trigger.dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowDown", bubbles: true, cancelable: true }));
  flushSync();
  await Promise.resolve();
  expect(document.activeElement?.textContent?.trim()).toBe("Auto");
  document.activeElement!.dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowDown", bubbles: true, cancelable: true }));
  expect(document.activeElement?.textContent?.trim()).toBe("100%");
  document.activeElement!.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true, cancelable: true }));
  flushSync();
  expect(trigger.getAttribute("aria-expanded")).toBe("false");
  expect(document.activeElement).toBe(trigger);
  expect(onextent).not.toHaveBeenCalled();
  trigger.click();
  flushSync();
  document.body.dispatchEvent(new Event("pointerdown", { bubbles: true }));
  flushSync();
  expect(container.querySelector('[role="menu"]')).toBeNull();
  await unmount(component);
  container.remove();
});
