<script lang="ts">
  import type { StatusLine } from "../lib/app/status-line";

  interface Props {
    line: StatusLine;
    restarting: boolean;
    onrestart: () => void;
  }

  let { line, restarting, onrestart }: Props = $props();
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
</style>
