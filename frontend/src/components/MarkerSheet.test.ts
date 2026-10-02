// @vitest-environment jsdom
import { expect, it, vi } from "vitest";
import { flushSync, mount, unmount } from "svelte";
import MarkerSheet from "./MarkerSheet.svelte";

// @ts-expect-error Svelte exposes types for its public entry, not this internal file.
vi.mock("svelte", () => import("../../node_modules/svelte/src/index-client.js"));

it("keeps all results in the scroll region and actions outside it", async () => {
  const target = document.createElement("div");
  document.body.append(target);
  const close = vi.fn();
  const print = vi.spyOn(window, "print").mockImplementation(() => undefined);
  const component = mount(MarkerSheet, { target, props: {
    open: true, session: { kind: "idle" }, totalScore: 200, onclose: close,
    shots: Array.from({ length: 40 }, (_, i) => ({ timestamp: i, xMm: 0, yMm: 0, score: "5", shotId: i })),
  } });
  flushSync();
  const body = target.querySelector('[aria-label="Shot results"]')!;
  expect(body.querySelectorAll("tbody tr")).toHaveLength(40);
  expect(body.querySelector("button")).toBeNull();
  const buttons = target.querySelectorAll<HTMLButtonElement>(".actions button");
  buttons[1]!.click();
  expect(print).toHaveBeenCalledOnce();
  buttons[0]!.click();
  expect(close).toHaveBeenCalledOnce();
  await unmount(component);
  target.remove();
  print.mockRestore();
});

it("opens with Close focused and restores focus without highlighting the results", async () => {
  const visibility = vi.spyOn(HTMLElement.prototype, "offsetParent", "get").mockReturnValue(document.body);
  const trigger = document.createElement("button"); trigger.textContent = "Shot sheet"; document.body.append(trigger); trigger.focus();
  const target = document.createElement("div"); document.body.append(target);
  const component = mount(MarkerSheet, {target, props: {open: true, session: {kind: "idle"}, totalScore: null, onclose: () => {}, shots: []}});
  flushSync();
  const close = target.querySelector<HTMLButtonElement>(".actions button")!;
  expect(document.activeElement).toBe(close);
  expect(document.activeElement).not.toBe(target.querySelector('[aria-label="Shot results"]'));
  const print = target.querySelectorAll<HTMLButtonElement>(".actions button")[1]!;
  print.focus();
  print.dispatchEvent(new KeyboardEvent("keydown", {key: "Tab", bubbles: true, cancelable: true}));
  expect(document.activeElement).toBe(target.querySelector('[aria-label="Shot results"]'));
  await unmount(component);
  expect(document.activeElement).toBe(trigger);
  target.remove(); trigger.remove(); visibility.mockRestore();
});

it("reports native print failures and clears the error when retrying", async () => {
  const print = vi.spyOn(window, "print")
    .mockImplementationOnce(() => Promise.reject(new Error("print denied")))
    .mockImplementation(() => undefined);
  const target = document.createElement("div");
  const component = mount(MarkerSheet, { target, props: {
    open: true, session: { kind: "idle" }, totalScore: null, shots: [], onclose: () => {},
  } });
  flushSync();
  const button = target.querySelector<HTMLButtonElement>(".actions .primary")!;
  button.click();
  await vi.waitFor(() => {
    flushSync();
    expect(target.querySelector('[role="alert"]')?.textContent).toContain("print denied");
  });
  button.click();
  await Promise.resolve();
  flushSync();
  expect(target.querySelector('[role="alert"]')).toBeNull();
  expect(print).toHaveBeenCalledTimes(2);
  await unmount(component);
  print.mockRestore();
});
