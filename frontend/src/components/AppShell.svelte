<script lang="ts">
  import type { Snippet } from "svelte";

  interface Props {
    header: Snippet;
    status: Snippet;
    camera?: Snippet;
    target?: Snippet;
    side?: Snippet;
  }

  let { header, status, camera, target, side }: Props = $props();
</script>

<div class="shell">
  <header class="header">{@render header()}</header>
  <aside class="camera" aria-label="Camera">{@render camera?.()}</aside>
  <main class="target">{@render target?.()}</main>
  <aside class="side" aria-label="Session">{@render side?.()}</aside>
  <footer class="status">{@render status()}</footer>
</div>

<style>
  .shell {
    display: grid;
    grid-template-columns: minmax(240px, 320px) minmax(0, 1fr) minmax(240px, 340px);
    grid-template-rows: auto minmax(0, 1fr) auto;
    grid-template-areas:
      "header header header"
      "camera target side"
      "status status status";
    height: 100%;
  }

  .header {
    grid-area: header;
    border-bottom: 1px solid var(--border);
  }

  .camera {
    grid-area: camera;
    display: flex;
    flex-direction: column;
    gap: 12px;
    padding: 12px;
    border-right: 1px solid var(--border);
    min-height: 0;
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
    gap: 12px;
    padding: 12px;
    border-left: 1px solid var(--border);
    min-height: 0;
    overflow: auto;
  }

  .status {
    grid-area: status;
    border-top: 1px solid var(--border);
    background: var(--bg-sunken);
  }
</style>
