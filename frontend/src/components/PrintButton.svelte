<script lang="ts">
  let { onprint }: { onprint: () => void } = $props();
</script>

<button type="button" class="print tool-button" title="Print shot sheet" aria-label="Print shot sheet" onclick={onprint}>
  <svg viewBox="0 0 24 24" aria-hidden="true" width="20" height="20">
    <path d="M7 8V3h10v5M7 17H4V8h16v9h-3" />
    <rect x="7" y="14" width="10" height="7" rx="1" />
    <path d="M16 11h1" />
  </svg>
</button>

<style>
  .print { flex: none; width: 36px; padding: 0; color: var(--text-muted); background: transparent; border-color: transparent; }
  .print:hover { color: var(--text); background: var(--surface-hover); }
  svg { fill: none; stroke: currentColor; stroke-width: 1.6; stroke-linecap: round; stroke-linejoin: round; }
</style>
