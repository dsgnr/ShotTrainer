import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { decodePacket } from "../frames/packet";
import type { EventOf, WireEvent, WireEventType } from "../wire/types";
import { MOCK_PREFERENCES, MOCK_FRAME_MS, MOCK_HEIGHT, MOCK_SHOT_EVERY_FRAMES, MOCK_WIDTH, MockBridge } from "./mock";

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
  it("delivers all target faces on startup and restart", async () => {
    await bridge.frontendReady();
    expect(ofType("targetFaces")[0]?.faces).toHaveLength(6);
    await bridge.restart();
    await bridge.frontendReady();
    expect(ofType("targetFaces").at(-1)?.faces.map(face => face.key)).toContain("air_rifle_10m");
    await bridge.send({ type: "setSessionSettings", prefs: { ...MOCK_PREFERENCES, targetFace: "air_rifle_10m" } });
    expect(ofType("preferences").at(-1)?.rings[0]?.diameterMm).toBe(45.5);
  });
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
    expect(frame?.tracePointMm).toBeNull();
  });

  it("sends the state a page needs when it is ready", async () => {
    await bridge.frontendReady();
    expect(events.map((event) => event.type)).toEqual([
      "targetFaces",
      "preferences",
      "zeroOffset",
      "session",
      "shots",
      "deviceOptions",
      "trackingStatusText",
    ]);
  });

  it("records a shot every 10 seconds while a session runs", async () => {
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

it("retains global decimal scoring when preparing a new session", async () => {
  await bridge.send({ type: "setPreferences", prefs: { ...MOCK_PREFERENCES, decimalScoring: true } });
  expect(ofType("preferences").at(-1)?.prefs.decimalScoring).toBe(true);
  await bridge.send({ type: "newSession" });
  expect(ofType("preferences").at(-1)?.prefs.decimalScoring).toBe(true);
});


it("generates automatic shots only after a full recording interval", async () => {
  vi.advanceTimersByTime(MOCK_FRAME_MS * (MOCK_SHOT_EVERY_FRAMES * 2 + 17));
  expect(ofType("audioLevel").every(event => event.level === 0.02)).toBe(true);
  expect(ofType("shots")).toHaveLength(0);
  for (let session = 0; session < 2; session++) {
    await bridge.send({ type: "startSession", name: "", category: "practice" });
    vi.advanceTimersByTime(MOCK_FRAME_MS * (MOCK_SHOT_EVERY_FRAMES - 1));
    expect(ofType("shots").at(-1)?.shots).toHaveLength(0);
    vi.advanceTimersByTime(MOCK_FRAME_MS);
    expect(ofType("shots").at(-1)?.shots).toHaveLength(1);
    expect(ofType("audioLevel").at(-1)?.level).toBe(0.9);
    await bridge.send({ type: "stopSession" });
    const count = ofType("shots").length;
    const audioCount = ofType("audioLevel").length;
    vi.advanceTimersByTime(MOCK_FRAME_MS * MOCK_SHOT_EVERY_FRAMES * 2);
    expect(ofType("shots")).toHaveLength(count);
    expect(ofType("audioLevel").slice(audioCount).every(event => event.level === 0.02)).toBe(true);
  }
});


it("keeps the idle camera stationary and generates varied settled shots", async () => {
  vi.advanceTimersByTime(MOCK_FRAME_MS * 200);
  const idle = ofType("frame");
  expect(idle.every(frame => frame.tracePointMm === null)).toBe(true);
  expect(new Set(idle.map(frame => JSON.stringify(frame.aim))).size).toBe(1);
  await bridge.send({ type: "startSession", name: "", category: "practice" });
  vi.advanceTimersByTime(MOCK_FRAME_MS * MOCK_SHOT_EVERY_FRAMES * 4);
  const shots = ofType("shots").at(-1)!.shots;
  expect(shots).toHaveLength(4);
  expect(new Set(shots.map(shot => JSON.stringify([shot.xMm, shot.yMm]))).size).toBe(4);
  expect(shots.every(shot => Math.hypot(shot.xMm!, shot.yMm!) < 15 && shot.score !== null)).toBe(true);
  await bridge.send({ type: "stopSession" });
  const count = ofType("frame").length;
  vi.advanceTimersByTime(MOCK_FRAME_MS * 50);
  expect(ofType("frame").slice(count).every(frame => frame.tracePointMm === null)).toBe(true);
});

it("keeps hidden shot offsets across new sessions", async () => {
  await bridge.send({type: "setPreferences", prefs: {...MOCK_PREFERENCES, showShotOffsets: false}});
  await bridge.send({type: "newSession"});
  expect(ofType("preferences").at(-1)?.prefs.showShotOffsets).toBe(false);
});

it("marks release and shot positions in the overlaid shot traces", async () => {
  await bridge.send({type: "startSession", name: "", category: "practice"});
  vi.advanceTimersByTime(MOCK_FRAME_MS * (MOCK_SHOT_EVERY_FRAMES + 30));
  await bridge.send({type: "loadShotTraces"});
  const trace = ofType("shotTraces").at(-1)!.traces[0]!;
  expect(trace.points.length).toBeGreaterThan(50);
  expect(trace.releaseIndex).not.toBeNull();
  expect(trace.splitIndex).toBeGreaterThan(trace.releaseIndex!);
  expect(trace.splitIndex).toBeLessThan(trace.points.length - 1);
});

it("previews the full shot window before replay and preserves it after stopping", async () => {
  await bridge.send({type: "startSession", name: "", category: "practice"});
  vi.advanceTimersByTime(MOCK_FRAME_MS * (MOCK_SHOT_EVERY_FRAMES + 30));
  for (const stopped of [false, true]) {
    if (stopped) await bridge.send({type: "stopSession"});
    const before = ofType("playerIndex").length;
    await bridge.send({type: "selectShot", index: 0});
    const replay = ofType("replayLoaded").at(-1)!;
    expect(replay.enabled).toBe(true);
    expect(replay.points.length).toBeGreaterThan(50);
    expect(replay.splitIndex).toBeLessThan(replay.points.length - 1);
    expect(ofType("playerIndex")).toHaveLength(before);
    await bridge.send({type: "replayPlay"});
    expect(ofType("playerIndex").at(-1)?.index).toBe(0);
    vi.advanceTimersByTime(MOCK_FRAME_MS * 5);
    expect(ofType("playerIndex").at(-1)?.index).toBe(5);
    await bridge.send({type: "replayPause"});
    vi.advanceTimersByTime(MOCK_FRAME_MS * 5);
    expect(ofType("playerIndex").at(-1)?.index).toBe(5);
    await bridge.send({type: "replayReset"});
    expect(ofType("playerIndex").at(-1)?.index).toBe(0);
    await bridge.send({type: "replaySeek", fraction: 1});
    expect(ofType("playerIndex").at(-1)?.index).toBe(replay.points.length - 1);
  }
});

it("scores shots on the selected target face", async () => {
  await bridge.send({ type: "setSessionSettings", prefs: { ...MOCK_PREFERENCES, targetFace: "nsra_50m_prone_rifle_mm12c_199618" } });
  await bridge.send({ type: "startSession", name: "", category: "practice" });
  vi.advanceTimersByTime(MOCK_FRAME_MS * MOCK_SHOT_EVERY_FRAMES);
  expect(ofType("shots").at(-1)!.shots[0]!.score).toBe("X");
});

it("keeps ten consecutive preview shots in the X ring of the recorded face", async () => {
  await bridge.send({ type: "setSessionSettings", prefs: { ...MOCK_PREFERENCES, targetFace: "nsra_50m_prone_rifle_mm12c_199618" } });
  await bridge.send({ type: "startSession", name: "", category: "practice" });
  vi.advanceTimersByTime(MOCK_FRAME_MS * MOCK_SHOT_EVERY_FRAMES * 10);
  expect(ofType("shots").at(-1)!.shots.map(shot => shot.score)).toEqual(Array(10).fill("X"));
});

it("places every preview shot inside the 2.25 mm X ring", async () => {
  await bridge.send({ type: "startSession", name: "", category: "practice" });
  vi.advanceTimersByTime(MOCK_FRAME_MS * MOCK_SHOT_EVERY_FRAMES * 10);
  expect(ofType("shots").at(-1)!.shots.every(shot => Math.hypot(shot.xMm!, shot.yMm!) < 2.25)).toBe(true);
});

it("sends a hold trace with aiming figures when a shot is selected", async () => {
  await bridge.send({type: "startSession", name: "", category: "practice"});
  vi.advanceTimersByTime(MOCK_FRAME_MS * (MOCK_SHOT_EVERY_FRAMES + 30));
  await bridge.send({type: "selectShot", index: 0});
  const hold = ofType("holdTrace").at(-1)!.trace!;
  expect(hold.stats.samples).toBeGreaterThan(0);
  expect(hold.aim?.tenRingHoldPct).not.toBeNull();
  expect(hold.aim?.shotOffsetMm).not.toBeNull();
  expect(hold.aim?.meanCustomRingHoldPct).toBeNull();
});
