import { activeMessage, type StatusState } from "../stores/status";

export type Tone = "info" | "success" | "warning" | "error";

export interface StatusLine {
  text: string;
  tone: Tone;
  /** Whether to offer `Restart controller`. */
  restart: boolean;
}

/** The shell's reply to a command once the controller thread has ended. */
export const STOPPED = "The controller has stopped. Restart it to continue.";
export const STARTING = "Starting";
export const AWAITING_ACCESS =
  "Waiting for camera and microphone access. Answer the system prompts to continue.";
export const FAKE_DEVICES = "Using fake devices";

/**
 * What the status line under the window shows, most important first. A
 * stopped controller outranks every message, and a transient message
 * outranks the refused-access reminder that would otherwise stay for good.
 */
export function statusLine(status: StatusState, now: number): StatusLine {
  if (status.connectionError !== null) {
    return {
      text: `The page could not reach the application: ${status.connectionError}`,
      tone: "error",
      restart: false,
    };
  }
  if (status.failure !== null) {
    return { text: `The controller stopped: ${status.failure}`, tone: "error", restart: true };
  }
  const shell = status.shell;
  if (shell === null) {
    return { text: STARTING, tone: "info", restart: false };
  }
  if (shell.error !== null) {
    return { text: `The controller could not start: ${shell.error}`, tone: "error", restart: true };
  }
  if (!shell.running) {
    return { text: STOPPED, tone: "error", restart: true };
  }
  if (shell.awaitingAccess) {
    return { text: AWAITING_ACCESS, tone: "info", restart: false };
  }
  const message = activeMessage(status, now);
  if (message !== null) {
    return { text: message.text, tone: message.severity, restart: false };
  }
  if (shell.denied.length > 0) {
    return {
      text: `Access refused for the ${shell.denied.join(" and ")}. Allow it in the system privacy settings.`,
      tone: "warning",
      restart: false,
    };
  }
  if (shell.fakeDevices) {
    return { text: FAKE_DEVICES, tone: "info", restart: false };
  }
  return { text: "", tone: "info", restart: false };
}
