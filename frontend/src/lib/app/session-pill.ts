import type { WireSessionState } from "../wire/types";

export type PillTone = "idle" | "recording" | "replay";

export interface SessionPill {
  label: string;
  tone: PillTone;
}

/** The header pill label and tone for a session state. */
export function sessionPill(state: WireSessionState): SessionPill {
  switch (state.kind) {
    case "recording":
      return { label: "Recording", tone: "recording" };
    case "reviewing":
      return { label: "Replay", tone: "replay" };
    case "idle":
      return { label: "Idle", tone: "idle" };
  }
}
