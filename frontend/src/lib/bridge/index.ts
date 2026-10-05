import { isTauri } from "@tauri-apps/api/core";

import type { Bridge } from "./bridge";
import { MockBridge } from "./mock";
import { TauriBridge } from "./tauri";

export type { Bridge, EventHandler, PacketHandler, Unlisten } from "./bridge";

/** The Tauri bridge inside the shell, otherwise the browser mock. */
export function createBridge(): Bridge {
  return isTauri() ? new TauriBridge() : new MockBridge();
}
