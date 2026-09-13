import { finiteOr } from "../wire/numbers";
import type { ShellStatus, WireEvent, WireMessage } from "../wire/types";

export interface StatusState {
  /** The latest `controller_status`, or `null` before the first answer. */
  shell: ShellStatus | null;
  /** The reason from `controllerFailed`, cleared by a successful restart. */
  failure: string | null;
  /** Why the page could not register its listener or ask for the status. */
  connectionError: string | null;
  /** The latest transient message and when it arrived, in `Date.now()` milliseconds. */
  message: WireMessage | null;
  messageAt: number;
  /** The header line, such as `Tracking 60 mm circle - 0.125 mm/px`. */
  trackingText: string;
  /** The microphone level multiplied by the gain. */
  audioLevel: number;
}

export const initialStatus: StatusState = {
  shell: null,
  failure: null,
  connectionError: null,
  message: null,
  messageAt: 0,
  trackingText: "Acquiring target...",
  audioLevel: 0,
};

export function reduceStatus(state: StatusState, event: WireEvent, now: number): StatusState {
  switch (event.type) {
    case "message":
      return { ...state, message: event.message, messageAt: now };
    case "controllerFailed":
      return { ...state, failure: event.reason };
    case "trackingStatusText":
      return { ...state, trackingText: event.text };
    case "audioLevel":
      return { ...state, audioLevel: finiteOr(event.level, 0) };
    default:
      return state;
  }
}

/** The message while its `durationMs` lasts. A duration of zero lasts until replaced. */
export function activeMessage(state: StatusState, now: number): WireMessage | null {
  const message = state.message;
  if (message === null) {
    return null;
  }
  return message.durationMs === 0 || now < state.messageAt + message.durationMs ? message : null;
}
