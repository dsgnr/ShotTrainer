<script lang="ts">
  import { focusTrap } from "../lib/app/focus-trap";
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
  let naming = $state(false);
  let category = $state<string>(DEFAULT_SESSION_CATEGORY);

  const recording = $derived(session.kind === "recording");
  const label = $derived(primaryLabel(session));
  const locked = $derived(secondaryDisabled(session));

  function onPrimary(): void {
    if (recording) {
      void send({ type: "stopSession" });
    } else {
      naming = true;
    }
  }

  function startSession(event: SubmitEvent): void {
    event.preventDefault();
    naming = false;
    void send({ type: "startSession", name: name.trim(), category });
  }

  function onClear(): void {
    void send({ type: "clearShots" });
  }
</script>

<div class="session">
  <button type="button" class="primary" data-variant={recording ? "stop" : ""} onclick={onPrimary}>
    {label}
  </button>

  {#if !locked}
    <button type="button" class="clear" onclick={onClear}>Clear shots</button>
  {/if}

  <p class="summary">{summary || "Not recording"}</p>
</div>

{#if naming}
  <!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
  <div
    class="backdrop"
    role="presentation"
    onclick={() => naming = false}
    onkeydown={(event) => {
      event.stopPropagation();
      if (event.key === "Escape") {
        naming = false;
      }
    }}
  >
    <!-- svelte-ignore a11y_click_events_have_key_events -->
    <div
      class="dialog"
      role="dialog"
      aria-modal="true"
      aria-labelledby="start-session-title"
      tabindex="-1"
      use:focusTrap
      onclick={(event) => event.stopPropagation()}
    >
      <h2 id="start-session-title">Start session</h2>
      <form onsubmit={startSession}>
        <label class="field">
          <span>Session name</span>
          <input type="text" bind:value={name} />
        </label>

        <label class="field">
          <span>Session category</span>
          <select bind:value={category} title="Tag this session as practice, sighters, or a match.">
            {#each SESSION_CATEGORIES as value (value)}
              <option {value}>{categoryLabel(value)}</option>
            {/each}
          </select>
        </label>
        <div class="actions">
          <button type="button" onclick={() => naming = false}>Cancel</button>
          <button type="submit" class="primary">Start session</button>
        </div>
      </form>
    </div>
  </div>
{/if}

<style>
  .backdrop {
    position: fixed;
    inset: 0;
    display: grid;
    place-items: center;
    background: rgba(0, 0, 0, 0.5);
    z-index: 10;
  }

  .dialog {
    width: min(400px, 92vw);
    padding: 20px 24px;
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: var(--radius);
  }

  h2 {
    margin: 0 0 16px;
    color: var(--text-heading);
  }

  .dialog .field {
    display: grid;
    gap: 8px;
  }

  form {
    display: grid;
    gap: 12px;
  }

  .actions {
    display: flex;
    justify-content: flex-end;
    gap: 8px;
    margin-top: 16px;
  }

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
