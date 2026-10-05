import { finiteOr } from "../wire/numbers";
import type { WireEvent, WireReplay } from "../wire/types";

export interface ReplayState {
  /** The loaded shot window, or `null` when the replay controls are disabled. */
  loaded: WireReplay | null;
  /** The trace sample under the replay cursor. */
  playhead: number | null;
  /** From 0 to 1 through the loaded window. */
  progress: number;
  playing: boolean;
}

export const initialReplay: ReplayState = {
  loaded: null,
  playhead: null,
  progress: 0,
  playing: false,
};

export function reduceReplay(state: ReplayState, event: WireEvent): ReplayState {
  switch (event.type) {
    case "replayLoaded": {
      const { type: _type, ...loaded } = event;
      return { loaded, playhead: null, progress: 0, playing: false };
    }
    case "replayCleared":
      return initialReplay;
    case "playerIndex":
      return { ...state, playhead: event.index };
    case "playerProgress":
      return { ...state, progress: finiteOr(event.fraction, 0) };
    case "replayPlaying":
      return { ...state, playing: event.playing };
    case "playerFinished":
      return { ...state, playing: false };
    default:
      return state;
  }
}
