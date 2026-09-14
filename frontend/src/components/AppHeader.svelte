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
    <img src="/icon.svg" alt="" width="32" height="32" />
    <span class="title">ShotTrainer</span>
  </div>
  <span class="pill" data-tone={pill.tone}>
    <span class="visually-hidden">Session state: </span>{pill.label}
  </span>
  <span class="spacer"></span>
  <p
    class="hint"
    title="Live mm-per-pixel reading. Lower means the camera is further from the target. The trace is correct in mm as soon as this number stabilises."
  >
    {trackingText}
  </p>
</div>

<style>
  .header {
    display: flex;
    align-items: center;
    gap: 16px;
    height: 60px;
    padding: 8px 16px 8px 20px;
  }

  .brand {
    display: flex;
    align-items: center;
    gap: 10px;
  }

  .title {
    color: var(--text-heading);
    font-size: 14px;
    font-weight: 600;
    letter-spacing: 1px;
    text-transform: uppercase;
  }

  .pill {
    min-width: 110px;
    padding: 4px 12px;
    border: 1px solid currentColor;
    border-radius: 12px;
    font-size: 11px;
    letter-spacing: 1.5px;
    text-align: center;
    text-transform: uppercase;
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
    color: var(--text-dim);
  }
</style>
