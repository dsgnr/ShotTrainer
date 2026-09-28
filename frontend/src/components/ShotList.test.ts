// @vitest-environment jsdom
import { expect, it, vi } from "vitest";
import { flushSync, mount, unmount } from "svelte";
import { AppState } from "../lib/stores/app.svelte";
import ShotList from "./ShotList.svelte";

// @ts-expect-error Svelte exposes types for its public entry, not this internal file.
vi.mock("svelte", () => import("../../node_modules/svelte/src/index-client.js"));

it("moves focus with arrow selection without bubbling to global shortcuts", async () => {
  const target = document.createElement("div");
  document.body.append(target);
  const state = new AppState();
  state.dispatch({ type: "selectedShot", index: 0 });
  const send = vi.fn(async (command) => {
    if (command.type === "selectShot") state.dispatch({ type: "selectedShot", index: command.index });
  });
  const globalKey = vi.fn();
  window.addEventListener("keydown", globalKey);
  const component = mount(ShotList, { target, props: {
    get selected() { return state.shots.selected; }, send,
    shots: Array.from({ length: 3 }, (_, i) => ({ timestamp: i, xMm: 0, yMm: 0, score: "5", shotId: i })),
  } });
  flushSync();
  const rows = target.querySelectorAll<HTMLElement>('[role="option"]');
  rows[0]!.focus();
  rows[0]!.click();
  send.mockClear();
  rows[0]!.dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowDown", bubbles: true }));
  flushSync();
  expect(send).toHaveBeenCalledExactlyOnceWith({ type: "selectShot", index: 1 });
  expect(globalKey).not.toHaveBeenCalled();
  expect(target.querySelector(".keyboard-navigation")).not.toBeNull();
  expect(rows[0]!.tabIndex).toBe(-1);
  expect(document.activeElement).toBe(rows[1]);
  expect(target.querySelectorAll('[aria-selected="true"]')).toHaveLength(1);
  rows[1]!.dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowUp", bubbles: true }));
  flushSync();
  expect(document.activeElement).toBe(rows[0]);
  await unmount(component);
  window.removeEventListener("keydown", globalKey);
  target.remove();
});
