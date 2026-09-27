<script lang="ts">
  import type { Snippet } from "svelte";

  interface Props {
    header?: Snippet;
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
    {@render header?.()}
    <div class="pane-controls">
      <button type="button" aria-expanded={!shotsCollapsed} aria-controls="session-shots"
        aria-label={shotsCollapsed ? "Show shots" : "Hide shots"}
        title={shotsCollapsed ? "Show shots" : "Hide shots"}
        onclick={() => (shotsCollapsed = !shotsCollapsed)}>
        <svg viewBox="0 0 24 24" aria-hidden="true" width="20" height="20">
          <rect x="3" y="4" width="18" height="16" rx="2" />
          <path d="M9 4v16" />
          <path d={shotsCollapsed ? "M13 9l3 3-3 3" : "M16 9l-3 3 3 3"} />
        </svg>
      </button>
      <button type="button" aria-expanded={!sessionCollapsed} aria-controls="session-controls"
        aria-label={sessionCollapsed ? "Show session" : "Hide session"}
        title={sessionCollapsed ? "Show session" : "Hide session"}
        onclick={() => (sessionCollapsed = !sessionCollapsed)}>
        <svg viewBox="0 0 24 24" aria-hidden="true" width="20" height="20">
          <rect x="3" y="4" width="18" height="16" rx="2" />
          <path d="M15 4v16" />
          <path d={sessionCollapsed ? "M11 9l-3 3 3 3" : "M8 9l3 3-3 3"} />
        </svg>
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
    transition: grid-template-columns 160ms ease-out, grid-template-rows 160ms ease-out;
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
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 32px;
    height: 32px;
    padding: 0;
  }

  .pane-controls svg {
    fill: none;
    stroke: currentColor;
    stroke-width: 1.6;
    stroke-linecap: round;
    stroke-linejoin: round;
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

  @media (max-width: 650px) {
    .shell, .shell:not(:has(.nav)) {
      grid-template-columns: auto minmax(0, 1fr);
      grid-template-rows: auto minmax(240px, 1fr) minmax(0, 0.45fr) minmax(0, 0.45fr) auto;
      grid-template-areas: "nav header" "nav target" "nav shots" "nav side" "nav status";
    }
    .shell:not(:has(.nav)) { grid-template-columns: 0 minmax(0, 1fr); }
    .shell.shots-collapsed {
      grid-template-rows: auto minmax(240px, 1fr) 0 minmax(0, 0.65fr) auto;
    }
    .shell.session-collapsed {
      grid-template-rows: auto minmax(240px, 1fr) minmax(0, 0.65fr) 0 auto;
    }
    .shell.shots-collapsed.session-collapsed {
      grid-template-rows: auto minmax(240px, 1fr) 0 0 auto;
    }
    .shots { flex-direction: row; padding: var(--space-2); gap: var(--space-2); }
    .shots :global(.overview) { width: 100px; }
  }

  @media (prefers-reduced-motion: reduce) {
    .shell { transition: none; }
  }
</style>
