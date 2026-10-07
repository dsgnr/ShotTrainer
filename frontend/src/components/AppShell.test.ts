// @vitest-environment jsdom
import { expect, it, vi } from "vitest";
import { createRawSnippet, flushSync, mount, unmount } from "svelte";
import AppShell from "./AppShell.svelte";
import NavRail from "./NavRail.svelte";

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

it("shows the app logo in navigation with only pane toggles in the header", async () => {
  const content = createRawSnippet(() => ({ render: () => "<span>Content</span>" }));
  const container = document.createElement("div");
  const component = mount(AppShell, { target: container, props: {
    status: content, nav: content,
  } });
  const nav = container.querySelector("nav")!;
  const rail = mount(NavRail, { target: nav, props: {
    onsessions: vi.fn(), onpreferences: vi.fn(), onpopout: vi.fn(),
  } });
  flushSync();
  const logo = nav.querySelector<HTMLImageElement>('img[alt="ShotTrainer"]')!;
  expect(logo.getAttribute("src")).toBe("/icon.svg");
  expect(logo.closest("button, a")).toBeNull();
  expect(nav.querySelector('button[aria-label="Target"] svg')).not.toBeNull();
  expect(nav.querySelector('button[aria-label="Shot sheet"]')).toBeNull();
  const header = container.querySelector("header")!;
  expect(header.querySelector("img")).toBeNull();
  expect(header.textContent!.trim()).toBe("");
  expect(header.querySelectorAll("button")).toHaveLength(2);
  await unmount(rail);
  await unmount(component);
});

it("uses the whole content area for a page without target pane controls", async () => {
  const content = createRawSnippet(() => ({ render: () => "<h1>Sessions</h1>" }));
  const container = document.createElement("div");
  const component = mount(AppShell, { target: container, props: { status: content, page: content } });
  flushSync();
  expect(container.querySelector("main h1")?.textContent).toBe("Sessions");
  expect(container.querySelector("aside")).toBeNull();
  expect(container.querySelector("header")).toBeNull();
  await unmount(component);
});

it("marks only the selected navigation page as current", async () => {
  const target = document.createElement("div");
  const ontarget = vi.fn();
  const component = mount(NavRail, { target, props: {
    page: "sessions", ontarget, onsessions: vi.fn(), onpreferences: vi.fn(), onpopout: vi.fn(),
  } });
  flushSync();
  expect(target.querySelectorAll('[aria-current="page"]')).toHaveLength(1);
  expect(target.querySelector('[aria-current="page"]')?.getAttribute("aria-label")).toBe("Sessions");
  target.querySelector<HTMLButtonElement>('[aria-label="Target"]')!.click();
  expect(ontarget).toHaveBeenCalledOnce();
  await unmount(component);
});

it("offers a labelled header icon button that invokes printing", async () => {
  const content = createRawSnippet(() => ({ render: () => "<span>Content</span>" }));
  const target = document.createElement("div");
  const onprint = vi.fn();
  const component = mount(AppShell, { target, props: { status: content, onprint } });
  flushSync();
  const button = target.querySelector<HTMLButtonElement>('header [aria-label="Print shot sheet"]')!;
  expect(button.title).toBe("Print shot sheet");
  expect(button.textContent?.trim()).toBe("");
  expect(button.querySelector('svg[aria-hidden="true"]')).not.toBeNull();
  button.click();
  expect(onprint).toHaveBeenCalledOnce();
  await unmount(component);
});
