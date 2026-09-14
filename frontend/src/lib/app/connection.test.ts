import { afterEach, describe, expect, it, vi } from "vitest";

import type { Bridge, EventHandler, PacketHandler, Unlisten } from "../bridge/bridge";
import { FrameSink } from "../frames/sink";
import { AppState } from "../stores/app.svelte";
import { SAMPLE_EVENTS } from "../wire/samples";
import type { ShellStatus } from "../wire/types";
import { ACCESS_POLL_MS, Connection } from "./connection";

const RUNNING: ShellStatus = {
  running: true,
  error: null,
  fakeDevices: false,
  denied: [],
  awaitingAccess: false,
};
const AWAITING: ShellStatus = { ...RUNNING, awaitingAccess: true };

class FakeBridge implements Bridge {
  calls: string[] = [];
  listenResult: Promise<Unlisten> = Promise.resolve(() => undefined);
  statuses: ShellStatus[] = [];
  handler: EventHandler | null = null;
  onPacket: PacketHandler | null = null;
  readyError: Error | null = null;
  restartError: Error | null = null;

  listen(handler: EventHandler): Promise<Unlisten> {
    this.calls.push("listen");
    this.handler = handler;
    return this.listenResult;
  }

  async subscribeFrames(onPacket: PacketHandler): Promise<void> {
    this.calls.push("subscribeFrames");
    this.onPacket = onPacket;
  }

  async frontendReady(): Promise<void> {
    this.calls.push("frontendReady");
    if (this.readyError !== null) {
      throw this.readyError;
    }
  }

  async send(): Promise<void> {
    this.calls.push("send");
  }

  frameDrawn(): void {
    this.calls.push("frameDrawn");
  }

  async status(): Promise<ShellStatus> {
    this.calls.push("status");
    return this.statuses.shift() ?? RUNNING;
  }

  async restart(): Promise<void> {
    this.calls.push("restart");
    if (this.restartError !== null) {
      throw this.restartError;
    }
  }
}

function connect(bridge: FakeBridge): { app: AppState; connection: Connection } {
  const app = new AppState();
  return { app, connection: new Connection(bridge, app, new FrameSink()) };
}

afterEach(() => {
  vi.useRealTimers();
});

describe("Connection.start", () => {
  it("calls frontend_ready only after the listener has registered", async () => {
    const bridge = new FakeBridge();
    let registered: (unlisten: Unlisten) => void = () => undefined;
    bridge.listenResult = new Promise((resolve) => {
      registered = resolve;
    });
    const { connection } = connect(bridge);
    const started = connection.start();
    await Promise.resolve();
    await Promise.resolve();
    expect(bridge.calls).toEqual(["listen"]);
    registered(() => undefined);
    await started;
    expect(bridge.calls).toEqual(["listen", "subscribeFrames", "frontendReady", "status"]);
  });

  it("never calls frontend_ready when the listener cannot register", async () => {
    const bridge = new FakeBridge();
    bridge.listenResult = Promise.reject(new Error("no IPC"));
    const { app, connection } = connect(bridge);
    await connection.start();
    expect(bridge.calls).toEqual(["listen"]);
    expect(app.status.connectionError).toBe("no IPC");
  });

  it("dispatches events to the state", async () => {
    const bridge = new FakeBridge();
    const { app, connection } = connect(bridge);
    await connection.start();
    bridge.handler?.(SAMPLE_EVENTS.session);
    expect(app.session.summary).toBe("S");
  });

  it("reports every packet drawn, even one it cannot decode", async () => {
    const bridge = new FakeBridge();
    const { connection } = connect(bridge);
    await connection.start();
    bridge.onPacket?.("not pixels");
    expect(bridge.calls.at(-1)).toBe("frameDrawn");
  });

  it("asks for the status when frontend_ready is refused", async () => {
    const bridge = new FakeBridge();
    bridge.readyError = new Error("database");
    bridge.statuses = [{ ...RUNNING, running: false, error: "database" }];
    const { app, connection } = connect(bridge);
    await connection.start();
    expect(bridge.calls.at(-1)).toBe("status");
    expect(app.status.shell?.error).toBe("database");
  });

  it("asks again every second while access is awaited and stops once it is settled", async () => {
    vi.useFakeTimers();
    const bridge = new FakeBridge();
    bridge.statuses = [AWAITING, AWAITING, RUNNING];
    const { app, connection } = connect(bridge);
    await connection.start();
    const asked = (): number => bridge.calls.filter((call) => call === "status").length;
    expect(asked()).toBe(1);
    expect(app.status.shell?.awaitingAccess).toBe(true);
    await vi.advanceTimersByTimeAsync(ACCESS_POLL_MS);
    expect(asked()).toBe(2);
    await vi.advanceTimersByTimeAsync(ACCESS_POLL_MS);
    expect(asked()).toBe(3);
    expect(app.status.shell?.awaitingAccess).toBe(false);
    await vi.advanceTimersByTimeAsync(ACCESS_POLL_MS * 5);
    expect(asked()).toBe(3);
  });
});

describe("Connection.restart", () => {
  it("clears the failure and connects frames again without a second listener", async () => {
    const bridge = new FakeBridge();
    const { app, connection } = connect(bridge);
    await connection.start();
    app.dispatch(SAMPLE_EVENTS.controllerFailed);
    bridge.calls = [];
    await connection.restart();
    expect(bridge.calls).toEqual(["restart", "subscribeFrames", "frontendReady", "status"]);
    expect(app.status.failure).toBeNull();
  });

  it("keeps the failure when the shell refuses the restart", async () => {
    const bridge = new FakeBridge();
    bridge.restartError = new Error("database");
    const { app, connection } = connect(bridge);
    await connection.start();
    app.dispatch(SAMPLE_EVENTS.controllerFailed);
    bridge.calls = [];
    await connection.restart();
    expect(bridge.calls).toEqual(["restart", "status"]);
    expect(app.status.failure).toBe("boom");
  });
});
