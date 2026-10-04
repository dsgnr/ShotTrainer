<script lang="ts">
  let { category }: { category: string } = $props();
</script>

{#if category === "practice"}
  <svg viewBox="0 0 24 24" aria-hidden="true" width="16" height="16">
    <circle cx="12" cy="12" r="9" /><circle cx="12" cy="12" r="5" /><circle cx="12" cy="12" r="1" />
  </svg>
{:else if category === "sighter"}
  <svg viewBox="0 0 24 24" aria-hidden="true" width="16" height="16">
    <circle cx="12" cy="12" r="6" /><path d="M12 2v6M12 16v6M2 12h6M16 12h6" />
  </svg>
{:else if category === "match"}
  <svg viewBox="0 0 24 24" aria-hidden="true" width="16" height="16">
    <path d="M8 4h8v5a4 4 0 0 1-8 0zM8 6H5a3 3 0 0 0 3 4M16 6h3a3 3 0 0 1-3 4M12 13v4M9 20h6M10 17h4" />
  </svg>
{/if}

<style>
  svg { flex: none; fill: none; stroke: currentColor; stroke-width: 1.6; stroke-linecap: round; stroke-linejoin: round; }
</style>
