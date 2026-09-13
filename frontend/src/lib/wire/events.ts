import type { WireEvent, WireEventType } from "./types";

// A `Record` over the union makes `npm run check` fail when a tag is missing
// or misspelt.
const KNOWN: Record<WireEventType, true> = {
  frame: true,
  cameraIdle: true,
  audioLevel: true,
  trackingStatusText: true,
  preferences: true,
  zeroOffset: true,
  clearLiveTrace: true,
  deviceOptions: true,
  targetFaces: true,
  detectorStatus: true,
  imageControls: true,
  optimiseEnabled: true,
  message: true,
  controllerFailed: true,
  session: true,
  shots: true,
  holdTrace: true,
  replayCleared: true,
  playerPoint: true,
  playerIndex: true,
  playerProgress: true,
  playerFinished: true,
  selectedShot: true,
  replayLoaded: true,
  replayPlaying: true,
  sessions: true,
};

export const EVENT_TYPES: readonly WireEventType[] = Object.keys(KNOWN) as WireEventType[];

/**
 * The payload as a `WireEvent`, or `null` when it is not an object tagged
 * with a known `type`. Fields are trusted, because the shell serialises them
 * from Rust types.
 */
export function parseEvent(payload: unknown): WireEvent | null {
  if (typeof payload !== "object" || payload === null) {
    return null;
  }
  const type: unknown = (payload as { type?: unknown }).type;
  return typeof type === "string" && Object.hasOwn(KNOWN, type) ? (payload as WireEvent) : null;
}
