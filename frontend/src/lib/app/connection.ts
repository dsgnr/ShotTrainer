import type { Bridge } from "../bridge/bridge";
import type { FrameSink } from "../frames/sink";
import type { ShellStatus, WireEvent } from "../wire/types";

/** The part of `AppState` the connection writes to. */
export interface ConnectionTarget {
  dispatch(event: WireEvent): void;
  setShellStatus(shell: ShellStatus): void;
  clearFailure(): void;
  setConnectionError(error: string): void;
}

/** How often the status is asked again while the access prompts are open. */
export const ACCESS_POLL_MS = 1000;

function describe(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

/**
 * Connects the page to the shell in the order the shell needs. The event
 * listener registers first, then the frame channel, and only then does
 * `frontend_ready` ask the controller to send its state again, so none of it
 * is emitted before the page can receive it.
 */
export class Connection {
  readonly #bridge: Bridge;
  readonly #target: ConnectionTarget;
  readonly #frames: FrameSink;
  #poll: ReturnType<typeof setTimeout> | null = null;

  constructor(bridge: Bridge, target: ConnectionTarget, frames: FrameSink) {
    this.#bridge = bridge;
    this.#target = target;
    this.#frames = frames;
  }

  async start(): Promise<void> {
    try {
      await this.#bridge.listen((event) => this.#target.dispatch(event));
    } catch (error) {
      this.#target.setConnectionError(describe(error));
      return;
    }
    await this.#attach();
    await this.refreshStatus();
  }

  /** Replaces a stopped or failed controller and asks for its state. */
  async restart(): Promise<void> {
    try {
      await this.#bridge.restart();
      this.#target.clearFailure();
      await this.#attach();
    } catch {
      // The shell keeps the reason, and the status below reports it.
    }
    await this.refreshStatus();
  }

  async refreshStatus(): Promise<void> {
    this.#stopPolling();
    let shell: ShellStatus;
    try {
      shell = await this.#bridge.status();
    } catch (error) {
      this.#target.setConnectionError(describe(error));
      return;
    }
    this.#target.setShellStatus(shell);
    if (shell.awaitingAccess) {
      this.#poll = setTimeout(() => void this.refreshStatus(), ACCESS_POLL_MS);
    }
  }

  #stopPolling(): void {
    if (this.#poll !== null) {
      clearTimeout(this.#poll);
      this.#poll = null;
    }
  }

  async #attach(): Promise<void> {
    try {
      await this.#bridge.subscribeFrames((message) =>
        this.#frames.present(message, () => this.#bridge.frameDrawn()),
      );
      await this.#bridge.frontendReady();
    } catch {
      // A controller that could not start refuses `frontend_ready`, and the
      // status the caller asks for next carries the reason.
    }
  }
}
