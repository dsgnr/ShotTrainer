// @vitest-environment jsdom
import { expect, it, vi } from "vitest";
import { flushSync, mount, unmount } from "svelte";
import { AppState } from "../lib/stores/app.svelte";
import SessionBrowser from "./SessionBrowser.svelte";

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
    const button = target.querySelector<HTMLButtonElement>("header button")!;
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

it("imports an exported shots file and prevents import while recording", async () => {
  const prompt = vi.spyOn(window, "prompt").mockReturnValue(" /tmp/session_1_shots.csv ");
  for (const recording of [false, true]) {
    const target = document.createElement("div");
    const send = vi.fn(async () => undefined);
    const component = mount(SessionBrowser, { target, props: { open: true, sessions: [], recording, send, onnew: vi.fn(), onopen: vi.fn() } });
    flushSync();
    const button = [...target.querySelectorAll<HTMLButtonElement>("button")].find(button => button.textContent === "Import CSV...")!;
    expect(button.disabled).toBe(recording);
    button.click();
    if (!recording) expect(send).toHaveBeenCalledWith({ type: "importSession", path: "/tmp/session_1_shots.csv" });
    else expect(send).not.toHaveBeenCalledWith(expect.objectContaining({ type: "importSession" }));
    await unmount(component);
  }
  prompt.mockRestore();
});
