// @vitest-environment jsdom
import { expect, it, vi } from "vitest";
import { flushSync, mount, unmount } from "svelte";
import { AppState } from "../lib/stores/app.svelte";
import { resolveShortcut } from "../lib/app/shortcuts";
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
    shots: Array.from({ length: 3 }, (_, i) => ({ timestamp: i, xMm: 0, yMm: 0, score: "5", shotId: i, seriesIndex: i === 0 ? 0 : 1 })),
  } });
  flushSync();
  expect([...target.querySelectorAll(".series")].map(row => row.textContent)).toEqual(["Series 1", "Series 2"]);
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


it("lets Space toggle replay after a row click while Enter still selects", async () => {
  const target = document.createElement("div"); document.body.append(target);
  const send = vi.fn(async (_command: import("../lib/wire/types").WireCommand) => undefined);
  let playing = false;
  const shortcut = (event: KeyboardEvent) => {
    const action = resolveShortcut({key: event.key, typing: false, modalOpen: false,
      replayEnabled: true, replayPlaying: playing, shotCount: 1, selected: 0});
    if (action?.kind === "replayToggle") {
      event.preventDefault();
      void send({type: action.play ? "replayPlay" : "replayPause"});
      playing = action.play;
    }
  };
  window.addEventListener("keydown", shortcut);
  const component = mount(ShotList, {target, props: {selected: 0, send,
    shots: [{timestamp: 1, xMm: 0, yMm: 0, score: "10", shotId: 1}]}});
  flushSync();
  const row = target.querySelector<HTMLElement>('[role="option"]')!;
  row.click(); send.mockClear();
  const space = new KeyboardEvent("keydown", {key: " ", bubbles: true, cancelable: true});
  row.dispatchEvent(space);
  expect(space.defaultPrevented).toBe(true);
  expect(send).toHaveBeenCalledExactlyOnceWith({type: "replayPlay"});
  send.mockClear();
  row.dispatchEvent(new KeyboardEvent("keydown", {key: " ", bubbles: true, cancelable: true}));
  expect(send).toHaveBeenCalledExactlyOnceWith({type: "replayPause"});
  send.mockClear();
  row.dispatchEvent(new KeyboardEvent("keydown", {key: "Enter", bubbles: true}));
  expect(send).toHaveBeenCalledExactlyOnceWith({type: "selectShot", index: 0});
  window.removeEventListener("keydown", shortcut);
  await unmount(component); target.remove();
});

it("can hide offsets and their direction arrows without hiding shots", async () => {
  for (const showOffsets of [true, false]) {
    const target = document.createElement("div"); document.body.append(target);
    const component = mount(ShotList, {target, props: {selected: null, showOffsets, send: async () => {},
      shots: [{timestamp: 1, xMm: 4, yMm: 3, score: "9", shotId: 1}, {timestamp: 2, xMm: 0, yMm: 0, score: "10", shotId: 2}]}});
    flushSync();
    expect(target.querySelectorAll('[role="option"]')).toHaveLength(2);
    expect(target.querySelectorAll('.offset')).toHaveLength(showOffsets ? 2 : 0);
    expect(target.querySelectorAll('[aria-label="Towards target centre"]')).toHaveLength(showOffsets ? 1 : 0);
    expect(target.querySelector('.columns')!.textContent!.includes("Offset")).toBe(showOffsets);
    await unmount(component); target.remove();
  }
});
