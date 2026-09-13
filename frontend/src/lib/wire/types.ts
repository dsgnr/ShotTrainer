// The JSON the shell exchanges with the page. Each type mirrors a struct or
// enum in `src-tauri/src/wire/` or `ShellStatus` in `src-tauri/src/bridge.rs`,
// and a change there must be repeated here.

/** A Rust `f64`. serde writes a number that is not finite as `null`. */
export type F64 = number | null;

/** A Rust `(f64, f64)`, such as a position in millimetres. */
export type Pair = [F64, F64];

export type Severity = "info" | "warning" | "success";

export interface WireMessage {
  text: string;
  severity: Severity;
  /** How long the status line shows the text. Zero keeps it until replaced. */
  durationMs: number;
}

export interface WireMarker {
  xPx: F64;
  yPx: F64;
  radiusPx: F64;
}

export type TrackingStatus = "idle" | "tracking" | "lost" | "rejected";

export interface WireFrame {
  frameId: number;
  timestamp: F64;
  width: number;
  height: number;
  status: TrackingStatus;
  aim: WireMarker | null;
  /** A circle found outside the tracking region. */
  rejected: WireMarker | null;
  zeroPx: Pair | null;
  /** Absent while a saved session is on display. */
  tracePointMm: Pair | null;
}

export interface WireRing {
  diameterMm: F64;
  label: string | null;
}

export interface WireFace {
  key: string;
  label: string;
  rings: WireRing[];
  shotDiameterMm: F64;
  faceDiameterMm: F64;
  scoringDirection: string;
}

export interface WireCamera {
  index: number;
  name: string;
}

export type WireSessionState =
  | { kind: "idle" }
  | { kind: "recording"; sessionId: number }
  | { kind: "reviewing"; sessionId: number };

export interface WireShot {
  timestamp: F64;
  xMm: F64;
  yMm: F64;
  score: string | null;
  shotId: number | null;
}

export interface WireShotStats {
  count: number;
  meanXMm: F64;
  meanYMm: F64;
  extremeSpreadMm: F64;
  meanRadiusMm: F64;
}

export interface WireTraceStats {
  samples: number;
  holdTremorMm: F64;
  traceLengthMm: F64;
  meanXMm: F64;
  meanYMm: F64;
}

export interface WireHoldTrace {
  points: Pair[];
  stats: WireTraceStats;
}

export interface WireHoldZone {
  centreMm: Pair;
  radiusMm: F64;
}

export interface WireReplay {
  /** The selected shot's position in the shot list. */
  index: number;
  points: Pair[];
  releaseIndex: number | null;
  /** The sample nearest the shot. */
  splitIndex: number | null;
  durationMs: number | null;
  holdZone: WireHoldZone | null;
  /** False when the window holds no samples. */
  enabled: boolean;
}

export interface WireSessionSummary {
  id: number;
  name: string;
  /** ISO 8601 local time without a zone, as stored in `sessions.db`. */
  startedAt: string;
  endedAt: string | null;
  shotCount: number;
  totalScore: F64;
  category: string;
}

/**
 * The controller validates preferences, so their numbers are always finite
 * and the page can send them back unchanged in `setPreferences`.
 */
export interface WirePreferences {
  cameraId: number | null;
  cameraRotation: number;
  cameraFlipH: boolean;
  cameraFlipV: boolean;
  cameraBrightness: number;
  cameraContrast: number;
  audioDevice: string;
  audioGain: number;
  shotThreshold: number;
  shotRefractoryMs: number;
  preShotMs: number;
  postShotMs: number;
  releaseWindowMs: number;
  targetFace: string;
  shotDiameterMm: number;
  trackingRegionFraction: number;
  circleDiameterMm: number;
  invertTraceHorizontal: boolean;
  invertTraceVertical: boolean;
  showHoldZone: boolean;
}

/** Every controller event, emitted as the Tauri event `ui-event`. */
export type WireEvent =
  | ({ type: "frame" } & WireFrame)
  | { type: "cameraIdle" }
  | { type: "audioLevel"; level: F64 }
  | { type: "trackingStatusText"; text: string }
  | { type: "preferences"; prefs: WirePreferences; rings: WireRing[] }
  | { type: "zeroOffset"; active: boolean; offsetMm: Pair }
  | { type: "clearLiveTrace" }
  | {
      type: "deviceOptions";
      cameras: WireCamera[];
      microphones: string[];
      savedCamera: string;
    }
  | { type: "targetFaces"; faces: WireFace[] }
  | { type: "detectorStatus"; message: WireMessage }
  | { type: "imageControls"; brightness: F64; contrast: F64 }
  | { type: "optimiseEnabled"; enabled: boolean }
  | { type: "message"; message: WireMessage }
  | { type: "controllerFailed"; reason: string }
  | { type: "session"; state: WireSessionState; summary: string }
  | {
      type: "shots";
      shots: WireShot[];
      group: WireShotStats;
      totalScore: F64;
    }
  | { type: "holdTrace"; trace: WireHoldTrace | null }
  | { type: "replayCleared" }
  | { type: "playerPoint"; xMm: F64; yMm: F64 }
  | { type: "playerIndex"; index: number }
  | { type: "playerProgress"; fraction: F64 }
  | { type: "playerFinished" }
  | { type: "selectedShot"; index: number }
  | ({ type: "replayLoaded" } & WireReplay)
  | { type: "replayPlaying"; playing: boolean }
  | { type: "sessions"; sessions: WireSessionSummary[] };

export type WireEventType = WireEvent["type"];

export type EventOf<T extends WireEventType> = Extract<WireEvent, { type: T }>;

export type WireImageControl = "brightness" | "contrast";

/**
 * Every command `send_command` accepts. The shell refuses unknown fields,
 * negative indices and a missing field.
 */
export type WireCommand =
  | { type: "startSession"; name: string; category: string }
  | { type: "stopSession" }
  | { type: "clearShots" }
  | { type: "deleteShot"; index: number }
  | { type: "rescore" }
  | { type: "selectShot"; index: number }
  | { type: "listSessions" }
  | { type: "openSession"; id: number }
  | { type: "renameSession"; id: number; name: string }
  | { type: "setSessionCategory"; id: number; category: string }
  | { type: "deleteSession"; id: number }
  | { type: "exportSession"; id: number; dir: string }
  | { type: "replayPlay" }
  | { type: "replayPause" }
  | { type: "replayReset" }
  | { type: "replaySeek"; fraction: number }
  | { type: "setPreferences"; prefs: WirePreferences }
  | { type: "setCircleDiameter"; diameterMm: number }
  | { type: "zeroOnAim" }
  | { type: "clearZero" }
  | { type: "refresh" }
  | { type: "listDevices"; refresh: boolean }
  | { type: "listTargetFaces" }
  | { type: "beginPreview"; cameraId: number | null }
  | { type: "previewCamera"; cameraId: number | null }
  | { type: "previewImage"; control: WireImageControl; value: number }
  | {
      type: "previewTransform";
      rotationDegrees: number;
      flipHorizontal: boolean;
      flipVertical: boolean;
    }
  | { type: "endPreview"; saved: boolean }
  | { type: "optimise" }
  | { type: "resetDetector" };

/** What `controller_status` returns. */
export interface ShellStatus {
  running: boolean;
  /** Why the controller could not be created, such as a database that cannot be opened. */
  error: string | null;
  fakeDevices: boolean;
  /** `camera` or `microphone` for each access the user refused. */
  denied: string[];
  /** True until the system access prompts are answered and the devices may open. */
  awaitingAccess: boolean;
}
