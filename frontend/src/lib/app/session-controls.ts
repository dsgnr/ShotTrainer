import type { WireSessionState } from "../wire/types";

/** The primary button label. It stops a recording and starts one otherwise. */
export function primaryLabel(state: WireSessionState): string {
  return state.kind === "recording" ? "Stop session" : "Start session";
}

/** Whether the name, category and clear controls are locked, which they are while recording. */
export function secondaryDisabled(state: WireSessionState): boolean {
  return state.kind === "recording";
}
