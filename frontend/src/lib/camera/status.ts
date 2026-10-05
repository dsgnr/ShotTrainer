import type { CameraState } from "../stores/camera";
import type { TrackingStatus } from "../wire/types";

export interface StatusBadge {
  label: string;
  colour: string;
}

/** The badge label and dot colour for each tracking status. */
export const STATUS_BADGES: Record<TrackingStatus, StatusBadge> = {
  idle: { label: "Idle", colour: "#888888" },
  tracking: { label: "Tracking", colour: "#27ae60" },
  lost: { label: "No target", colour: "#e67e22" },
  rejected: { label: "Outside region", colour: "#d35400" },
};

/** The badge over the camera, or `null` before the first frame. */
export function statusBadge(camera: CameraState): StatusBadge | null {
  if (camera.frame !== null) {
    return STATUS_BADGES[camera.frame.status];
  }
  return camera.idle ? STATUS_BADGES.idle : null;
}
