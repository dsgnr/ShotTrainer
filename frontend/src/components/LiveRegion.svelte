<script lang="ts">
  import type { Announcer } from "../lib/app/announcer.svelte";

  interface Props {
    announcer: Announcer;
  }

  let { announcer }: Props = $props();
</script>

<div class="visually-hidden">
  <div aria-live="polite" aria-atomic="true">{announcer.regions[0]}</div>
  <div aria-live="polite" aria-atomic="true">{announcer.regions[1]}</div>
</div>
