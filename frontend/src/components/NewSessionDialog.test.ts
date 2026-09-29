// @vitest-environment jsdom
import { expect, it, vi } from "vitest";
import { flushSync, mount, unmount } from "svelte";
import NewSessionDialog from "./NewSessionDialog.svelte";
import { MOCK_PREFERENCES } from "../lib/bridge/mock";
// @ts-expect-error Svelte exposes types for its public entry, not this internal file.
vi.mock("svelte", () => import("../../node_modules/svelte/src/index-client.js"));
it("collects metadata and session settings before creating", async () => {
  const target = document.createElement("div"); document.body.append(target);
  const oncreate = vi.fn(async () => undefined); const onclose = vi.fn();
  const component = mount(NewSessionDialog, { target, props: {
    prefs: MOCK_PREFERENCES, faces: [], oncreate, onclose,
  } }); flushSync();
  const name = target.querySelector<HTMLInputElement>('input[type="text"]')!;
  name.value = "  Morning  "; name.dispatchEvent(new Event("input", { bubbles: true }));
  const pre = target.querySelector<HTMLInputElement>('input[type="number"]')!;
  pre.value = "2500"; pre.dispatchEvent(new Event("input", { bubbles: true }));
  target.querySelector<HTMLButtonElement>('[aria-label="Session category"]')!.click(); flushSync();
  [...target.querySelectorAll<HTMLButtonElement>('[role="menuitemradio"]')].find(b => b.textContent === "Match")!.click(); flushSync();
  target.querySelector("form")!.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
  expect(oncreate).toHaveBeenCalledWith("Morning", "match", expect.objectContaining({ preShotMs: 2500 }));
  expect(onclose).not.toHaveBeenCalled();
  await unmount(component); target.remove();
});
it("cancels without creating or modifying the supplied settings", async () => {
  const target = document.createElement("div"); document.body.append(target);
  const oncreate = vi.fn(async () => undefined); const onclose = vi.fn();
  const prefs = { ...MOCK_PREFERENCES }; const before = { ...prefs };
  const component = mount(NewSessionDialog, { target, props: { prefs, faces: [], oncreate, onclose } }); flushSync();
  target.querySelector<HTMLButtonElement>('footer button[type="button"]')!.click();
  expect(onclose).toHaveBeenCalledOnce(); expect(oncreate).not.toHaveBeenCalled(); expect(prefs).toEqual(before);
  await unmount(component); target.remove();
});
