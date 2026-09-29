<script lang="ts">
  import { untrack } from "svelte";
  import SessionOptions from "./SessionOptions.svelte";
  import { clampPreferences } from "../lib/preferences/form";
  import type { CommandSender } from "../lib/app/commands";
  import type { WireFace, WirePreferences } from "../lib/wire/types";

  let { prefs, faces, locked, send }: {
    prefs: WirePreferences | null; faces: WireFace[]; locked: boolean; send: CommandSender;
  } = $props();
  let draft = $state<WirePreferences | null>(null);
  $effect(() => { const current = prefs; untrack(() => { draft = current ? { ...current } : null; }); });
  async function save(event: SubmitEvent): Promise<void> {
    event.preventDefault();
    if (draft && !locked) await send({ type: "setSessionSettings", prefs: clampPreferences(draft) });
  }
</script>

<details class="settings">
  <summary>Session settings</summary>
  {#if draft}
    <form onsubmit={save}>
      <fieldset disabled={locked}>
        <SessionOptions bind:draft {faces} />
        <button type="submit">Apply session settings</button>
      </fieldset>
      {#if locked}<p>Create a new session to change these settings.</p>{/if}
    </form>
  {/if}
</details>

<style>
  .settings { border-top: 1px solid var(--divider); padding-top: var(--space-3); }
  summary { cursor: pointer; color: var(--text-heading); }
  fieldset { border: 0; margin: 0; padding: var(--space-3) 0 0; display: grid; gap: 8px; min-width: 0; }
  p { color: var(--text-muted); font-size: var(--text-sm); }
</style>
