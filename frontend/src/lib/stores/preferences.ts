import type {
  F64,
  Pair,
  WireEvent,
  WireFace,
  WireMessage,
  WirePreferences,
  WireRing,
} from "../wire/types";

export interface PreferencesState {
  /** `null` until the controller sends them. */
  prefs: WirePreferences | null;
  /** The rings of the active target face. */
  rings: WireRing[];
  faces: WireFace[];
  zero: { active: boolean; offsetMm: Pair };
  /** The detector line of the open Preferences dialog. */
  detectorStatus: WireMessage | null;
  /** The dialog's sliders after auto-optimise. */
  imageControls: { brightness: F64; contrast: F64 } | null;
  optimiseEnabled: boolean;
}

export const initialPreferences: PreferencesState = {
  prefs: null,
  rings: [],
  faces: [],
  zero: { active: false, offsetMm: [0, 0] },
  detectorStatus: null,
  imageControls: null,
  optimiseEnabled: false,
};

export function reducePreferences(state: PreferencesState, event: WireEvent): PreferencesState {
  switch (event.type) {
    case "preferences":
      return { ...state, prefs: event.prefs, rings: event.rings };
    case "targetFaces":
      return { ...state, faces: event.faces };
    case "zeroOffset":
      return { ...state, zero: { active: event.active, offsetMm: event.offsetMm } };
    case "detectorStatus":
      return { ...state, detectorStatus: event.message };
    case "imageControls":
      return { ...state, imageControls: { brightness: event.brightness, contrast: event.contrast } };
    case "optimiseEnabled":
      return { ...state, optimiseEnabled: event.enabled };
    default:
      return state;
  }
}
