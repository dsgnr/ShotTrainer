<script lang="ts">
  import { sessionPill } from "../lib/app/session-pill";
  import type { WireSessionState } from "../lib/wire/types";

  interface Props {
    session: WireSessionState;
    trackingText: string;
  }

  let { session, trackingText }: Props = $props();

  const pill = $derived(sessionPill(session));
</script>

<div class="header">
  <div class="brand">
    <img src="/icon.svg" alt="" width="24" height="24" />
    <span class="title">ShotTrainer</span>
  </div>
  <span class="pill" data-tone={pill.tone}>
    <span class="dot" aria-hidden="true"></span>
    <span class="visually-hidden">Session state: </span>{pill.label}
  </span>
  <span class="spacer"></span>
  <p
    class="hint num"
    title="Live mm-per-pixel reading. Lower means the camera is further from the target. The trace is correct in mm as soon as this number stabilises."
  >
    {trackingText}
  </p>
</div>

<style>
  .header {
    display: flex;
    align-items: center;
    gap: var(--space-4);
    height: 48px;
    padding: 0 var(--space-4);
  }

  .brand {
    display: flex;
    align-items: center;
    gap: var(--space-2);
  }

  .title {
    color: var(--text-heading);
    font-size: var(--text-sm);
    font-weight: 600;
    letter-spacing: 0.12em;
    text-transform: uppercase;
  }

  .pill {
    display: inline-flex;
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

  .dot {
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

  .spacer {
    flex: 1;
  }

  .hint {
    margin: 0;
    color: var(--text-muted);
    font-size: var(--text-sm);
  }
</style>
