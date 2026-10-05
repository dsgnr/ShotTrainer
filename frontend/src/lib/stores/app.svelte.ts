import type { ShellStatus, WireEvent } from "../wire/types";
import { initialCamera, reduceCamera, type CameraState } from "./camera";
import { initialDevices, reduceDevices, type DevicesState } from "./devices";
import { initialPreferences, reducePreferences, type PreferencesState } from "./preferences";
import { initialReplay, reduceReplay, type ReplayState } from "./replay";
import { initialSession, reduceSession, type SessionState } from "./session";
import { initialShots, reduceShots, type ShotsState } from "./shots";
import { initialStatus, reduceStatus, type StatusState } from "./status";

/**
 * Everything the views read, updated from controller events. Each store is
 * replaced as a whole by its reducer, so `$state.raw` notifies only the
 * readers of a store an event changed.
 */
export class AppState {
  session: SessionState = $state.raw(initialSession);
  shots: ShotsState = $state.raw(initialShots);
  preferences: PreferencesState = $state.raw(initialPreferences);
  status: StatusState = $state.raw(initialStatus);
  replay: ReplayState = $state.raw(initialReplay);
  devices: DevicesState = $state.raw(initialDevices);
  camera: CameraState = $state.raw(initialCamera);

  readonly #now: () => number;

  constructor(now: () => number = Date.now) {
    this.#now = now;
  }

  dispatch(event: WireEvent): void {
    this.session = reduceSession(this.session, event);
    this.shots = reduceShots(this.shots, event);
    this.preferences = reducePreferences(this.preferences, event);
    this.status = reduceStatus(this.status, event, this.#now());
    this.replay = reduceReplay(this.replay, event);
    this.devices = reduceDevices(this.devices, event);
    this.camera = reduceCamera(this.camera, event);
  }

  setShellStatus(shell: ShellStatus): void {
    this.status = { ...this.status, shell, connectionError: null };
  }

  clearFailure(): void {
    if (this.status.failure !== null) {
      this.status = { ...this.status, failure: null };
    }
  }

  setConnectionError(error: string): void {
    this.status = { ...this.status, connectionError: error };
  }
}
