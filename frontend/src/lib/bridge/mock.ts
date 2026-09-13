import { encodePacket } from "../frames/packet";
import type {
  ShellStatus,
  WireCommand,
  WireEvent,
  WirePreferences,
  WireRing,
  WireSessionState,
  WireShot,
  WireShotStats,
} from "../wire/types";
import type { Bridge, EventHandler, PacketHandler, Unlisten } from "./bridge";

export const MOCK_WIDTH = 320;
export const MOCK_HEIGHT = 240;
export const MOCK_FRAME_MS = 33;
/** The fake microphone in `src-tauri/src/fake.rs` also hears a shot every 5 seconds. */
export const MOCK_SHOT_EVERY_FRAMES = 150;
const MAX_IN_FLIGHT = 2;
const CIRCLE_RADIUS_PX = 24;
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
  trackingRegionFraction: 0.7,
  circleDiameterMm: CIRCLE_DIAMETER_MM,
  invertTraceHorizontal: false,
  invertTraceVertical: false,
  showHoldZone: true,
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
 * the live trace, and a shot lands every 5 seconds while recording.
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
  #aimMm: [number, number] = [0, 0];

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
      case "refresh":
        this.#sendState();
        break;
      case "startSession":
        this.#session = { kind: "recording", sessionId: this.#nextSessionId };
        this.#summary = `Recording session ${this.#nextSessionId}`;
        this.#nextSessionId += 1;
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
    this.#emit({ type: "preferences", prefs: MOCK_PREFERENCES, rings: MOCK_RINGS });
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
    const dx = 18 * Math.sin(t * 0.9) + 4 * Math.sin(t * 3.1);
    const dy = 12 * Math.cos(t * 0.7) + 3 * Math.sin(t * 2.3);
    const x = MOCK_WIDTH / 2 + dx;
    const y = MOCK_HEIGHT / 2 + dy;
    this.#aimMm = [dx * MM_PER_PX, dy * MM_PER_PX];
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
      tracePointMm: this.#aimMm,
    });
    const shot = this.#frameId % MOCK_SHOT_EVERY_FRAMES === 0;
    this.#emit({ type: "audioLevel", level: shot ? 0.9 : 0.02 });
    if (shot && this.#session.kind === "recording") {
      this.#shots = [
        ...this.#shots,
        { timestamp: t, xMm: this.#aimMm[0], yMm: this.#aimMm[1], score: null, shotId: null },
      ];
      this.#emitShots();
    }
    if (this.#onPacket !== null && this.#inFlight < MAX_IN_FLIGHT) {
      this.#inFlight += 1;
      this.#onPacket(this.#pixels(x, y, t));
    }
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
