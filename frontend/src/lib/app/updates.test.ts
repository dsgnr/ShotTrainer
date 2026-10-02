import { expect, it, vi } from "vitest";
import { UpdateManager } from "./updates.svelte";
import type { AvailableUpdate, UpdateBackend } from "./updates";

// @ts-expect-error Svelte exposes types for its public entry, not this internal file.
vi.mock("svelte", () => import("../../../node_modules/svelte/src/index-client.js"));

function setup(selfInstall = true) {
  let recording = false;
  const order: string[] = [];
  const update: AvailableUpdate = {
    version: "0.2.0", selfInstall,
    download: vi.fn(async () => { order.push("download"); }),
    install: vi.fn(async () => { order.push("install"); }),
    close: vi.fn(async () => undefined),
  };
  const backend: UpdateBackend = {
    check: vi.fn(async () => update),
    prepare: vi.fn(async () => { order.push("prepare"); }),
    openReleases: vi.fn(async () => undefined),
  };
  const restore = vi.fn(async () => undefined);
  const manager = new UpdateManager(backend, () => recording, restore);
  return { manager, backend, update, restore, order, setRecording: (next: boolean) => { recording = next; } };
}

it("checks once and does not overlap or replace an offered update", async () => {
  const { manager, backend } = setup();
  const promise = manager.check(true);
  await manager.check();
  await promise;
  await manager.check();
  expect(backend.check).toHaveBeenCalledOnce();
  expect(manager.available?.version).toBe("0.2.0");
});

it("keeps automatic failures quiet and reports manual check failures", async () => {
  const { manager, backend } = setup();
  vi.mocked(backend.check).mockRejectedValue(new Error("offline"));
  await manager.check(true);
  expect(manager.error).toBeNull();
  expect(manager.checked).toBe(false);
  await manager.check();
  expect(manager.error).toContain("offline");
  expect(manager.checked).toBe(false);
  vi.mocked(backend.check).mockResolvedValue(null);
  await manager.check();
  expect(manager.checked).toBe(true);
  expect(manager.error).toBeNull();
});

it("downloads then stops the controller before installing", async () => {
  const { manager, order } = setup();
  await manager.check();
  await manager.install();
  expect(order).toEqual(["download", "prepare", "install"]);
});

it("refuses installation during recording and pauses if recording starts during download", async () => {
  const { manager, update, backend, setRecording } = setup();
  await manager.check();
  setRecording(true);
  await manager.install();
  expect(update.download).not.toHaveBeenCalled();
  setRecording(false);
  vi.mocked(update.download).mockImplementation(async () => { setRecording(true); });
  await manager.install();
  expect(manager.stage).toBe("downloaded");
  expect(backend.prepare).not.toHaveBeenCalled();
  expect(update.install).not.toHaveBeenCalled();
  setRecording(false);
  await manager.install();
  expect(update.download).toHaveBeenCalledOnce();
  expect(update.install).toHaveBeenCalledOnce();
});

it("restores the controller after an install failure and retries downloaded bytes", async () => {
  const { manager, update, restore } = setup();
  await manager.check();
  vi.mocked(update.install).mockRejectedValueOnce(new Error("installer failed"));
  await manager.install();
  expect(manager.error).toContain("installer failed");
  expect(restore).toHaveBeenCalledOnce();
  expect(manager.stage).toBe("downloaded");
  await manager.install();
  expect(update.download).toHaveBeenCalledOnce();
  expect(update.install).toHaveBeenCalledTimes(2);
});

it("retries download failures without shutting down the controller", async () => {
  const { manager, update, backend, restore } = setup();
  await manager.check();
  vi.mocked(update.download).mockRejectedValueOnce(new Error("bad signature"));
  await manager.install();
  expect(manager.error).toContain("bad signature");
  expect(manager.stage).toBe("available");
  expect(backend.prepare).not.toHaveBeenCalled();
  expect(restore).not.toHaveBeenCalled();
  await manager.install();
  expect(update.download).toHaveBeenCalledTimes(2);
});

it("disables repeated installs and dismissal while downloading", async () => {
  const { manager, update } = setup();
  await manager.check();
  let finish!: () => void;
  vi.mocked(update.download).mockImplementation(() => new Promise<void>(resolve => { finish = resolve; }));
  const install = manager.install();
  await manager.install();
  await manager.dismiss();
  expect(manager.available).not.toBeNull();
  expect(update.download).toHaveBeenCalledOnce();
  finish();
  await install;
});

it("closes deferred updates and offers downloads for Linux package installs", async () => {
  const { manager, update, backend } = setup(false);
  await manager.check();
  await manager.install();
  expect(update.download).not.toHaveBeenCalled();
  await manager.openReleases();
  expect(backend.openReleases).toHaveBeenCalledOnce();
  await manager.dismiss();
  expect(update.close).toHaveBeenCalledOnce();
  expect(manager.available).toBeNull();
});
