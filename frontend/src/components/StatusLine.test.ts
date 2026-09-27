// @vitest-environment jsdom
import { expect, it, vi } from "vitest";
import { flushSync, mount, unmount } from "svelte";
import StatusLine from "./StatusLine.svelte";
import type { WireSessionState } from "../lib/wire/types";

// @ts-expect-error Svelte exposes types for its public entry, not this internal file.
vi.mock("svelte", () => import("../../node_modules/svelte/src/index-client.js"));

it.each([
  [{ kind: "idle" }, "Idle"],
  [{ kind: "recording", sessionId: 1 }, "Recording"],
  [{ kind: "reviewing", sessionId: 1 }, "Replay"],
] satisfies [WireSessionState, string][])("shows %j alongside controller errors", async (session, label) => {
  const footer = document.createElement("footer");
  const onrestart = vi.fn();
  const trackingText = "Tracking 60 mm circle - 0.500 mm/px";
  const status = mount(StatusLine, { target: footer, props: {
    session, trackingText, restarting: false, onrestart,
    line: { text: "The controller stopped", tone: "error", restart: true },
  } });
  flushSync();
  expect(footer.querySelector(".pill")!.textContent).toContain(label);
  expect(footer.querySelector(".hint")!.textContent).toContain(trackingText);
  expect(footer.querySelector(".text")!.textContent).toBe("The controller stopped");
  footer.querySelector("button")!.click();
  expect(onrestart).toHaveBeenCalledOnce();
  await unmount(status);
});
