<script lang="ts">
  import { onMount } from "svelte";
  import { getVersion } from "@tauri-apps/api/app";
  import { isTauri } from "@tauri-apps/api/core";
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
</section>

<style>
  .about { padding: clamp(16px, 4vw, 48px); }
  h2 { color: var(--text-heading); }
  a { color: var(--accent-strong); }
  .repository { color: var(--text-muted); overflow-wrap: anywhere; }
</style>
