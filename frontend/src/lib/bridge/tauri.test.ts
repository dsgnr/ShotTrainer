// @vitest-environment jsdom
import { Channel } from "@tauri-apps/api/core";
import { emit } from "@tauri-apps/api/event";
import { clearMocks, mockIPC } from "@tauri-apps/api/mocks";
import { afterEach, describe, expect, it, vi } from "vitest";

import { SAMPLE_EVENTS } from "../wire/samples";
import type { ShellStatus } from "../wire/types";
import { TauriBridge, UI_EVENT } from "./tauri";

afterEach(() => {
  clearMocks();
});

function recordCalls(reply: (command: string) => unknown = () => null): [string, unknown][] {
  const calls: [string, unknown][] = [];
  mockIPC((command, args) => {
    calls.push([command, args]);
    return reply(command);
  });
  return calls;
}

describe("TauriBridge", () => {
  it("sends a command as the argument of send_command", async () => {
    const calls = recordCalls();
    await new TauriBridge().send({ type: "deleteShot", index: 2 });
    expect(calls).toEqual([["send_command", { command: { type: "deleteShot", index: 2 } }]]);
  });

  it("calls the shell's commands by their names", async () => {
    const status: ShellStatus = {
      running: true,
      error: null,
      fakeDevices: false,
      denied: ["camera"],
      awaitingAccess: false,
    };
    const calls = recordCalls((command) => (command === "controller_status" ? status : null));
    const bridge = new TauriBridge();
    await bridge.frontendReady();
    await bridge.restart();
    expect(await bridge.status()).toEqual(status);
    bridge.frameDrawn();
    await vi.waitFor(() => expect(calls).toHaveLength(4));
    expect(calls.map(([command]) => command)).toEqual([
      "frontend_ready",
      "restart_controller",
      "controller_status",
      "frame_drawn",
    ]);
  });

  it("ignores a frame_drawn the IPC refuses", async () => {
    const refused = vi.fn();
    mockIPC(() => {
      refused();
      throw new Error("IPC gone");
    });
    new TauriBridge().frameDrawn();
    await vi.waitFor(() => expect(refused).toHaveBeenCalledOnce());
  });

  it("subscribes a channel that hands packets to the page", async () => {
    const calls = recordCalls();
    const onPacket = vi.fn();
    await new TauriBridge().subscribeFrames(onPacket);
    const [command, args] = calls[0] ?? [];
    expect(command).toBe("subscribe_frames");
    const channel = (args as { onFrame: unknown }).onFrame;
    expect(channel).toBeInstanceOf(Channel);
    const packet = new ArrayBuffer(8);
    (channel as Channel<unknown>).onmessage(packet);
    expect(onPacket).toHaveBeenCalledWith(packet);
  });

  it("passes known events from ui-event to the handler and drops the rest", async () => {
    mockIPC(() => null, { shouldMockEvents: true });
    const handler = vi.fn();
    await new TauriBridge().listen(handler);
    await emit(UI_EVENT, { type: "launchMissiles" });
    await emit(UI_EVENT, SAMPLE_EVENTS.audioLevel);
    await emit("another-event", SAMPLE_EVENTS.cameraIdle);
    expect(handler).toHaveBeenCalledOnce();
    expect(handler).toHaveBeenCalledWith(SAMPLE_EVENTS.audioLevel);
  });
});
