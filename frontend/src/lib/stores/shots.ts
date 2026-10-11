import type { F64, WireEvent, WireHoldTrace, WireShot, WireShotStats, WireShotTrace } from "../wire/types";

export interface ShotsState {
  shots: WireShot[];
  /** From the shots with both coordinates. `null` before the first `shots` event. */
  group: WireShotStats | null;
  totalScore: F64;
  /** The highlighted shot's position in `shots`. */
  selected: number | null;
  /** The hold figures for the selected or latest shot. */
  holdTrace: WireHoldTrace | null;
  /** Each shot's trace window, in shot order. Filled on request for the overlay. */
  traces: WireShotTrace[];
}

export const initialShots: ShotsState = {
  shots: [],
  group: null,
  totalScore: 0,
  selected: null,
  holdTrace: null,
  traces: [],
};

export function reduceShots(state: ShotsState, event: WireEvent): ShotsState {
  switch (event.type) {
    case "shots":
      return { ...state, shots: event.shots, group: event.group, totalScore: event.totalScore,
        selected: event.shots.length > state.shots.length ? null : state.selected };
    case "selectedShot":
      return { ...state, selected: event.index };
    case "holdTrace":
      return { ...state, holdTrace: event.trace };
    case "shotTraces":
      return { ...state, traces: event.traces };
    default:
      return state;
  }
}
