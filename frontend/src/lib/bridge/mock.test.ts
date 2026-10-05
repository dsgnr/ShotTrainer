import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { decodePacket } from "../frames/packet";
import type { EventOf, WireEvent, WireEventType } from "../wire/types";
import { MOCK_FRAME_MS, MOCK_HEIGHT, MOCK_SHOT_EVERY_FRAMES, MOCK_WIDTH, MockBridge } from "./mock";

let bridge: MockBridge;
let events: WireEvent[];
let packets: ArrayBuffer[];

function ofType<T extends WireEventType>(type: T): EventOf<T>[] {
  return events.filter((event): event is EventOf<T> => event.type === type);
}

beforeEach(async () => {
  vi.useFakeTimers();
  bridge = new MockBridge();
  events = [];
  packets = [];
  await bridge.listen((event) => events.push(event));
  await bridge.subscribeFrames((message) => packets.push(message as ArrayBuffer));
});

afterEach(() => {
  bridge.close();
  vi.useRealTimers();
});

describe("MockBridge", () => {
  it("sends pixels for at most two frames until one is drawn", () => {
    vi.advanceTimersByTime(MOCK_FRAME_MS * 10);
    expect(ofType("frame")).toHaveLength(10);
    expect(packets).toHaveLength(2);
    bridge.frameDrawn();
    vi.advanceTimersByTime(MOCK_FRAME_MS);
    expect(packets).toHaveLength(3);
  });

  it("sends packets that decode to the frame their event names", () => {
    vi.advanceTimersByTime(MOCK_FRAME_MS);
    const packet = decodePacket(packets[0] ?? new ArrayBuffer(0));
    const frame = ofType("frame")[0];
    expect(packet?.frameId).toBe(frame?.frameId);
    expect([packet?.width, packet?.height]).toEqual([MOCK_WIDTH, MOCK_HEIGHT]);
    expect(frame?.tracePointMm).not.toBeNull();
  });

  it("sends the state a page needs when it is ready", async () => {
    await bridge.frontendReady();
    expect(events.map((event) => event.type)).toEqual([
      "preferences",
      "zeroOffset",
      "session",
      "shots",
      "deviceOptions",
      "trackingStatusText",
    ]);
  });

  it("records a shot every 5 seconds while a session runs", async () => {
    await bridge.send({ type: "startSession", name: "", category: "practice" });
    expect(ofType("session").at(-1)?.state).toEqual({ kind: "recording", sessionId: 1 });
    vi.advanceTimersByTime(MOCK_FRAME_MS * MOCK_SHOT_EVERY_FRAMES);
    expect(ofType("shots").at(-1)?.shots).toHaveLength(1);
    await bridge.send({ type: "stopSession" });
    expect(ofType("session").at(-1)).toMatchObject({ state: { kind: "idle" }, summary: "Saved session 1" });
  });

  it("answers a command it cannot perform with a message", async () => {
    await bridge.send({ type: "zeroOnAim" });
    expect(ofType("message").at(-1)?.message.text).toBe("Not available in the browser preview");
  });

  it("reports fake devices that need no access prompt", async () => {
    expect(await bridge.status()).toEqual({
      running: true,
      error: null,
      fakeDevices: true,
      denied: [],
      awaitingAccess: false,
    });
  });
});
