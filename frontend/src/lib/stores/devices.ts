import type { WireCamera, WireEvent } from "../wire/types";

export interface DevicesState {
  cameras: WireCamera[];
  microphones: string[];
  /** The saved camera name, so the camera list can preselect it. */
  savedCamera: string;
}

export const initialDevices: DevicesState = {
  cameras: [],
  microphones: [],
  savedCamera: "",
};

export function reduceDevices(state: DevicesState, event: WireEvent): DevicesState {
  if (event.type !== "deviceOptions") {
    return state;
  }
  return { cameras: event.cameras, microphones: event.microphones, savedCamera: event.savedCamera };
}
