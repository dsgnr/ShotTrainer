<script lang="ts">
  import { untrack } from "svelte";
  import { focusTrap } from "../lib/app/focus-trap";
  import SessionOptions from "./SessionOptions.svelte";
  import { clampPreferences } from "../lib/preferences/form";
  import type { CommandSender } from "../lib/app/commands";
  import type { WireFace, WirePreferences } from "../lib/wire/types";

  let { prefs, faces, locked, send, onclose }: {
    prefs: WirePreferences | null; faces: WireFace[]; locked: boolean; send: CommandSender; onclose: () => void;
  } = $props();
  let draft = $state<WirePreferences | null>(null);
  $effect(() => { const current = prefs; untrack(() => { draft = current ? { ...current } : null; }); });
  async function save(event: SubmitEvent): Promise<void> {
    event.preventDefault();
    if (!draft || locked) return;
    await send({ type: "setSessionSettings", prefs: clampPreferences(draft) });
    onclose();
  }
</script>

<!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
<div class="backdrop" role="presentation" onclick={onclose} onkeydown={(event) => {
  event.stopPropagation(); if (event.key === "Escape") onclose();
}}>
  <!-- svelte-ignore a11y_click_events_have_key_events -->
  <div class="dialog" role="dialog" aria-modal="true" aria-labelledby="session-settings-title"
    tabindex="-1" use:focusTrap onclick={(event) => event.stopPropagation()}>
    <h2 id="session-settings-title">Session settings</h2>
    {#if draft}
      <form onsubmit={save}>
        <div class="body">
          <fieldset disabled={locked}>
            <SessionOptions bind:draft {faces} />
          </fieldset>
          {#if locked}<p>Create a new session to change these settings.</p>{/if}
        </div>
        <footer>
          <button type="button" onclick={onclose}>Close</button>
          <button type="submit" class="primary" disabled={locked}>Apply session settings</button>
        </footer>
      </form>
    {/if}
  </div>
</div>

<style>
  .backdrop { position: fixed; inset: 0; z-index: 10; display: grid; place-items: center; background: #0008; padding: 16px; }
  .dialog { width: min(440px, 100%); max-height: calc(100dvh - 32px); display: flex; flex-direction: column; background: var(--panel); border: 1px solid var(--border); border-radius: var(--radius); }
  h2 { margin: 0; padding: 20px 24px 12px; color: var(--text-heading); }
  form { display: flex; flex-direction: column; min-height: 0; }
  .body { overflow: auto; min-height: 0; padding: 8px 24px 20px; }
  fieldset { border: 0; margin: 0; padding: 0; display: grid; gap: 12px; min-width: 0; }
  p { color: var(--text-muted); font-size: var(--text-sm); }
  footer { flex: none; display: flex; justify-content: flex-end; gap: 8px; padding: 16px 24px; border-top: 1px solid var(--divider); }
</style>
