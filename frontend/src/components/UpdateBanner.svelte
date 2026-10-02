<script lang="ts">
  import type { UpdateManager } from "../lib/app/updates.svelte";
  let { updates, recording }: { updates: UpdateManager; recording: boolean } = $props();
  const label = $derived(updates.stage === "downloading" ? "Downloading..." : updates.stage === "installing" ? "Installing..." : "Install and restart");
</script>

{#if updates.available}
  <section class="update" aria-label="Application update" aria-live="polite">
    <span>Version {updates.available.version} is available</span>
    {#if updates.available.selfInstall}
      <button class="primary" disabled={recording || updates.busy} onclick={() => void updates.install()}>{label}</button>
      {#if recording}<span>Stop recording to install the update.</span>{/if}
    {:else}
      <button class="primary" onclick={() => void updates.openReleases()}>Download</button>
    {/if}
    <button disabled={updates.busy} onclick={() => void updates.dismiss()}>Later</button>
    {#if updates.error}<span role="alert">{updates.error}</span>{/if}
  </section>
{/if}

<style>
  .update { position: fixed; top: 16px; left: 50%; transform: translateX(-50%); z-index: 20; display: flex; align-items: center; flex-wrap: wrap; gap: 12px; width: max-content; max-width: calc(100vw - 80px); padding: 12px 16px; border: 1px solid var(--accent-strong); border-radius: var(--radius); background: var(--panel-raised); box-shadow: 0 8px 24px #0004; }
</style>
