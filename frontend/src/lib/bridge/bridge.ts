import type { ShellStatus, WireCommand, WireEvent } from "../wire/types";

export type EventHandler = (event: WireEvent) => void;
export type PacketHandler = (message: unknown) => void;
export type Unlisten = () => void;

/**
 * The page's only route to the shell. `TauriBridge` calls the Tauri
 * commands in `src-tauri/src/shell.rs`, and `MockBridge` imitates them in a
 * plain browser.
 */
export interface Bridge {
  /** Resolves once `handler` receives every later event with a known type. */
  listen(handler: EventHandler): Promise<Unlisten>;
  /** Sends later pixel packets to `onPacket` and forgets those in flight. */
  subscribeFrames(onPacket: PacketHandler): Promise<void>;
  /** Asks the controller to send its state again. Call it after `listen`. */
  frontendReady(): Promise<void>;
  /** Rejects with the shell's reason when the controller is not running. */
  send(command: WireCommand): Promise<void>;
  /** Reports one packet drawn. It never throws. */
  frameDrawn(): void;
  status(): Promise<ShellStatus>;
  /** Replaces the controller. Subscribe and call `frontendReady` again after it. */
  restart(): Promise<void>;
}
