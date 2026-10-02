import { beforeEach, expect, it, vi } from "vitest";
import { invoke, isTauri } from "@tauri-apps/api/core";
import { check } from "@tauri-apps/plugin-updater";
import { relaunch } from "@tauri-apps/plugin-process";
import { openUrl } from "@tauri-apps/plugin-opener";
import { RELEASES_URL, updateBackend } from "./updates";

vi.mock("@tauri-apps/api/core", () => ({ invoke: vi.fn(), isTauri: vi.fn(() => true) }));
vi.mock("@tauri-apps/plugin-updater", () => ({ check: vi.fn() }));
vi.mock("@tauri-apps/plugin-process", () => ({ relaunch: vi.fn(async () => undefined) }));
vi.mock("@tauri-apps/plugin-opener", () => ({ openUrl: vi.fn(async () => undefined) }));

beforeEach(() => { vi.clearAllMocks(); vi.mocked(isTauri).mockReturnValue(true); });

it("skips desktop IPC in the browser preview", async () => {
  vi.mocked(isTauri).mockReturnValue(false);
  expect(await updateBackend.check()).toBeNull();
  expect(check).not.toHaveBeenCalled();
});

it("checks with a timeout, installs before relaunching and releases resources", async () => {
  const order: string[] = [];
  const raw = { version: "0.2.0", download: vi.fn(async () => undefined), install: vi.fn(async () => { order.push("install"); }), close: vi.fn(async () => undefined) };
  vi.mocked(check).mockResolvedValue(raw as unknown as NonNullable<Awaited<ReturnType<typeof check>>>);
  vi.mocked(invoke).mockResolvedValue(true);
  vi.mocked(relaunch).mockImplementation(async () => { order.push("relaunch"); });
  const update = (await updateBackend.check())!;
  expect(check).toHaveBeenCalledExactlyOnceWith({ timeout: 15000 });
  expect(invoke).toHaveBeenCalledWith("can_self_update");
  await update.download();
  expect(raw.download).toHaveBeenCalledOnce();
  await updateBackend.prepare();
  expect(invoke).toHaveBeenCalledWith("prepare_update");
  await update.install();
  expect(order).toEqual(["install", "relaunch"]);
  await update.close();
  expect(raw.close).toHaveBeenCalledOnce();
  await updateBackend.openReleases();
  expect(openUrl).toHaveBeenCalledWith(RELEASES_URL);
});

it("closes the update resource if platform detection fails", async () => {
  const raw = { version: "0.2.0", close: vi.fn(async () => undefined) };
  vi.mocked(check).mockResolvedValue(raw as unknown as NonNullable<Awaited<ReturnType<typeof check>>>);
  vi.mocked(invoke).mockRejectedValue(new Error("IPC failed"));
  await expect(updateBackend.check()).rejects.toThrow("IPC failed");
  expect(raw.close).toHaveBeenCalledOnce();
});
