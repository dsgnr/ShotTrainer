<script lang="ts">
  import type { Snippet } from "svelte";

  interface Props {
    header: Snippet;
    status: Snippet;
    nav?: Snippet;
    camera?: Snippet;
    target?: Snippet;
    side?: Snippet;
  }

  let { header, status, nav, camera, target, side }: Props = $props();
</script>

<div class="shell">
  {#if nav}
    <nav class="nav" aria-label="Primary">{@render nav()}</nav>
  {/if}
  <header class="header">{@render header()}</header>
  <aside class="camera" aria-label="Camera">{@render camera?.()}</aside>
  <main class="target">{@render target?.()}</main>
  <aside class="side" aria-label="Session">{@render side?.()}</aside>
  <footer class="status">{@render status()}</footer>
</div>

<style>
  .shell {
    display: grid;
    grid-template-columns:
      auto
      minmax(248px, 320px)
      minmax(0, 1fr)
      minmax(260px, 340px);
    grid-template-rows: auto minmax(0, 1fr) auto;
    grid-template-areas:
      "nav header header header"
      "nav camera target side"
      "nav status status status";
    height: 100%;
    background: var(--bg);
  }

  .nav {
    grid-area: nav;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: var(--space-2);
    padding: var(--space-3) var(--space-2);
    background: var(--bg-sunken);
    border-right: 1px solid var(--divider);
  }

  .header {
    grid-area: header;
    border-bottom: 1px solid var(--divider);
    background: var(--bg-sunken);
  }

  .camera {
    grid-area: camera;
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
    padding: var(--space-3);
    border-right: 1px solid var(--divider);
    min-height: 0;
    overflow: auto;
  }

  .target {
    grid-area: target;
    display: flex;
    min-width: 0;
    min-height: 0;
  }

  .side {
    grid-area: side;
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
    padding: var(--space-3);
    border-left: 1px solid var(--divider);
    min-height: 0;
    overflow: auto;
  }

  .status {
    grid-area: status;
    border-top: 1px solid var(--divider);
    background: var(--bg-sunken);
  }

  /* When no nav rail is supplied the grid collapses its column cleanly. */
  .shell:not(:has(.nav)) {
    grid-template-columns:
      minmax(248px, 320px)
      minmax(0, 1fr)
      minmax(260px, 340px);
    grid-template-areas:
      "header header header"
      "camera target side"
      "status status status";
  }
</style>
