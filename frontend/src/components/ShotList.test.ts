// @vitest-environment jsdom
import { expect, it, vi } from "vitest";
import { flushSync, mount, unmount } from "svelte";
import { AppState } from "../lib/stores/app.svelte";
import { resolveShortcut } from "../lib/app/shortcuts";
import { SAMPLE_EVENTS } from "../lib/wire/samples";
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


it("renders only the rows near the viewport and moves focus to a far selection", async () => {
  const target = document.createElement("div");
  document.body.append(target);
  const state = new AppState();
  const send = vi.fn(async () => undefined);
  const shots = Array.from({ length: 3000 }, (_, i) => ({ timestamp: i, xMm: 1, yMm: 1, score: "9", shotId: i }));
  const component = mount(ShotList, { target, props: {
    get selected() { return state.shots.selected; }, send, shots,
  } });
  flushSync();

  const options = () => [...target.querySelectorAll<HTMLElement>('[role="option"]')];
  expect(options().length).toBeGreaterThan(0);
  expect(options().length).toBeLessThan(100);
  expect(options()[0]!.getAttribute("aria-setsize")).toBe("3000");
  expect(target.querySelector(".count")!.textContent).toBe("3000");

  options()[0]!.focus();
  state.dispatch({ type: "selectedShot", index: 2500 });
  flushSync();

  expect(options().length).toBeLessThan(100);
  const row = target.querySelector<HTMLElement>('[data-index="2500"]')!;
  expect(row.getAttribute("aria-selected")).toBe("true");
  expect(row.getAttribute("aria-posinset")).toBe("2501");
  expect(document.activeElement).toBe(row);
  expect(options().filter(option => option.tabIndex === 0)).toEqual([row]);

  await unmount(component);
  target.remove();
});

it("keeps the scroll position when the same number of shots is sent again", async () => {
  const target = document.createElement("div");
  document.body.append(target);
  const state = new AppState();
  const make = () => Array.from({ length: 3000 }, (_, i) => ({ timestamp: i, xMm: 1, yMm: 1, score: "9", shotId: i }));
  state.dispatch({ type: "shots", shots: make(), group: SAMPLE_EVENTS.shots.group, totalScore: 0 });
  const component = mount(ShotList, { target, props: {
    get selected() { return state.shots.selected; }, get shots() { return state.shots.shots; },
    send: async () => undefined,
  } });
  flushSync();
  // A new list is followed to its last shot, then a selection near the top scrolls back up.
  expect(target.querySelector('[data-index="2999"]')).not.toBeNull();
  state.dispatch({ type: "selectedShot", index: 5 });
  flushSync();
  expect(target.querySelector('[data-index="5"]')).not.toBeNull();

  state.dispatch({ type: "shots", shots: make(), group: SAMPLE_EVENTS.shots.group, totalScore: 0 });
  flushSync();
  expect(target.querySelector('[data-index="5"]')).not.toBeNull();
  expect(target.querySelector('[data-index="2999"]')).toBeNull();

  await unmount(component);
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
