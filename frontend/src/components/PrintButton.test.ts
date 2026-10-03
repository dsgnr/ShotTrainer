// @vitest-environment jsdom
import { expect, it, vi } from "vitest";
import { flushSync, mount, unmount } from "svelte";
import PrintButton from "./PrintButton.svelte";

// @ts-expect-error Svelte exposes types for its public entry, not this internal file.
vi.mock("svelte", () => import("../../node_modules/svelte/src/index-client.js"));

it("offers a labelled icon button that invokes printing", async () => {
  const target = document.createElement("div");
  const onprint = vi.fn();
  const component = mount(PrintButton, { target, props: { onprint } });
  flushSync();
  const button = target.querySelector<HTMLButtonElement>('[aria-label="Print shot sheet"]')!;
  expect(button.title).toBe("Print shot sheet");
  expect(button.textContent?.trim()).toBe("");
  expect(button.querySelector('svg[aria-hidden="true"]')).not.toBeNull();
  button.click();
  expect(onprint).toHaveBeenCalledOnce();
  await unmount(component);
});
