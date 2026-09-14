import { describe, expect, it } from "vitest";

import { initialStatus, type StatusState } from "../stores/status";
import type { ShellStatus } from "../wire/types";
import { AWAITING_ACCESS, FAKE_DEVICES, STARTING, STOPPED, statusLine } from "./status-line";

const RUNNING: ShellStatus = {
  running: true,
  error: null,
  fakeDevices: false,
  denied: [],
  awaitingAccess: false,
};

function status(shell: Partial<ShellStatus> | null, extra: Partial<StatusState> = {}): StatusState {
  return { ...initialStatus, shell: shell === null ? null : { ...RUNNING, ...shell }, ...extra };
}

const WARNING = { text: "Camera: busy", severity: "warning", durationMs: 5000 } as const;

describe("statusLine", () => {
  it("says the page is starting before the first status", () => {
    expect(statusLine(status(null), 0)).toEqual({ text: STARTING, tone: "info", restart: false });
  });

  it("is empty while a controller with system devices runs quietly", () => {
    expect(statusLine(status({}), 0).text).toBe("");
  });

  it("offers a restart after the controller fails, whatever else is known", () => {
    const line = statusLine(
      status({ awaitingAccess: true }, { failure: "boom", message: WARNING, messageAt: 0 }),
      0,
    );
    expect(line).toEqual({ text: "The controller stopped: boom", tone: "error", restart: true });
  });

  it("offers a restart when the controller could not start", () => {
    expect(statusLine(status({ running: false, error: "no database" }), 0)).toEqual({
      text: "The controller could not start: no database",
      tone: "error",
      restart: true,
    });
  });

  it("offers a restart when the controller has stopped", () => {
    expect(statusLine(status({ running: false }), 0)).toEqual({
      text: STOPPED,
      tone: "error",
      restart: true,
    });
  });

  it("explains a page that cannot reach the shell, without a restart it could not send", () => {
    const line = statusLine(status(null, { connectionError: "no IPC", failure: "boom" }), 0);
    expect(line.text).toBe("The page could not reach the application: no IPC");
    expect(line.restart).toBe(false);
  });

  it("says it is waiting while the access prompts are open, above any message", () => {
    const line = statusLine(status({ awaitingAccess: true }, { message: WARNING, messageAt: 0 }), 0);
    expect(line).toEqual({ text: AWAITING_ACCESS, tone: "info", restart: false });
  });

  it("shows a message with its severity until it expires, then the refused access", () => {
    const state = status({ denied: ["camera", "microphone"] }, { message: WARNING, messageAt: 1000 });
    expect(statusLine(state, 5999)).toEqual({ text: "Camera: busy", tone: "warning", restart: false });
    expect(statusLine(state, 6000)).toEqual({
      text: "Access refused for the camera and microphone. Allow it in the system privacy settings.",
      tone: "warning",
      restart: false,
    });
  });

  it("names fake devices when nothing else needs saying", () => {
    expect(statusLine(status({ fakeDevices: true }), 0).text).toBe(FAKE_DEVICES);
  });
});
