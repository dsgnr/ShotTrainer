// @vitest-environment jsdom
import { expect, it, vi } from "vitest";
import { createRawSnippet, flushSync, mount, unmount } from "svelte";
import AppShell from "./AppShell.svelte";

// @ts-expect-error Svelte exposes types for its public entry, not this internal file.
vi.mock("svelte", () => import("../../node_modules/svelte/src/index-client.js"));

it("collapses and restores each pane while leaving navigation accessible", async () => {
  const content = createRawSnippet(() => ({ render: () => "<span>Content</span>" }));
  const container = document.createElement("div");
  document.body.append(container);
  const component = mount(AppShell, { target: container, props: {
    header: content, status: content, nav: content, shots: content, side: content,
  } });
  flushSync();
  for (const id of ["session-shots", "session-controls"]) {
    const button = container.querySelector<HTMLButtonElement>(`button[aria-controls="${id}"]`)!;
    const pane = container.querySelector<HTMLElement>(`#${id}`)!;
    const name = id === "session-shots" ? "shots" : "session";
    expect(button.getAttribute("aria-label")).toBe(`Hide ${name}`);
    expect(button.title).toBe(`Hide ${name}`);
    expect(button.textContent!.trim()).toBe("");
    expect(button.querySelector('svg[aria-hidden="true"]')).not.toBeNull();
    const arrow = button.querySelector("path:last-child")!;
    const expandedArrow = arrow.getAttribute("d");
    button.click();
    flushSync();
    expect(button.getAttribute("aria-label")).toBe(`Show ${name}`);
    expect(button.title).toBe(`Show ${name}`);
    expect(arrow.getAttribute("d")).not.toBe(expandedArrow);
    expect(pane.hidden).toBe(true);
    expect(button.getAttribute("aria-expanded")).toBe("false");
    expect(container.querySelector("nav")).not.toBeNull();
    button.click();
    flushSync();
    expect(pane.hidden).toBe(false);
    expect(button.getAttribute("aria-expanded")).toBe("true");
    expect(button.getAttribute("aria-label")).toBe(`Hide ${name}`);
    expect(button.title).toBe(`Hide ${name}`);
    expect(arrow.getAttribute("d")).toBe(expandedArrow);
  }
  const toggles = container.querySelectorAll<HTMLButtonElement>("button[aria-controls]");
  toggles[0]!.click();
  toggles[1]!.click();
  flushSync();
  expect(container.querySelector<HTMLElement>("#session-shots")!.hidden).toBe(true);
  expect(container.querySelector<HTMLElement>("#session-controls")!.hidden).toBe(true);
  toggles[0]!.click();
  flushSync();
  expect(container.querySelector<HTMLElement>("#session-shots")!.hidden).toBe(false);
  expect(container.querySelector<HTMLElement>("#session-controls")!.hidden).toBe(true);
  await unmount(component);
  container.remove();
});
