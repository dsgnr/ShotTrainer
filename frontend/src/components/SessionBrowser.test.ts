// @vitest-environment jsdom
import { expect, it, vi } from "vitest";
import { flushSync, mount, unmount } from "svelte";
import { AppState } from "../lib/stores/app.svelte";
import SessionBrowser from "./SessionBrowser.svelte";

const dialog = vi.hoisted(() => ({ open: vi.fn(), save: vi.fn() }));
vi.mock("@tauri-apps/plugin-dialog", () => dialog);

// @ts-expect-error Svelte exposes types for its public entry, not this internal file.
vi.mock("svelte", () => import("../../node_modules/svelte/src/index-client.js"));

it("offers a new session on the page and disables it during recording", async () => {
  for (const recording of [false, true]) {
    const target = document.createElement("div");
    const onnew = vi.fn();
    const send = vi.fn(async () => undefined);
    const component = mount(SessionBrowser, { target, props: {
      open: true, sessions: [], recording, send, onnew, onopen: vi.fn(),
    } });
    flushSync();
    expect(send).toHaveBeenCalledWith({ type: "listSessions" });
    expect(target.querySelector('[role="dialog"]')).toBeNull();
    const button = target.querySelector<HTMLButtonElement>(".create .primary")!;
    expect(button.disabled).toBe(recording);
    button.click();
    expect(onnew).toHaveBeenCalledTimes(recording ? 0 : 1);
    await unmount(component);
  }
});

it("requests sessions once when the response updates reactive state", async () => {
  const state = new AppState();
  const target = document.createElement("div");
  const send = vi.fn(async () => {
    state.dispatch({ type: "sessions", sessions: [] });
  });
  const component = mount(SessionBrowser, { target, props: {
    open: true, get sessions() { return state.session.sessions; },
    send, onnew: vi.fn(), onopen: vi.fn(),
  } });
  flushSync();
  state.dispatch({ type: "sessions", sessions: [] });
  flushSync();
  expect(send).toHaveBeenCalledOnce();
  await unmount(component);
});

it("opens in-app dialogues and sends each confirmed session action", async () => {
  const session = { id: 7, name: "Practice", startedAt: "2026-10-09T10:00:00", endedAt: null, shotCount: 10, totalScore: 98, category: "practice", notes: "gusty\nsecond line" };
  const cases = [
    { button: "Rename...", input: " Updated name ", command: { type: "renameSession", id: 7, name: "Updated name" } },
    { button: "Category...", category: "Match", command: { type: "setSessionCategory", id: 7, category: "match" } },
    { button: "Notes...", input: " Wind from the left ", textarea: true, command: { type: "setSessionNotes", id: 7, notes: "Wind from the left" } },
    { button: "Delete", command: { type: "deleteSession", id: 7 } },
  ];
  const prompt = vi.spyOn(window, "prompt");
  const confirm = vi.spyOn(window, "confirm");
  for (const test of cases) {
    const target = document.createElement("div");
    const send = vi.fn(async () => undefined);
    const component = mount(SessionBrowser, { target, props: { open: true, sessions: [session], send, onnew: vi.fn(), onopen: vi.fn() } });
    flushSync();
    target.querySelector<HTMLElement>('[role="option"]')!.click();
    flushSync();
    [...target.querySelectorAll<HTMLButtonElement>("button")].find(button => button.textContent === test.button)!.click();
    flushSync();
    const dialog = target.querySelector<HTMLElement>('[role="dialog"]')!;
    expect(dialog).not.toBeNull();
    if (test.input !== undefined) {
      const input = dialog.querySelector<HTMLInputElement>(test.textarea ? "textarea" : "input")!;
      if (test.textarea) expect(input.value).toBe("gusty\nsecond line");
      input.value = test.input;
      input.dispatchEvent(new Event("input", { bubbles: true }));
    }
    if (test.category) {
      dialog.querySelector<HTMLButtonElement>('[aria-label="Session category"]')!.click();
      flushSync();
      [...dialog.querySelectorAll<HTMLButtonElement>('[role="menuitemradio"]')].find(button => button.textContent === test.category)!.click();
    }
    flushSync();
    dialog.querySelector("form")!.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
    await vi.waitFor(() => {
      flushSync();
      expect(send).toHaveBeenCalledWith(test.command);
      expect(target.querySelector('[role="dialog"]')).toBeNull();
    });
    await unmount(component);
  }
  expect(prompt).not.toHaveBeenCalled();
  expect(confirm).not.toHaveBeenCalled();
  prompt.mockRestore(); confirm.mockRestore();
});

it("sends the paths chosen in the OS file dialogs", async () => {
  const session = { id: 7, name: "Practice", startedAt: "2026-10-09T10:00:00", endedAt: null, shotCount: 10, totalScore: 98, category: "practice", notes: "gusty\nsecond line" };
  const click = (target: HTMLElement, label: string) =>
    [...target.querySelectorAll<HTMLButtonElement>("button")].find(button => button.textContent === label)!.click();
  const target = document.createElement("div");
  const send = vi.fn(async () => undefined);
  const component = mount(SessionBrowser, { target, props: { open: true, sessions: [session], send, onnew: vi.fn(), onopen: vi.fn() } });
  flushSync();

  dialog.open.mockResolvedValueOnce("/tmp/session_1.json");
  click(target, "Import...");
  await vi.waitFor(() => expect(send).toHaveBeenCalledWith({ type: "importSession", path: "/tmp/session_1.json" }));

  target.querySelector<HTMLElement>('[role="option"]')!.click();
  flushSync();
  dialog.save.mockResolvedValueOnce("/tmp/round.json");
  click(target, "Export...");
  await vi.waitFor(() => expect(send).toHaveBeenCalledWith({ type: "exportSession", id: 7, path: "/tmp/round.json" }));
  expect(dialog.save).toHaveBeenCalledWith(expect.objectContaining({ defaultPath: "session_7.json" }));

  send.mockClear();
  dialog.open.mockResolvedValueOnce(null);
  dialog.save.mockResolvedValueOnce(null);
  click(target, "Import...");
  click(target, "Export...");
  await vi.waitFor(() => expect(dialog.save).toHaveBeenCalledTimes(2));
  expect(send).not.toHaveBeenCalled();
  await unmount(component);
});

it("disables importing during recording", async () => {
  const target = document.createElement("div");
  const component = mount(SessionBrowser, { target, props: { open: true, sessions: [], recording: true, send: vi.fn(async () => undefined), onnew: vi.fn(), onopen: vi.fn() } });
  flushSync();
  const button = [...target.querySelectorAll<HTMLButtonElement>("button")].find(button => button.textContent === "Import...")!;
  expect(button.disabled).toBe(true);
  await unmount(component);
});
