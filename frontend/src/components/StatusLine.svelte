<script lang="ts">
  import { sessionPill } from "../lib/app/session-pill";
  import type { WireSessionState } from "../lib/wire/types";
  import type { StatusLine } from "../lib/app/status-line";

  interface Props {
    line: StatusLine;
    session: WireSessionState;
    trackingText: string;
    restarting: boolean;
    onrestart: () => void;
  }

  let { line, session, trackingText, restarting, onrestart }: Props = $props();

  const pill = $derived(sessionPill(session));
</script>

<div class="status-line">
  {#if line.text !== ""}
    <span class="dot" data-tone={line.tone} aria-hidden="true"></span>
  {/if}
  <p class="text" data-tone={line.tone}>{line.text}</p>
  {#if line.restart}
    <button type="button" disabled={restarting} onclick={onrestart}>
      {restarting ? "Restarting" : "Restart controller"}
    </button>
  {/if}
  <span class="pill" data-tone={pill.tone}>
    <span class="session-dot" aria-hidden="true"></span>
    <span class="visually-hidden">Session state: </span>{pill.label}
  </span>
  <p
    class="hint num"
    title="Live mm-per-pixel reading. Lower means the camera is further from the target. The trace is correct in mm as soon as this number stabilises."
  >
    {trackingText}
  </p>
</div>

<style>
  .status-line {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    min-height: 32px;
    padding: var(--space-1) var(--space-4);
    font-size: var(--text-sm);
  }

  .dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    flex: none;
  }

  .dot[data-tone="info"] {
    background: var(--tone-info);
  }

  .dot[data-tone="success"] {
    background: var(--tone-success);
  }

  .dot[data-tone="warning"] {
    background: var(--tone-warning);
  }

  .dot[data-tone="error"] {
    background: var(--tone-error);
  }

  .text {
    flex: 1;
    margin: 0;
  }

  .text[data-tone="info"] {
    color: var(--tone-info);
  }

  .text[data-tone="success"] {
    color: var(--tone-success);
  }

  .text[data-tone="warning"] {
    color: var(--tone-warning);
  }

  .text[data-tone="error"] {
    color: var(--tone-error);
  }
  .pill {
    display: inline-flex;
    flex-shrink: 0;
    align-items: center;
    gap: var(--space-2);
    padding: 3px 10px 3px 8px;
    border: 1px solid var(--divider);
    border-radius: 10px;
    color: var(--text-dim);
    font-size: var(--text-xs);
    font-weight: 600;
    letter-spacing: 0.1em;
    text-transform: uppercase;
  }

  .session-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: currentColor;
  }

  .pill[data-tone="idle"] {
    color: var(--pill-idle);
  }

  .pill[data-tone="recording"] {
    color: var(--pill-recording);
  }

  .pill[data-tone="replay"] {
    color: var(--pill-replay);
  }

  .hint {
    min-width: 0;
    max-width: 45%;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    margin: 0;
    color: var(--text-muted);
    font-size: var(--text-sm);
  }
</style>
