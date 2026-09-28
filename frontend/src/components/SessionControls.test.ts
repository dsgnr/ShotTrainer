// @vitest-environment jsdom
import { expect, it, vi } from "vitest";
import { flushSync, mount, unmount } from "svelte";
import SessionControls from "./SessionControls.svelte";

// @ts-expect-error Svelte exposes types for its public entry, not this internal file.
vi.mock("svelte", () => import("../../node_modules/svelte/src/index-client.js"));

it("asks for a name only when starting and submits the trimmed name and category", async () => {
  const container = document.createElement("div");
  document.body.append(container);
  const send = vi.fn(async () => undefined);
  const component = mount(SessionControls, {
    target: container, props: { session: { kind: "idle" }, summary: "", send },
  });
  flushSync();
  expect(container.querySelector(".clear")).toBeNull();
  expect(container.querySelector("input")).toBeNull();
  expect(container.querySelector("select")).toBeNull();
  container.querySelector<HTMLButtonElement>(".session .primary")!.click();
  flushSync();
  expect(send).not.toHaveBeenCalled();
  const input = container.querySelector<HTMLInputElement>("[role=dialog] input")!;
  container.querySelector<HTMLButtonElement>('[aria-label="Session category"]')!.click();
  flushSync();
  [...container.querySelectorAll<HTMLButtonElement>('[role="menuitemradio"]')]
    .find((item) => item.textContent === "Match")!.click();
  flushSync();
  input.value = "  Morning practice  ";
  input.dispatchEvent(new Event("input", { bubbles: true }));
  container.querySelector("form")!.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
  flushSync();
  expect(send).toHaveBeenCalledExactlyOnceWith({ type: "startSession", name: "Morning practice", category: "match" });
  expect(container.querySelector("[role=dialog]")).toBeNull();
  await unmount(component);
  container.remove();
});

it("cancels the name dialog with Cancel or Escape without starting", async () => {
  const container = document.createElement("div");
  document.body.append(container);
  const send = vi.fn(async () => undefined);
  const component = mount(SessionControls, {
    target: container, props: { session: { kind: "reviewing", sessionId: 1 }, summary: "", send },
  });
  flushSync();
  expect(container.querySelector(".clear")).toBeNull();
  for (const action of ["cancel", "escape"]) {
    container.querySelector<HTMLButtonElement>(".session .primary")!.click();
    flushSync();
    if (action === "cancel") {
      container.querySelector<HTMLButtonElement>('.actions button[type="button"]')!.click();
    } else {
      container.querySelector("input")!.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
    }
    flushSync();
    expect(container.querySelector("[role=dialog]")).toBeNull();
    expect(send).not.toHaveBeenCalled();
  }
  await unmount(component);
  container.remove();
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
