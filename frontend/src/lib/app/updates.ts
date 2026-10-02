import { invoke, isTauri } from "@tauri-apps/api/core";
import { openUrl } from "@tauri-apps/plugin-opener";
import { relaunch } from "@tauri-apps/plugin-process";
import { check } from "@tauri-apps/plugin-updater";

export const RELEASES_URL = "https://github.com/dsgnr/ShotTrainer/releases";

export interface AvailableUpdate {
  version: string;
  selfInstall: boolean;
  download(): Promise<void>;
  install(): Promise<void>;
  close(): Promise<void>;
}

export interface UpdateBackend {
  check(): Promise<AvailableUpdate | null>;
  prepare(): Promise<void>;
  openReleases(): Promise<void>;
}

export const updateBackend: UpdateBackend = {
  async check() {
    if (!isTauri()) return null;
    const update = await check({ timeout: 15000 });
    if (!update) return null;
    try {
      return {
        version: update.version,
        selfInstall: await invoke<boolean>("can_self_update"),
        download: () => update.download(),
        install: async () => { await update.install(); await relaunch(); },
        close: () => update.close(),
      };
    } catch (error) {
      await update.close();
      throw error;
    }
  },
  prepare: () => invoke("prepare_update"),
  openReleases: () => openUrl(RELEASES_URL),
};
