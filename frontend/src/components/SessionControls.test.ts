// @vitest-environment jsdom
import { expect, it, vi } from "vitest";
import { flushSync, mount, unmount } from "svelte";
import SessionControls from "./SessionControls.svelte";

// @ts-expect-error Svelte exposes types for its public entry, not this internal file.
vi.mock("svelte", () => import("../../node_modules/svelte/src/index-client.js"));

it("starts with the prepared name and category without a dialog", async () => {
  const target = document.createElement("div");
  const send = vi.fn(async () => undefined);
  const component = mount(SessionControls, { target, props: {
    session: { kind: "idle" }, summary: "", name: "Morning", category: "match", send,
  } });
  flushSync();
  target.querySelector<HTMLButtonElement>("button")!.click();
  expect(send).toHaveBeenCalledExactlyOnceWith({ type: "startSession", name: "Morning", category: "match" });
  expect(target.querySelector('[role="dialog"]')).toBeNull();
  await unmount(component);
});

it("opens creation when reviewing without starting a recording", async () => {
  const target = document.createElement("div");
  const send = vi.fn(async () => undefined);
  const onnew = vi.fn();
  const component = mount(SessionControls, { target, props: {
    session: { kind: "reviewing", sessionId: 1 }, summary: "Reviewing session 1", send, onnew,
  } });
  flushSync();
  expect(target.querySelector(".summary")).toBeNull();
  target.querySelector<HTMLButtonElement>("button")!.click();
  expect(onnew).toHaveBeenCalledOnce();
  expect(send).not.toHaveBeenCalled();
  await unmount(component);
});

it("stops recording immediately without asking for a name", async () => {
  const container = document.createElement("div");
  const send = vi.fn(async () => undefined);
  const component = mount(SessionControls, {
    target: container, props: { session: { kind: "recording", sessionId: 1 }, summary: "", send },
  });
  flushSync();
  expect(container.querySelector(".clear")).toBeNull();
  container.querySelector<HTMLButtonElement>(".primary")!.click();
  flushSync();
  expect(send).toHaveBeenCalledExactlyOnceWith({ type: "stopSession" });
  expect(container.querySelector("[role=dialog]")).toBeNull();
  await unmount(component);
});
