<script lang="ts">
  import type { Snippet } from "svelte";

  interface Props {
    header: Snippet;
    status: Snippet;
    nav?: Snippet;
    shots?: Snippet;
    target?: Snippet;
    side?: Snippet;
  }

  let { header, status, nav, shots, target, side }: Props = $props();
  let shotsCollapsed = $state(false);
  let sessionCollapsed = $state(false);
</script>

<div class="shell" class:shots-collapsed={shotsCollapsed} class:session-collapsed={sessionCollapsed}
  style:--shots-width={shotsCollapsed ? "0px" : "280px"}
  style:--session-width={sessionCollapsed ? "0px" : "300px"}>
  {#if nav}
    <nav class="nav" aria-label="Primary">{@render nav()}</nav>
  {/if}
  <header class="header">
    {@render header()}
    <div class="pane-controls">
      <button aria-expanded={!shotsCollapsed} aria-controls="session-shots"
        onclick={() => (shotsCollapsed = !shotsCollapsed)}>
        {shotsCollapsed ? "Show shots" : "Hide shots"}
      </button>
      <button aria-expanded={!sessionCollapsed} aria-controls="session-controls"
        onclick={() => (sessionCollapsed = !sessionCollapsed)}>
        {sessionCollapsed ? "Show session" : "Hide session"}
      </button>
    </div>
  </header>
  <aside id="session-shots" class="shots" hidden={shotsCollapsed} aria-label="Session shots">{@render shots?.()}</aside>
  <main class="target">{@render target?.()}</main>
  <aside id="session-controls" class="side" hidden={sessionCollapsed} aria-label="Session">{@render side?.()}</aside>
  <footer class="status">{@render status()}</footer>
</div>

<style>
  .shell {
    display: grid;
    grid-template-columns:
      auto
      var(--shots-width)
      minmax(0, 1fr)
      var(--session-width);
    grid-template-rows: auto minmax(0, 1fr) auto;
    grid-template-areas:
      "nav header header header"
      "nav shots target side"
      "nav status status status";
    height: 100%;
    min-height: 0;
    overflow: hidden;
    transition: grid-template-columns 160ms ease-out;
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
    min-width: 0;
    border-bottom: 1px solid var(--divider);
    background: var(--bg-sunken);
  }

  .shots {
    grid-area: shots;
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
    padding: var(--space-3);
    border-right: 1px solid var(--divider);
    min-height: 0;
    overflow: hidden;
    min-width: 0;
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

  .shots[hidden], .side[hidden] {
    display: none;
  }

  .shots :global(.shot-list) {
    flex: 1;
  }

  .pane-controls button {
    min-height: 32px;
    font-size: var(--text-sm);
  }

  .pane-controls {
    display: flex;
    justify-content: space-between;
    padding: var(--space-2) var(--space-3);
  }

  .status {
    grid-area: status;
    border-top: 1px solid var(--divider);
    background: var(--bg-sunken);
  }

  /* When no nav rail is supplied the grid collapses its column cleanly. */
  .shell:not(:has(.nav)) {
    grid-template-columns:
      var(--shots-width)
      minmax(0, 1fr)
      var(--session-width);
    grid-template-areas:
      "header header header"
      "shots target side"
      "status status status";
  }
  @media (max-width: 1050px) {
    .shell, .shell:not(:has(.nav)) {
      grid-template-columns: auto minmax(0, 1fr) minmax(0, 1fr);
      grid-template-rows: auto minmax(220px, 1fr) minmax(0, 0.7fr) auto;
      grid-template-areas:
        "nav header header"
        "nav target target"
        "nav shots side"
        "nav status status";
    }
    .shell:not(:has(.nav)) { grid-template-columns: 0 minmax(0, 1fr) minmax(0, 1fr); }
    .shell.shots-collapsed .side, .shell.session-collapsed .shots {
      grid-column: 2 / -1;
    }
    .shell.shots-collapsed.session-collapsed {
      grid-template-rows: auto minmax(220px, 1fr) 0 auto;
    }
    .shots, .side { border-top: 1px solid var(--divider); }
  }

  @media (prefers-reduced-motion: reduce) {
    .shell { transition: none; }
  }
</style>
