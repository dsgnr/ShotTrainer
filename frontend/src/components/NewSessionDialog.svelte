<script lang="ts">
  import { untrack } from "svelte";
  import { focusTrap } from "../lib/app/focus-trap";
  import { clampPreferences } from "../lib/preferences/form";
  import { DEFAULT_SESSION_CATEGORY, SESSION_CATEGORIES, categoryLabel } from "../lib/wire/categories";
  import type { WireFace, WirePreferences } from "../lib/wire/types";
  import SessionOptions from "./SessionOptions.svelte";
  import Dropdown from "./Dropdown.svelte";
  let { prefs, faces, onclose, oncreate }: {
    prefs: WirePreferences; faces: WireFace[]; onclose: () => void;
    oncreate: (name: string, category: string, prefs: WirePreferences) => Promise<void>;
  } = $props();
  let name = $state("");
  let category = $state<string>(DEFAULT_SESSION_CATEGORY);
  let draft = $state(untrack(() => ({ ...prefs, targetFace: "default", preShotMs: 1500, postShotMs: 800,
    releaseWindowMs: 250, shotRefractoryMs: 400, shotDiameterMm: 4.5 })));
  let saving = $state(false);
  async function create(event: SubmitEvent): Promise<void> {
    event.preventDefault();
    if (saving) return;
    saving = true;
    try { await oncreate(name.trim(), category, clampPreferences(draft)); }
    finally { saving = false; }
  }
</script>

<!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
<div class="backdrop" role="presentation" onclick={onclose} onkeydown={(event) => {
  event.stopPropagation(); if (event.key === "Escape") onclose();
}}>
  <!-- svelte-ignore a11y_click_events_have_key_events -->
  <div class="dialog" role="dialog" aria-modal="true" aria-labelledby="new-session-title"
    tabindex="-1" use:focusTrap onclick={(event) => event.stopPropagation()}>
    <h2 id="new-session-title">New session</h2>
    <form onsubmit={create}>
      <fieldset disabled={saving}>
        <label class="name">Session name <input type="text" bind:value={name} /></label>
        <label for="new-session-category">Session category</label>
        <Dropdown id="new-session-category" label="Session category" bind:value={category}
          options={SESSION_CATEGORIES.map(value => ({ value, label: categoryLabel(value) }))} />
        <SessionOptions bind:draft {faces} />
      </fieldset>
      <footer><button type="button" disabled={saving} onclick={onclose}>Cancel</button>
        <button type="submit" class="primary" disabled={saving}>Create session</button></footer>
    </form>
  </div>
</div>

<style>
  .backdrop { position: fixed; inset: 0; z-index: 10; display: grid; place-items: center; background: #0008; padding: 16px; }
  .dialog { width: min(440px, 100%); max-height: calc(100dvh - 32px); display: flex; flex-direction: column; background: var(--panel); border: 1px solid var(--border); border-radius: var(--radius); }
  h2 { margin: 0; padding: 20px 24px 12px; color: var(--text-heading); }
  form { display: flex; flex-direction: column; min-height: 0; }
  fieldset { margin: 0; border: 0; padding: 8px 24px 20px; display: grid; gap: 12px; overflow: auto; min-height: 0; }
  .name { display: grid; gap: 8px; }
  input { padding: 6px 8px; color: var(--text); background: var(--panel-raised); border: 1px solid var(--border); border-radius: var(--radius-control); font: inherit; }
  footer { display: flex; justify-content: flex-end; gap: 8px; padding: 16px 24px; border-top: 1px solid var(--divider); }
</style>
