// @vitest-environment jsdom
import { expect, it, vi } from "vitest";
import { flushSync, mount, unmount } from "svelte";
import MarkerSheet from "./MarkerSheet.svelte";

// @ts-expect-error Svelte exposes types for its public entry, not this internal file.
vi.mock("svelte", () => import("../../node_modules/svelte/src/index-client.js"));

it("prints all results directly without a shot sheet dialogue", async () => {
  const target = document.createElement("div");
  const print = vi.spyOn(window, "print").mockImplementation(() => undefined);
  const component = mount(MarkerSheet, { target, props: {
    session: { kind: "idle" }, totalScore: 200,
    shots: Array.from({ length: 40 }, (_, i) => ({ timestamp: i, xMm: 0, yMm: 0, score: "5", shotId: i })),
  } });
  flushSync();
  expect(target.querySelectorAll("tbody tr")).toHaveLength(40);
  expect(target.textContent).toContain("200 pts");
  expect(target.querySelector('[role="dialog"]')).toBeNull();
  expect(target.querySelector("button")).toBeNull();
  await component.print();
  expect(print).toHaveBeenCalledOnce();
  await unmount(component);
  print.mockRestore();
});

it("reports native print failures and clears the error when retrying", async () => {
  const print = vi.spyOn(window, "print")
    .mockImplementationOnce(() => Promise.reject(new Error("print denied")))
    .mockImplementation(() => undefined);
  const target = document.createElement("div");
  const component = mount(MarkerSheet, { target, props: {
    session: { kind: "idle" }, totalScore: null, shots: [],
  } });
  await component.print();
  flushSync();
  expect(target.querySelector('[role="alert"]')?.textContent).toContain("print denied");
  await component.print();
  flushSync();
  expect(target.querySelector('[role="alert"]')).toBeNull();
  expect(print).toHaveBeenCalledTimes(2);
  await unmount(component);
  print.mockRestore();
});
