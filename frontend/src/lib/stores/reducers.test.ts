import { describe, expect, it } from "vitest";

import { SAMPLE_EVENTS } from "../wire/samples";
import type { WireEvent, WireEventType } from "../wire/types";
import { initialCamera, reduceCamera } from "./camera";
import { initialDevices, reduceDevices } from "./devices";
import { initialPreferences, reducePreferences } from "./preferences";
import { initialReplay, reduceReplay } from "./replay";
import { initialSession, reduceSession } from "./session";
import { initialShots, reduceShots } from "./shots";
import { activeMessage, initialStatus, reduceStatus } from "./status";

const reducers: [string, unknown, (state: never, event: WireEvent) => unknown, WireEventType[]][] = [
  ["session", initialSession, reduceSession, ["session", "sessions"]],
  ["shots", initialShots, reduceShots, ["shots", "selectedShot", "holdTrace"]],
  [
    "preferences",
    initialPreferences,
    reducePreferences,
    ["preferences", "targetFaces", "zeroOffset", "detectorStatus", "imageControls", "optimiseEnabled"],
  ],
  [
    "replay",
    initialReplay,
    reduceReplay,
    ["replayLoaded", "replayCleared", "playerIndex", "playerProgress", "replayPlaying", "playerFinished"],
  ],
  ["devices", initialDevices, reduceDevices, ["deviceOptions"]],
  ["camera", initialCamera, reduceCamera, ["frame", "cameraIdle"]],
  [
    "status",
    initialStatus,
    (state, event) => reduceStatus(state, event, 0),
    ["message", "controllerFailed", "trackingStatusText", "audioLevel"],
  ],
];

describe("reducers", () => {
  it.each(reducers)("%s keeps its state for events it does not handle", (_name, initial, reduce, handled) => {
    for (const event of Object.values(SAMPLE_EVENTS)) {
      if (!handled.includes(event.type)) {
        expect(reduce(initial as never, event), event.type).toBe(initial);
      }
    }
  });
});

describe("reduceSession", () => {
  it("keeps the state, summary and session list", () => {
    let state = reduceSession(initialSession, SAMPLE_EVENTS.session);
    state = reduceSession(state, SAMPLE_EVENTS.sessions);
    expect(state.state).toEqual({ kind: "recording", sessionId: 4 });
    expect(state.summary).toBe("S");
    expect(state.sessions.map((session) => session.id)).toEqual([1]);
  });
});

describe("reduceShots", () => {
  it("keeps the list, group, selection and hold figures", () => {
    let state = reduceShots(initialShots, SAMPLE_EVENTS.shots);
    state = reduceShots(state, SAMPLE_EVENTS.selectedShot);
    state = reduceShots(state, SAMPLE_EVENTS.holdTrace);
    expect(state.shots).toHaveLength(1);
    expect(state.group?.extremeSpreadMm).toBe(3);
    expect(state.totalScore).toBe(10);
    expect(state.selected).toBe(5);
    expect(state.holdTrace?.stats.holdTremorMm).toBe(0.1);
    expect(reduceShots(state, { type: "holdTrace", trace: null }).holdTrace).toBeNull();
  });
});

describe("reducePreferences", () => {
  it("keeps preferences, rings, faces, zero and the dialog state", () => {
    let state = initialPreferences;
    for (const type of [
      "preferences",
      "targetFaces",
      "zeroOffset",
      "detectorStatus",
      "imageControls",
      "optimiseEnabled",
    ] as const) {
      state = reducePreferences(state, SAMPLE_EVENTS[type]);
    }
    expect(state.prefs?.targetFace).toBe("air_rifle_10m");
    expect(state.rings).toEqual([{ diameterMm: 30.5, label: null }]);
    expect(state.faces.map((face) => face.key)).toEqual(["k"]);
    expect(state.zero).toEqual({ active: true, offsetMm: [1.5, -2.0] });
    expect(state.detectorStatus?.text).toBe("Lost");
    expect(state.imageControls).toEqual({ brightness: 12, contrast: 1.5 });
    expect(state.optimiseEnabled).toBe(true);
  });
});

describe("reduceReplay", () => {
  it("loads a window without its tag and with the cursor unset", () => {
    const state = reduceReplay({ ...initialReplay, playhead: 9, playing: true }, SAMPLE_EVENTS.replayLoaded);
    expect(state.loaded).toEqual({
      index: 2,
      points: [[0, 1]],
      releaseIndex: 3,
      splitIndex: 4,
      durationMs: 1500,
      holdZone: { centreMm: [0.5, -0.5], radiusMm: 1.5 },
      enabled: true,
    });
    expect(state.playhead).toBeNull();
    expect(state.playing).toBe(false);
  });

  it("follows the player and stops when it finishes", () => {
    let state = reduceReplay(initialReplay, SAMPLE_EVENTS.replayLoaded);
    state = reduceReplay(state, SAMPLE_EVENTS.playerIndex);
    state = reduceReplay(state, SAMPLE_EVENTS.playerProgress);
    state = reduceReplay(state, SAMPLE_EVENTS.replayPlaying);
    expect([state.playhead, state.progress, state.playing]).toEqual([3, 0.5, true]);
    state = reduceReplay(state, { type: "playerProgress", fraction: null });
    expect(state.progress).toBe(0);
    expect(reduceReplay(state, SAMPLE_EVENTS.playerFinished).playing).toBe(false);
    expect(reduceReplay(state, SAMPLE_EVENTS.replayCleared)).toBe(initialReplay);
  });
});

describe("reduceDevices", () => {
  it("keeps the cameras, microphones and saved camera", () => {
    expect(reduceDevices(initialDevices, SAMPLE_EVENTS.deviceOptions)).toEqual({
      cameras: [
        { index: 0, name: "Built-in" },
        { index: 3, name: "USB" },
      ],
      microphones: ["default"],
      savedCamera: "USB",
    });
  });
});

describe("reduceCamera", () => {
  it("keeps the latest frame until the camera stops", () => {
    const state = reduceCamera(initialCamera, SAMPLE_EVENTS.frame);
    expect(state.frame?.frameId).toBe(12);
    expect(state.idle).toBe(false);
    const idle = reduceCamera(state, SAMPLE_EVENTS.cameraIdle);
    expect(idle).toEqual({ frame: null, idle: true });
    expect(reduceCamera(idle, SAMPLE_EVENTS.cameraIdle)).toBe(idle);
    expect(reduceCamera(idle, SAMPLE_EVENTS.frame).idle).toBe(false);
  });
});

describe("reduceStatus", () => {
  it("keeps the failure, the header line and the level", () => {
    let state = reduceStatus(initialStatus, SAMPLE_EVENTS.controllerFailed, 0);
    state = reduceStatus(state, SAMPLE_EVENTS.trackingStatusText, 0);
    state = reduceStatus(state, SAMPLE_EVENTS.audioLevel, 0);
    expect([state.failure, state.trackingText, state.audioLevel]).toEqual(["boom", "Tracking", 0.5]);
    expect(reduceStatus(state, { type: "audioLevel", level: null }, 0).audioLevel).toBe(0);
  });

  it("shows a message for its duration", () => {
    const state = reduceStatus(initialStatus, SAMPLE_EVENTS.message, 5000);
    expect(activeMessage(state, 5999)?.text).toBe("a");
    expect(activeMessage(state, 6000)).toBeNull();
  });

  it("keeps a message with no duration until another replaces it", () => {
    const state = reduceStatus(initialStatus, SAMPLE_EVENTS.detectorStatus, 0);
    expect(activeMessage(state, 0)).toBeNull();
    const lasting = reduceStatus(
      initialStatus,
      { type: "message", message: { text: "Saved", severity: "success", durationMs: 0 } },
      0,
    );
    expect(activeMessage(lasting, 1e9)?.text).toBe("Saved");
  });
});
