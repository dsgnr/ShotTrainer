import type { WireEvent, WireSessionState, WireSessionSummary } from "../wire/types";

export interface SessionState {
  state: WireSessionState;
  /** The line under the session controls, such as `Recording session 4`. */
  summary: string;
  /** The session browser list, newest first. */
  sessions: WireSessionSummary[];
}

export const initialSession: SessionState = {
  state: { kind: "idle" },
  summary: "",
  sessions: [],
};

export function reduceSession(state: SessionState, event: WireEvent): SessionState {
  switch (event.type) {
    case "session":
      return { ...state, state: event.state, summary: event.summary };
    case "sessions":
      return { ...state, sessions: event.sessions };
    default:
      return state;
  }
}
