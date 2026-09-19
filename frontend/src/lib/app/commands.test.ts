import { describe, expect, it, vi } from "vitest";

import type { Bridge } from "../bridge/bridge";
import { AppState } from "../stores/app.svelte";
import type { WireCommand } from "../wire/types";
import { createCommandSender } from "./commands";

function stubBridge(send: (command: WireCommand) => Promise<void>): Bridge {
  return {
    listen: vi.fn(),
    subscribeFrames: vi.fn(),
    frontendReady: vi.fn(),
    send,
    frameDrawn: vi.fn(),
    status: vi.fn(),
    restart: vi.fn(),
  } as unknown as Bridge;
}

describe("createCommandSender", () => {
  it("forwards a command to the bridge", async () => {
    const sent: WireCommand[] = [];
    const app = new AppState();
    const sendCommand = createCommandSender(
      stubBridge(async (command) => {
        sent.push(command);
      }),
      app,
    );
    await sendCommand({ type: "clearShots" });
    expect(sent).toEqual([{ type: "clearShots" }]);
  });

  it("shows the shell's reason as a warning when a command is refused", async () => {
    const app = new AppState();
    const sendCommand = createCommandSender(
      stubBridge(() => Promise.reject(new Error("The controller has stopped."))),
      app,
    );
    await sendCommand({ type: "stopSession" });
    expect(app.status.message?.text).toBe("The controller has stopped.");
    expect(app.status.message?.severity).toBe("warning");
  });
});
