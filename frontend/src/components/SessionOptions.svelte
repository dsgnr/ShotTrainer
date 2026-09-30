<script lang="ts">
  import PositionSelector from "./PositionSelector.svelte";
  import Dropdown from "./Dropdown.svelte";
  import { NUMBER_RANGES } from "../lib/preferences/form";
  import type { WireFace, WirePreferences } from "../lib/wire/types";
  let { draft = $bindable(), faces }: { draft: WirePreferences; faces: WireFace[] } = $props();
  const fields = [
    ["preShotMs", "Pre-shot", "ms"], ["postShotMs", "Post-shot", "ms"],
    ["releaseWindowMs", "Release window", "ms"], ["shotRefractoryMs", "Refractory", "ms"],
    ["shotDiameterMm", "Shot diameter", "mm"],
  ] as const;
</script>
<PositionSelector bind:value={draft.sessionPosition} />
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
<style>
  .field { display: flex; justify-content: space-between; gap: 8px; align-items: center; }
  input { width: 90px; min-width: 0; padding: 6px; color: var(--text); background: var(--panel-raised); border: 1px solid var(--border); border-radius: var(--radius-control); }
</style>
