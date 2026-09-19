import type { Bridge } from "../bridge/bridge";
import type { WireCommand } from "../wire/types";

/** The part of `AppState` a refused command reports through. */
export interface CommandTarget {
  dispatch(event: { type: "message"; message: { text: string; severity: "warning"; durationMs: number } }): void;
}

export type CommandSender = (command: WireCommand) => Promise<void>;

/** How long a refused-command warning stays in the status line. */
const WARNING_MS = 5000;

/**
 * A sender that forwards commands to the shell and surfaces a refusal as a
 * warning in the status line. The shell rejects a command with the controller's
 * reason when it is not running.
 */
export function createCommandSender(bridge: Bridge, target: CommandTarget): CommandSender {
  return async (command) => {
    try {
      await bridge.send(command);
    } catch (error) {
      const text = error instanceof Error ? error.message : String(error);
      target.dispatch({ type: "message", message: { text, severity: "warning", durationMs: WARNING_MS } });
    }
  };
}
