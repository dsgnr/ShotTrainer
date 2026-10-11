import { encodePacket } from "../frames/packet";
import type {
  ShellStatus,
  WireCommand,
  WireFace,
  WireEvent,
  WirePreferences,
  WireRing,
  WireReplay,
  WireSessionState,
  WireShot,
  WireShotStats,
} from "../wire/types";
import type { Bridge, EventHandler, PacketHandler, Unlisten } from "./bridge";

export const MOCK_WIDTH = 320;
export const MOCK_HEIGHT = 240;
export const MOCK_FRAME_MS = 16;
/** The fake microphone in `src-tauri/src/fake.rs` also hears a shot every 10 seconds. */
export const MOCK_SHOT_EVERY_FRAMES = Math.round(10000 / MOCK_FRAME_MS);
const MAX_IN_FLIGHT = 2;
const CIRCLE_RADIUS_PX = 8;
const CIRCLE_DIAMETER_MM = 60;
const MM_PER_PX = CIRCLE_DIAMETER_MM / (CIRCLE_RADIUS_PX * 2);

/** `Preferences::default()` in `crates/settings/src/preferences.rs`. */
export const MOCK_PREFERENCES: WirePreferences = {
  cameraId: 0,
  cameraRotation: 0,
  cameraFlipH: false,
  cameraFlipV: false,
  cameraBrightness: 0,
  cameraContrast: 1,
  audioDevice: "default",
  audioGain: 1,
  shotThreshold: 0.25,
  shotRefractoryMs: 400,
  preShotMs: 1500,
  postShotMs: 800,
  releaseWindowMs: 250,
  targetFace: "default",
  shotDiameterMm: 4.5,
  sessionPosition: "standing",
  shotsPerSeries: 10,
  trackingRegionFraction: 0.7,
  circleDiameterMm: CIRCLE_DIAMETER_MM,
  invertTraceHorizontal: false,
  invertTraceVertical: false,
  showHoldZone: true,
  decimalScoring: false,
  showShotOffsets: true,
};

/** The bundled `default.json` face. */
export const MOCK_RINGS: WireRing[] = [
  { diameterMm: 150, label: "1" },
  { diameterMm: 120, label: "3" },
  { diameterMm: 90, label: "5" },
  { diameterMm: 60, label: "7" },
  { diameterMm: 30, label: "9" },
  { diameterMm: 10, label: "X" },
];

interface FaceSource {
  label: string;
  rings: { diameter_mm: number; label: string }[];
  shot_diameter_mm?: number;
  face_diameter_mm?: number;
  scoring_direction?: string;
}
const sources = import.meta.glob<FaceSource>("../../../../crates/settings/assets/target_faces/*.json", { eager: true, import: "default" });
export const MOCK_FACES: WireFace[] = Object.entries(sources).sort(([a], [b]) => a.localeCompare(b)).map(([path, face]) => ({
  key: path.split("/").pop()!.replace(/\.json$/, ""), label: face.label,
  rings: face.rings.map(ring => ({ diameterMm: ring.diameter_mm, label: ring.label })),
  shotDiameterMm: face.shot_diameter_mm ?? null, faceDiameterMm: face.face_diameter_mm ?? null,
  scoringDirection: face.scoring_direction ?? "inward",
}));

import { simulatedAim, simulatedShot } from "./simulated-aim";

const UNAVAILABLE = "Not available in the browser preview";

function groupStats(shots: WireShot[]): WireShotStats {
  const points = shots.flatMap((shot) =>
    shot.xMm !== null && shot.yMm !== null ? [[shot.xMm, shot.yMm] as const] : [],
  );
  const count = points.length;
  const meanX = count === 0 ? 0 : points.reduce((sum, [x]) => sum + x, 0) / count;
  const meanY = count === 0 ? 0 : points.reduce((sum, [, y]) => sum + y, 0) / count;
  let spread = 0;
  for (const [ax, ay] of points) {
    for (const [bx, by] of points) {
      spread = Math.max(spread, Math.hypot(ax - bx, ay - by));
    }
  }
  const meanRadius =
    count === 0 ? 0 : points.reduce((sum, [x, y]) => sum + Math.hypot(x - meanX, y - meanY), 0) / count;
  return {
    count,
    meanXMm: meanX,
    meanYMm: meanY,
    extremeSpreadMm: spread,
    meanRadiusMm: meanRadius,
  };
}

/**
 * Imitates the shell with fake devices, so `npm run dev` works in a plain
 * browser. A dark circle drifts around the frame centre, its offset becomes
 * the live trace, and a shot lands every 10 seconds while recording.
 */
export class MockBridge implements Bridge {
  #handler: EventHandler | null = null;
  #onPacket: PacketHandler | null = null;
  #timer: ReturnType<typeof setInterval> | null = null;
  #inFlight = 0;
  #frameId = 0;
  #session: WireSessionState = { kind: "idle" };
  #summary = "No active session";
  #nextSessionId = 1;
  #shots: WireShot[] = [];
  #shotNumber = 0;
  #recordingFrames = 0;
  #prefs = { ...MOCK_PREFERENCES };
  #aimMm: [number, number] = [0, 0];
  #trace: {timestamp: number; point: [number, number]}[] = [];
  #replay: WireReplay | null = null;
  #playerIndex = 0;
  #playing = false;

  async listen(handler: EventHandler): Promise<Unlisten> {
    this.#handler = handler;
    return () => {
      if (this.#handler === handler) {
        this.#handler = null;
      }
    };
  }

  async subscribeFrames(onPacket: PacketHandler): Promise<void> {
    this.#onPacket = onPacket;
    this.#inFlight = 0;
    this.#timer ??= setInterval(() => this.#tick(), MOCK_FRAME_MS);
  }

  async frontendReady(): Promise<void> {
    this.#sendState();
  }

  async send(command: WireCommand): Promise<void> {
    switch (command.type) {
      case "listTargetFaces":
        this.#emit({ type: "targetFaces", faces: MOCK_FACES });
        break;
      case "setPreferences": {
        const current = this.#prefs;
        this.#prefs = { ...command.prefs,
          targetFace: current.targetFace, preShotMs: current.preShotMs, postShotMs: current.postShotMs,
          releaseWindowMs: current.releaseWindowMs, shotRefractoryMs: current.shotRefractoryMs,
          shotDiameterMm: current.shotDiameterMm, sessionPosition: current.sessionPosition,
          shotsPerSeries: current.shotsPerSeries,
        };
        this.#emit({ type: "preferences", prefs: this.#prefs, rings: this.#rings() });
        break;
      }
      case "setSessionSettings":
        if (this.#session.kind !== "idle" || this.#shots.length > 0) break;
        this.#prefs = { ...command.prefs };
        this.#emit({ type: "preferences", prefs: this.#prefs, rings: this.#rings() });
        break;
      case "newSession":
        if (this.#session.kind === "recording") break;
        this.#trace = [];
        this.#clearReplay();
        this.#prefs = { ...this.#prefs,
          targetFace: MOCK_PREFERENCES.targetFace, preShotMs: MOCK_PREFERENCES.preShotMs,
          postShotMs: MOCK_PREFERENCES.postShotMs, releaseWindowMs: MOCK_PREFERENCES.releaseWindowMs,
          shotRefractoryMs: MOCK_PREFERENCES.shotRefractoryMs, shotDiameterMm: MOCK_PREFERENCES.shotDiameterMm,
          sessionPosition: MOCK_PREFERENCES.sessionPosition, shotsPerSeries: MOCK_PREFERENCES.shotsPerSeries,
        };
        this.#emit({ type: "preferences", prefs: this.#prefs, rings: this.#rings() });
        this.#session = { kind: "idle" };
        this.#summary = "Ready to start a new session";
        this.#shots = [];
        this.#shotNumber = 0;
        this.#emit({ type: "replayCleared" });
        this.#emitSession();
        this.#emitShots();
        break;
      case "refresh":
        this.#sendState();
        break;
      case "startSession":
        if (this.#session.kind === "recording") break;
        this.#recordingFrames = 0;
        this.#trace = [];
        this.#clearReplay();
        this.#session = { kind: "recording", sessionId: this.#nextSessionId };
        this.#summary = `Recording session ${this.#nextSessionId}`;
        this.#nextSessionId += 1;
        this.#shotNumber = 0;
        this.#shots = [];
        this.#emitSession();
        this.#emitShots();
        break;
      case "stopSession":
        if (this.#session.kind === "recording") {
          this.#summary = `Saved session ${this.#session.sessionId}`;
          this.#session = { kind: "idle" };
          this.#emitSession();
        }
        break;
      case "clearShots":
        this.#shots = [];
        this.#emitShots();
        break;
      case "selectShot":
        if (command.index < this.#shots.length) {
          this.#emit({ type: "selectedShot", index: command.index });
          this.#loadReplay(command.index);
        }
        break;
      case "loadShotTraces":
        this.#emit({ type: "shotTraces", traces: this.#shots.map(shot => ({
          points: this.#trace
            .filter(s => shot.timestamp !== null && Math.abs(s.timestamp - shot.timestamp) <= this.#prefs.preShotMs / 1000)
            .map(s => s.point),
          releaseIndex: null,
          splitIndex: null,
        })) });
        break;
      case "replayPlay":
        if (this.#replay?.enabled) {
          if (this.#playerIndex >= this.#replay.points.length - 1) this.#playerIndex = 0;
          this.#playing = true;
          this.#emitPlayhead();
          this.#emit({type: "replayPlaying", playing: true});
        }
        break;
      case "replayPause":
        this.#playing = false;
        this.#emit({type: "replayPlaying", playing: false});
        break;
      case "replayReset":
        this.#playing = false;
        this.#playerIndex = 0;
        this.#emitPlayhead();
        this.#emit({type: "replayPlaying", playing: false});
        break;
      case "replaySeek":
        if (this.#replay?.enabled) {
          this.#playerIndex = Math.round(Math.max(0, Math.min(1, command.fraction)) * (this.#replay.points.length - 1));
          this.#emitPlayhead();
        }
        break;
      default:
        this.#emit({
          type: "message",
          message: { text: UNAVAILABLE, severity: "info", durationMs: 3000 },
        });
    }
  }

  frameDrawn(): void {
    this.#inFlight = Math.max(0, this.#inFlight - 1);
  }

  async status(): Promise<ShellStatus> {
    return { running: true, error: null, fakeDevices: true, denied: [], awaitingAccess: false };
  }

  async restart(): Promise<void> {
    this.#inFlight = 0;
  }

  /** Stops the frame timer. */
  close(): void {
    if (this.#timer !== null) {
      clearInterval(this.#timer);
      this.#timer = null;
    }
  }

  #emit(event: WireEvent): void {
    this.#handler?.(event);
  }

  #emitSession(): void {
    this.#emit({ type: "session", state: this.#session, summary: this.#summary });
  }

  #emitShots(): void {
    this.#emit({ type: "shots", shots: this.#shots, group: groupStats(this.#shots), totalScore: 0 });
  }

  #sendState(): void {
    this.#emit({ type: "targetFaces", faces: MOCK_FACES });
    this.#emit({ type: "preferences", prefs: this.#prefs, rings: this.#rings() });
    this.#emit({ type: "zeroOffset", active: false, offsetMm: [0, 0] });
    this.#emitSession();
    this.#emitShots();
    this.#emit({
      type: "deviceOptions",
      cameras: [{ index: 0, name: "Simulated camera" }],
      microphones: ["Simulated microphone"],
      savedCamera: "Simulated camera",
    });
    this.#emit({
      type: "trackingStatusText",
      text: `Tracking ${CIRCLE_DIAMETER_MM} mm circle - ${MM_PER_PX.toFixed(3)} mm/px`,
    });
  }

  #tick(): void {
    this.#frameId += 1;
    const t = (this.#frameId * MOCK_FRAME_MS) / 1000;
    const recording = this.#session.kind === "recording";
    this.#aimMm = recording ? simulatedAim(this.#recordingFrames / MOCK_SHOT_EVERY_FRAMES * 10) : [0, 0];
    if (recording) this.#trace.push({timestamp: t, point: [...this.#aimMm]});
    const x = MOCK_WIDTH / 2 + this.#aimMm[0] / MM_PER_PX;
    const y = MOCK_HEIGHT / 2 + this.#aimMm[1] / MM_PER_PX;
    this.#emit({
      type: "frame",
      frameId: this.#frameId,
      timestamp: t,
      width: MOCK_WIDTH,
      height: MOCK_HEIGHT,
      status: "tracking",
      aim: { xPx: x, yPx: y, radiusPx: CIRCLE_RADIUS_PX },
      rejected: null,
      zeroPx: null,
      tracePointMm: recording ? this.#aimMm : null,
    });
    const shot = this.#session.kind === "recording"
      && ++this.#recordingFrames % MOCK_SHOT_EVERY_FRAMES === 0;
    this.#emit({ type: "audioLevel", level: shot ? 0.9 : 0.02 });
    if (shot && this.#session.kind === "recording") {
      const [shotX, shotY] = simulatedShot(this.#shotNumber);
      this.#shots = [
        ...this.#shots,
        { timestamp: t, xMm: shotX, yMm: shotY, score: this.#score(shotX, shotY), shotId: null,
          seriesIndex: Math.floor(this.#shotNumber++ / this.#prefs.shotsPerSeries) },
      ];
      this.#emitShots();
    }
    if (this.#playing && this.#replay !== null) {
      this.#playerIndex = Math.min(this.#replay.points.length - 1, this.#playerIndex + 1);
      this.#emitPlayhead();
      if (this.#playerIndex === this.#replay.points.length - 1) {
        this.#playing = false;
        this.#emit({type: "playerFinished"});
        this.#emit({type: "replayPlaying", playing: false});
      }
    }
    if (this.#onPacket !== null && this.#inFlight < MAX_IN_FLIGHT) {
      this.#inFlight += 1;
      this.#onPacket(this.#pixels(x, y, t));
    }
  }

  #clearReplay(): void {
    this.#replay = null;
    this.#playing = false;
    this.#playerIndex = 0;
    this.#emit({type: "replayCleared"});
  }

  #loadReplay(index: number): void {
    const timestamp = this.#shots[index]!.timestamp;
    if (timestamp === null) { this.#clearReplay(); return; }
    const samples = this.#trace.filter(sample => sample.timestamp >= timestamp - this.#prefs.preShotMs / 1000
      && sample.timestamp <= timestamp + this.#prefs.postShotMs / 1000);
    const split = samples.reduce((best, sample, i) => Math.abs(sample.timestamp - timestamp) < Math.abs(samples[best]!.timestamp - timestamp) ? i : best, 0);
    const release = samples.findIndex(sample => sample.timestamp >= timestamp - this.#prefs.releaseWindowMs / 1000 && sample.timestamp <= timestamp);
    this.#replay = {index, points: samples.map(sample => sample.point), splitIndex: samples.length ? split : null,
      releaseIndex: release < 0 ? null : release, enabled: samples.length > 0,
      durationMs: samples.length ? Math.round((samples.at(-1)!.timestamp - samples[0]!.timestamp) * 1000) : null,
      holdZone: null};
    this.#playing = false;
    this.#playerIndex = 0;
    this.#emit({type: "replayPlaying", playing: false});
    this.#emit({type: "replayLoaded", ...this.#replay});
    this.#emit({type: "playerProgress", fraction: 0});
  }

  #emitPlayhead(): void {
    const replay = this.#replay;
    if (replay === null || !replay.enabled) return;
    this.#emit({type: "playerIndex", index: this.#playerIndex});
    this.#emit({type: "playerProgress", fraction: this.#playerIndex / Math.max(1, replay.points.length - 1)});
  }

  #rings(): WireRing[] {
    return MOCK_FACES.find(face => face.key === this.#prefs.targetFace)?.rings ?? MOCK_RINGS;
  }

  #score(x: number, y: number): string {
    const distance = Math.hypot(x, y);
    const rings = this.#rings().filter((ring): ring is WireRing & { diameterMm: number } => ring.diameterMm !== null).sort((a, b) => a.diameterMm - b.diameterMm);
    if (!this.#prefs.decimalScoring) {
      return rings.find(r => distance <= r.diameterMm / 2 + this.#prefs.shotDiameterMm / 2)?.label ?? "";
    }
    const hasTen = rings.some(r => r.label === "10");
    const numeric = rings.map(r => ({radius: r.diameterMm / 2 + this.#prefs.shotDiameterMm / 2,
      value: r.label === "X" && !hasTen ? 10 : Number(r.label)})).filter(r => Number.isFinite(r.value) && r.value > 0);
    let innerRadius = 0;
    let innerValue = (numeric[0]?.value ?? 0) + 1;
    for (const ring of numeric) {
      if (distance <= ring.radius) {
        const value = ring.value + (ring.radius - distance) / (ring.radius - innerRadius) * (innerValue - ring.value);
        return Math.min((numeric[0]?.value ?? 0) + 0.9, Math.floor(value * 10) / 10).toFixed(1);
      }
      innerRadius = ring.radius;
      innerValue = ring.value;
    }
    return "";
  }

  #pixels(x: number, y: number, t: number): ArrayBuffer {
    const pixels = new Uint8ClampedArray(MOCK_WIDTH * MOCK_HEIGHT * 4);
    const r2 = CIRCLE_RADIUS_PX * CIRCLE_RADIUS_PX;
    for (let row = 0; row < MOCK_HEIGHT; row += 1) {
      for (let column = 0; column < MOCK_WIDTH; column += 1) {
        const inside = (column - x) ** 2 + (row - y) ** 2 <= r2;
        const grey = inside ? 30 : 190;
        const at = (row * MOCK_WIDTH + column) * 4;
        pixels[at] = grey;
        pixels[at + 1] = grey;
        pixels[at + 2] = grey;
        pixels[at + 3] = 255;
      }
    }
    return encodePacket(
      { width: MOCK_WIDTH, height: MOCK_HEIGHT, frameId: this.#frameId, timestamp: t, sentAtMs: Date.now() },
      pixels,
    );
  }
}
