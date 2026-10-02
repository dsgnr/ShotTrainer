import type { AvailableUpdate, UpdateBackend } from "./updates";

export class UpdateManager {
  available: AvailableUpdate | null = $state.raw(null);
  stage: "idle" | "checking" | "available" | "downloading" | "downloaded" | "installing" = $state("idle");
  error: string | null = $state(null);
  checked = $state(false);
  readonly #backend: UpdateBackend;
  readonly #recording: () => boolean;
  readonly #restore: () => Promise<void>;

  constructor(backend: UpdateBackend, recording: () => boolean, restore: () => Promise<void>) {
    this.#backend = backend;
    this.#recording = recording;
    this.#restore = restore;
  }

  get busy(): boolean {
    return ["checking", "downloading", "installing"].includes(this.stage);
  }

  async check(silent = false): Promise<void> {
    if (this.busy || this.available) return;
    this.stage = "checking";
    this.error = null;
    this.checked = false;
    try {
      this.available = await this.#backend.check();
      this.stage = this.available ? "available" : "idle";
      this.checked = true;
    } catch (error) {
      this.stage = "idle";
      if (!silent) this.error = `Could not check for updates: ${String(error)}`;
    }
  }

  async install(): Promise<void> {
    const update = this.available;
    if (!update?.selfInstall || this.busy || this.#recording()) return;
    this.error = null;
    let stopped = false;
    try {
      if (this.stage !== "downloaded") {
        this.stage = "downloading";
        await update.download();
        this.stage = "downloaded";
      }
      if (this.#recording()) return;
      this.stage = "installing";
      stopped = true;
      await this.#backend.prepare();
      await update.install();
    } catch (error) {
      this.stage = this.stage === "downloading" ? "available" : "downloaded";
      this.error = `Update failed: ${String(error)}`;
      if (stopped) {
        try { await this.#restore(); }
        catch (restoreError) { this.error += `; could not restart the controller: ${String(restoreError)}`; }
      }
    }
  }

  async dismiss(): Promise<void> {
    if (this.busy) return;
    const update = this.available;
    this.available = null;
    this.stage = "idle";
    this.error = null;
    await update?.close().catch(() => undefined);
  }

  async openReleases(): Promise<void> {
    try { await this.#backend.openReleases(); }
    catch (error) { this.error = `Could not open downloads: ${String(error)}`; }
  }
}
