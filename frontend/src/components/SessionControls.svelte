<script lang="ts">
  import type { CommandSender } from "../lib/app/commands";
  import { primaryLabel } from "../lib/app/session-controls";
  import type { WireSessionState } from "../lib/wire/types";
  let { session, summary, send, name = "", category = "practice", onnew }: {
    session: WireSessionState; summary: string; send: CommandSender;
    name?: string; category?: string; onnew?: () => void;
  } = $props();
  const recording = $derived(session.kind === "recording");
  function onPrimary(): void {
    if (recording) void send({ type: "stopSession" });
    else if (session.kind === "reviewing") onnew?.();
    else void send({ type: "startSession", name, category });
  }
</script>
<div class="session">
  <button type="button" class="primary" data-variant={recording ? "stop" : ""} onclick={onPrimary}>
    {session.kind === "reviewing" ? "New session" : primaryLabel(session)}
  </button>
  <p class="summary">{summary || "Not recording"}</p>
</div>
<style>
  .session { display: flex; flex-direction: column; gap: 8px; }
  .primary[data-variant="stop"] {
    background: var(--tone-error);
  }

  .summary {
    margin: 0;
    color: var(--text-dim);
  }
</style>
