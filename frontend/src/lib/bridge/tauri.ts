import { Channel, invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";

import { parseEvent } from "../wire/events";
import type { ShellStatus, WireCommand } from "../wire/types";
import type { Bridge, EventHandler, PacketHandler, Unlisten } from "./bridge";

/** The Tauri event every controller event arrives under. */
export const UI_EVENT = "ui-event";

export class TauriBridge implements Bridge {
  listen(handler: EventHandler): Promise<Unlisten> {
    return listen<unknown>(UI_EVENT, (event) => {
      const parsed = parseEvent(event.payload);
      if (parsed !== null) {
        handler(parsed);
      }
    });
  }

  async subscribeFrames(onPacket: PacketHandler): Promise<void> {
    await invoke("subscribe_frames", { onFrame: new Channel<unknown>(onPacket) });
  }

  async frontendReady(): Promise<void> {
    await invoke("frontend_ready");
  }

  async send(command: WireCommand): Promise<void> {
    await invoke("send_command", { command });
  }

  frameDrawn(): void {
    // The command cannot fail in the shell, so a rejection means the IPC
    // itself is gone and there is nothing to retry.
    invoke("frame_drawn").catch(() => undefined);
  }

  status(): Promise<ShellStatus> {
    return invoke<ShellStatus>("controller_status");
  }

  async restart(): Promise<void> {
    await invoke("restart_controller");
  }
}
