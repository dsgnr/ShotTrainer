import { describe, expect, it } from "vitest";

import { SAMPLE_EVENTS } from "../wire/samples";
import { AppState } from "./app.svelte";

describe("AppState", () => {
  it("changes only the stores an event concerns", () => {
    const app = new AppState(() => 1000);
    const stores = {
      session: app.session,
      shots: app.shots,
      preferences: app.preferences,
      status: app.status,
      replay: app.replay,
      devices: app.devices,
      camera: app.camera,
    };
    app.dispatch(SAMPLE_EVENTS.session);
    expect(app.session.summary).toBe("S");
    expect(app.session).not.toBe(stores.session);
    expect(app.shots).toBe(stores.shots);
    expect(app.preferences).toBe(stores.preferences);
    expect(app.status).toBe(stores.status);
    expect(app.replay).toBe(stores.replay);
    expect(app.devices).toBe(stores.devices);
    expect(app.camera).toBe(stores.camera);
  });

  it("stamps messages with its clock", () => {
    const app = new AppState(() => 1234);
    app.dispatch(SAMPLE_EVENTS.message);
    expect(app.status.messageAt).toBe(1234);
  });

  it("clears a connection error when the shell answers and a failure on request", () => {
    const app = new AppState();
    app.setConnectionError("no IPC");
    app.dispatch(SAMPLE_EVENTS.controllerFailed);
    app.setShellStatus({ running: false, error: null, fakeDevices: true, denied: [], awaitingAccess: false });
    expect(app.status.connectionError).toBeNull();
    expect(app.status.shell?.fakeDevices).toBe(true);
    expect(app.status.failure).toBe("boom");
    app.clearFailure();
    expect(app.status.failure).toBeNull();
  });
});
