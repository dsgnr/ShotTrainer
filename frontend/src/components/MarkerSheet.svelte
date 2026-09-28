<script lang="ts">
  import { focusTrap } from "../lib/app/focus-trap";
  import { shotRows } from "../lib/shots/rows";
  import type { WireSessionState, WireShot } from "../lib/wire/types";

  interface Props {
    open: boolean;
    shots: WireShot[];
    session: WireSessionState;
    totalScore: number | null;
    onclose: () => void;
  }

  let { open, shots, session, totalScore, onclose }: Props = $props();

  const rows = $derived(shotRows(shots));
  const title = $derived(session.kind === "idle" ? "Shot sheet" : `Session ${sessionId(session)}`);

  function sessionId(state: WireSessionState): number | string {
    return state.kind === "idle" ? "" : state.sessionId;
  }

  function print(): void {
    window.print();
  }
</script>

{#if open}
  <!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
  <div
    class="backdrop"
    role="presentation"
    onclick={onclose}
    onkeydown={(event) => event.key === "Escape" && onclose()}
  >
    <!-- svelte-ignore a11y_click_events_have_key_events -->
    <div
      class="sheet"
      role="dialog"
      aria-modal="true"
      aria-label="Marker sheet"
      tabindex="-1"
      use:focusTrap
      onclick={(event) => event.stopPropagation()}
    >
      <header>
        <h2>{title}</h2>
        {#if totalScore !== null && totalScore > 0}
          <span class="total">{totalScore} pts</span>
        {/if}
      </header>

      <!-- svelte-ignore a11y_no_noninteractive_tabindex -->
      <div class="sheet-body" role="region" aria-label="Shot results" tabindex="0">
      <table>
        <thead>
          <tr>
            <th scope="col">Shot</th>
            <th scope="col">Score</th>
            <th scope="col">Offset</th>
          </tr>
        </thead>
        <tbody>
          {#each rows as row (row.number)}
            <tr>
              <td>#{row.number}</td>
              <td>{row.score}</td>
              <td>{row.offset}</td>
            </tr>
          {/each}
        </tbody>
      </table>
      </div>

      <div class="actions">
        <button type="button" onclick={onclose}>Close</button>
        <button type="button" class="primary" onclick={print}>Print</button>
      </div>
    </div>
  </div>
{/if}

<style>
  .backdrop {
    position: fixed;
    inset: 0;
    display: grid;
    place-items: center;
    background: rgba(0, 0, 0, 0.5);
    z-index: 10;
  }

  .sheet {
    width: min(520px, 92vw);
    max-height: calc(100dvh - 32px);
    display: flex;
    flex-direction: column;
    overflow: hidden;
    padding: 20px 24px;
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: var(--radius);
  }

  .sheet-body {
    min-height: 0;
    max-height: 352px;
    overflow: auto;
  }

  header {
    flex: none;
    display: flex;
    align-items: baseline;
    justify-content: space-between;
  }

  h2 {
    margin: 0 0 12px;
    color: var(--text-heading);
  }

  .total {
    color: var(--text-heading);
    font-variant-numeric: tabular-nums;
  }

  table {
    width: 100%;
    border-collapse: collapse;
  }

  th,
  th {
    position: sticky;
    top: 0;
    background: var(--panel);
  }

  tbody tr {
    height: 32px;
  }

  td {
    padding: 6px 8px;
    text-align: left;
    border-bottom: 1px solid var(--border);
  }

  th {
    position: sticky;
    top: 0;
    background: var(--panel);
  }

  tbody tr {
    height: 32px;
  }

  td {
    font-variant-numeric: tabular-nums;
  }

  .actions {
    flex: none;
    display: flex;
    justify-content: flex-end;
    gap: 8px;
    margin-top: 16px;
  }
  @media print {
    .sheet,
    .sheet-body {
      max-height: none;
      overflow: visible;
    }

    th {
      position: static;
    }

    .actions {
      display: none;
    }
  }
</style>
