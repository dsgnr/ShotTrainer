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
    gap: 12px;
    min-height: 36px;
    padding: 4px 16px;
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
