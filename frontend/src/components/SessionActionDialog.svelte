<script module lang="ts">
  import type { WireSessionSummary } from "../lib/wire/types";
  export type SessionAction = { kind: "import" } | {
    kind: "rename" | "category" | "delete" | "export";
    session: WireSessionSummary;
  };
</script>

<script lang="ts">
  import { untrack } from "svelte";
  import { focusTrap } from "../lib/app/focus-trap";
  import { SESSION_CATEGORIES, categoryLabel } from "../lib/wire/categories";
  import type { WireCommand } from "../lib/wire/types";
  import Dropdown from "./Dropdown.svelte";

  let { action, recording, onconfirm, onclose }: {
    action: SessionAction; recording: boolean;
    onconfirm: (command: WireCommand) => Promise<void>; onclose: () => void;
  } = $props();
  let value = $state(untrack(() => action.kind === "rename" ? action.session.name : action.kind === "category" ? action.session.category : ""));
  let saving = $state(false);
  let error = $state<string | null>(null);
  const title = $derived(({ rename: "Rename session", category: "Session category", delete: "Delete session", export: "Export CSV", import: "Import CSV" })[action.kind]);
  const blocked = $derived(saving || (action.kind === "import" && recording));
  const confirmLabel = $derived(action.kind === "delete" ? "Delete session" : action.kind === "import" ? "Import" : action.kind === "export" ? "Export" : "Save");

  function close(): void { if (!saving) onclose(); }

  async function submit(event: SubmitEvent): Promise<void> {
    event.preventDefault();
    if (blocked) return;
    const text = value.trim();
    if ((action.kind === "import" || action.kind === "export") && !text) return;
    if (action.kind === "category" && !(SESSION_CATEGORIES as readonly string[]).includes(text)) return;
    let command: WireCommand;
    switch (action.kind) {
      case "rename": command = { type: "renameSession", id: action.session.id, name: text }; break;
      case "category": command = { type: "setSessionCategory", id: action.session.id, category: text }; break;
      case "delete": command = { type: "deleteSession", id: action.session.id }; break;
      case "export": command = { type: "exportSession", id: action.session.id, dir: text }; break;
      case "import": command = { type: "importSession", path: text }; break;
    }
    saving = true;
    error = null;
    try { await onconfirm(command); }
    catch (failure) { error = String(failure); }
    finally { saving = false; }
  }
</script>

<!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
<div class="backdrop" role="presentation" onclick={close} onkeydown={(event) => {
  event.stopPropagation(); if (event.key === "Escape") close();
}}>
  <!-- svelte-ignore a11y_click_events_have_key_events -->
  <div class="dialog" role="dialog" aria-modal="true" aria-labelledby="session-action-title"
    tabindex="-1" use:focusTrap onclick={(event) => event.stopPropagation()}>
    <h2 id="session-action-title">{title}</h2>
    <form onsubmit={submit}>
      <fieldset disabled={blocked}>
        {#if action.kind === "rename"}
          <label>Session name <input type="text" bind:value /></label>
        {:else if action.kind === "category"}
          <label for="session-action-category">Category</label>
          <Dropdown id="session-action-category" label="Session category" bind:value
            options={SESSION_CATEGORIES.map(value => ({ value, label: categoryLabel(value) }))} />
        {:else if action.kind === "delete"}
          <p>Delete {action.session.name || `Session #${action.session.id}`} and all its shots and trace data?</p>
        {:else if action.kind === "export"}
          <label>Export folder <input type="text" bind:value required /></label>
        {:else}
          <label>Exported shots CSV path <input type="text" bind:value required /></label>
          <p>Enter the exported *_shots.csv path. A matching trace file is loaded when present.</p>
        {/if}
      </fieldset>
      {#if action.kind === "import" && recording}<p class="message">Stop recording before importing.</p>{/if}
      {#if error}<p class="message" role="alert">{error}</p>{/if}
      <footer><button type="button" disabled={saving} onclick={close}>Cancel</button>
        <button type="submit" class="primary" disabled={blocked || ((action.kind === "import" || action.kind === "export") && !value.trim())}>{confirmLabel}</button></footer>
    </form>
  </div>
</div>

<style>
  .backdrop { position: fixed; inset: 0; z-index: 10; display: grid; place-items: center; background: #0008; padding: 16px; }
  .dialog { width: min(440px, 100%); max-height: calc(100dvh - 32px); overflow: auto; background: var(--panel); border: 1px solid var(--border); border-radius: var(--radius); }
  h2 { margin: 0; padding: 20px 24px 12px; color: var(--text-heading); }
  fieldset { margin: 0; border: 0; padding: 8px 24px 20px; display: grid; gap: 12px; min-width: 0; }
  label { display: grid; gap: 8px; }
  input { min-width: 0; padding: 6px 8px; color: var(--text); background: var(--panel-raised); border: 1px solid var(--border); border-radius: var(--radius-control); font: inherit; }
  p { margin: 0; }
  .message { padding: 0 24px 16px; }
  footer { display: flex; justify-content: flex-end; gap: 8px; padding: 16px 24px; border-top: 1px solid var(--divider); }
</style>
