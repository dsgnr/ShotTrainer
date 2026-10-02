<script lang="ts">
  import { onMount } from "svelte";
  import { getVersion } from "@tauri-apps/api/app";
  import { isTauri } from "@tauri-apps/api/core";
  import type { UpdateManager } from "../lib/app/updates.svelte";
  let { updates }: { updates?: UpdateManager } = $props();
  const repository = "https://github.com/dsgnr/ShotTrainer";
  let version = $state(isTauri() ? "Loading..." : "Browser preview");
  onMount(() => {
    if (isTauri()) void getVersion().then(value => { version = value; }, () => { version = "Unavailable"; });
  });
</script>

<section class="about" aria-label="About ShotTrainer">
  <h2>About ShotTrainer</h2>
  <p>Version {version}</p>
  <p><a href={repository} target="_blank" rel="noopener noreferrer">GitHub repository</a></p>
  <p class="repository">{repository}</p>
  {#if updates}
    <button disabled={updates.busy || updates.available !== null} onclick={() => void updates.check()}>Check for updates</button>
    {#if updates.stage === "checking"}<p>Checking for updates...</p>
    {:else if updates.error}<p role="alert">{updates.error}</p>
    {:else if updates.available}<p>Version {updates.available.version} is available.</p>
    {:else if updates.checked}<p>No update is available.</p>{/if}
  {/if}
</section>

<style>
  .about { padding: clamp(16px, 4vw, 48px); }
  h2 { color: var(--text-heading); }
  a { color: var(--accent-strong); }
  .repository { color: var(--text-muted); overflow-wrap: anywhere; }
</style>
