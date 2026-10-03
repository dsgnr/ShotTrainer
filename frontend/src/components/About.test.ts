// @vitest-environment jsdom
import { getVersion } from "@tauri-apps/api/app";
import { isTauri } from "@tauri-apps/api/core";
import { expect, it, vi } from "vitest";
import { flushSync, mount, tick, unmount } from "svelte";
import About from "./About.svelte";
import NavRail from "./NavRail.svelte";

// @ts-expect-error Svelte exposes types for its public entry, not this internal file.
vi.mock("svelte", () => import("../../node_modules/svelte/src/index-client.js"));

vi.mock("@tauri-apps/api/app", () => ({ getVersion: vi.fn(async () => "2.3.4") }));
vi.mock("@tauri-apps/api/core", () => ({ isTauri: vi.fn(() => true) }));

it("shows the installed version and GitHub repository", async () => {
  const target = document.createElement("div");
  const component = mount(About, { target });
  flushSync();
  await tick();
  flushSync();
  expect(getVersion).toHaveBeenCalled();
  expect(target.textContent).toContain("Version 2.3.4");
  expect(target.querySelector("a")?.getAttribute("href")).toBe("https://github.com/dsgnr/ShotTrainer");
  await unmount(component);
});

it("opens About from navigation and marks it as current", async () => {
  const target = document.createElement("div");
  const onabout = vi.fn();
  const component = mount(NavRail, { target, props: { page: "about", onabout, onsessions: vi.fn(), onpreferences: vi.fn(), onpopout: vi.fn() } });
  flushSync();
  const button = target.querySelector<HTMLButtonElement>('[aria-label="About"]')!;
  expect(target.querySelectorAll('[aria-current="page"]')).toHaveLength(1);
  expect(button.getAttribute("aria-current")).toBe("page");
  button.click();
  expect(onabout).toHaveBeenCalledOnce();
  await unmount(component);
});

it("labels browser preview without calling desktop IPC", async () => {
  vi.mocked(isTauri).mockReturnValueOnce(false).mockReturnValueOnce(false);
  vi.mocked(getVersion).mockClear();
  const target = document.createElement("div");
  const component = mount(About, { target });
  flushSync();
  expect(target.textContent).toContain("Browser preview");
  expect(getVersion).not.toHaveBeenCalled();
  await unmount(component);
});
