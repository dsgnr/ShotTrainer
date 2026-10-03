<script lang="ts">
  import { tick } from "svelte";
  import { shotRows } from "../lib/shots/rows";
  import type { WireSessionState, WireShot } from "../lib/wire/types";

  interface Props {
    shots: WireShot[];
    session: WireSessionState;
    totalScore: number | null;
  }
  let { shots, session, totalScore }: Props = $props();
  const rows = $derived(shotRows(shots));
  const title = $derived(session.kind === "idle" ? "Shot sheet" : `Session ${session.sessionId}`);
  let printError = $state<string | null>(null);

  export async function print(): Promise<void> {
    printError = null;
    try {
      await tick();
      await window.print();
    } catch (error) {
      printError = `Could not print the shot sheet: ${String(error)}`;
    }
  }
</script>

{#if printError}<p class="print-error" role="alert">{printError}</p>{/if}
<section id="print-sheet" aria-label="Shot sheet">
  <header>
    <h1>{title}</h1>
    {#if totalScore !== null && totalScore > 0}<span>{totalScore} pts</span>{/if}
  </header>
  <table>
    <thead><tr><th scope="col">Shot</th><th scope="col">Score</th><th scope="col">Offset</th></tr></thead>
    <tbody>
      {#each rows as row (row.number)}
        <tr><td>#{row.number}</td><td>{row.score}</td><td>{row.offset}</td></tr>
      {/each}
    </tbody>
  </table>
</section>

<style>
  #print-sheet { display: none; }
  .print-error { position: fixed; bottom: 40px; right: 16px; z-index: 20; padding: 12px; background: var(--panel-raised); border: 1px solid var(--border); border-radius: var(--radius); }
  @media print {
    :global(#app > :not(#print-sheet)) { display: none !important; }
    :global(html), :global(body), :global(#app) { height: auto; overflow: visible; background: white; }
    #print-sheet { display: block; color: black; background: white; padding: 16px; }
    header { display: flex; align-items: baseline; justify-content: space-between; }
    h1 { font-size: 20px; }
    table { width: 100%; border-collapse: collapse; }
    th, td { padding: 6px 8px; text-align: left; border-bottom: 1px solid #ccc; }
    thead { display: table-header-group; }
    tr { break-inside: avoid; }
  }
</style>
