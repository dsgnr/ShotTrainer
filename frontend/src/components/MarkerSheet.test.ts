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
