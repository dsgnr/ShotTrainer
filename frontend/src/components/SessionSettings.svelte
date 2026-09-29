<script lang="ts">
  import { untrack } from "svelte";
  import Dropdown from "./Dropdown.svelte";
  import { NUMBER_RANGES, clampPreferences } from "../lib/preferences/form";
  import type { CommandSender } from "../lib/app/commands";
  import type { WireFace, WirePreferences } from "../lib/wire/types";

  let { prefs, faces, locked, send }: {
    prefs: WirePreferences | null; faces: WireFace[]; locked: boolean; send: CommandSender;
  } = $props();
  let draft = $state<WirePreferences | null>(null);
  $effect(() => { const current = prefs; untrack(() => { draft = current ? { ...current } : null; }); });
  const fields = [
    ["preShotMs", "Pre-shot", "ms"], ["postShotMs", "Post-shot", "ms"],
    ["releaseWindowMs", "Release window", "ms"], ["shotRefractoryMs", "Refractory", "ms"],
    ["shotDiameterMm", "Shot diameter", "mm"],
  ] as const;
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
        <label for="session-target">Target face</label>
        <Dropdown id="session-target" label="Session target face" bind:value={draft.targetFace}
          options={faces.map(face => ({ value: face.key, label: face.label }))} />
        {#each fields as [key, label, unit]}
          <label class="field">
            <span>{label} ({unit})</span>
            <input type="number" min={NUMBER_RANGES[key][0]} max={NUMBER_RANGES[key][1]}
              step={key === "shotDiameterMm" ? 0.1 : 1} bind:value={draft[key]} />
          </label>
        {/each}
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
  .field { display: flex; justify-content: space-between; gap: 8px; align-items: center; }
  input { width: 90px; min-width: 0; padding: 6px; color: var(--text); background: var(--panel-raised); border: 1px solid var(--border); border-radius: var(--radius-control); }
  p { color: var(--text-muted); font-size: var(--text-sm); }
</style>
