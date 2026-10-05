<script lang="ts">
  import type { CommandSender } from "../lib/app/commands";
  import { primaryLabel, secondaryDisabled } from "../lib/app/session-controls";
  import {
    DEFAULT_SESSION_CATEGORY,
    SESSION_CATEGORIES,
    categoryLabel,
  } from "../lib/wire/categories";
  import type { WireSessionState } from "../lib/wire/types";

  interface Props {
    session: WireSessionState;
    summary: string;
    send: CommandSender;
  }

  let { session, summary, send }: Props = $props();

  let name = $state("");
  let category = $state<string>(DEFAULT_SESSION_CATEGORY);

  const recording = $derived(session.kind === "recording");
  const label = $derived(primaryLabel(session));
  const locked = $derived(secondaryDisabled(session));

  function onPrimary(): void {
    if (recording) {
      void send({ type: "stopSession" });
    } else {
      void send({ type: "startSession", name: name.trim(), category });
    }
  }

  function onClear(): void {
    void send({ type: "clearShots" });
  }
</script>

<div class="session">
  <label class="field">
    <span class="visually-hidden">Session name</span>
    <input
      type="text"
      placeholder="Session name"
      bind:value={name}
      disabled={locked}
    />
  </label>

  <label class="field">
    <span class="visually-hidden">Session category</span>
    <select bind:value={category} disabled={locked} title="Tag this session as practice, sighters, or a match.">
      {#each SESSION_CATEGORIES as value (value)}
        <option {value}>{categoryLabel(value)}</option>
      {/each}
    </select>
  </label>

  <button type="button" class="primary" data-variant={recording ? "stop" : ""} onclick={onPrimary}>
    {label}
  </button>

  <button type="button" class="clear" disabled={locked} onclick={onClear}>Clear shots</button>

  <p class="summary">{summary || "Not recording"}</p>
</div>

<style>
  .session {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .field {
    display: block;
  }

  input,
  select {
    width: 100%;
    padding: 6px 8px;
    color: var(--text);
    background: var(--panel-raised);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    font: inherit;
  }

  input:disabled,
  select:disabled {
    opacity: 0.6;
  }

  .primary[data-variant="stop"] {
    background: var(--tone-error);
  }

  .summary {
    margin: 0;
    color: var(--text-dim);
  }
</style>
