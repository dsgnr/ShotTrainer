import type { WireEvent, WireFrame } from "../wire/types";

export interface CameraState {
  /** The overlay of the latest frame, or `null` before the first frame and while the camera is stopped. */
  frame: WireFrame | null;
  /** True after `cameraIdle` until the next frame. */
  idle: boolean;
}

export const initialCamera: CameraState = { frame: null, idle: false };

const IDLE: CameraState = { frame: null, idle: true };

export function reduceCamera(state: CameraState, event: WireEvent): CameraState {
  switch (event.type) {
    case "frame":
      return { frame: event, idle: false };
    case "cameraIdle":
      return state.idle ? state : IDLE;
    default:
      return state;
  }
}
