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
    button.click();
    flushSync();
    expect(pane.hidden).toBe(true);
    expect(button.getAttribute("aria-expanded")).toBe("false");
    expect(container.querySelector("nav")).not.toBeNull();
    button.click();
    flushSync();
    expect(pane.hidden).toBe(false);
    expect(button.getAttribute("aria-expanded")).toBe("true");
  }
  await unmount(component);
  container.remove();
});
