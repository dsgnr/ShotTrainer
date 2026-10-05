<script lang="ts">
  import type { CommandSender } from "../lib/app/commands";
  import { shotRows, stepSelection } from "../lib/shots/rows";
  import type { WireShot } from "../lib/wire/types";

  interface Props {
    shots: WireShot[];
    selected: number | null;
    send: CommandSender;
  }

  let { shots, selected, send }: Props = $props();

  const rows = $derived(shotRows(shots));

  function select(index: number): void {
    void send({ type: "selectShot", index });
  }

  function onRowKeydown(event: KeyboardEvent, index: number): void {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      select(index);
    }
  }

  function onKeydown(event: KeyboardEvent): void {
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      const next = stepSelection(selected, event.key === "ArrowDown" ? 1 : -1, shots.length);
      if (next !== null) {
        event.preventDefault();
        select(next);
      }
    } else if ((event.key === "Delete" || event.key === "Backspace") && selected !== null) {
      event.preventDefault();
      void send({ type: "deleteShot", index: selected });
    }
  }
</script>

<section class="shot-list" aria-label="Shots">
  <header class="head">
    <h3 class="panel-title">Shot list</h3>
    {#if rows.length > 0}
      <span class="count num">{rows.length}</span>
    {/if}
  </header>

  {#if rows.length === 0}
    <p class="empty">No shots yet. Start a session and the microphone will pick up each one.</p>
  {:else}
    <div class="columns" aria-hidden="true">
      <span>No</span>
      <span class="right">Score</span>
      <span class="right">Offset</span>
    </div>
    <!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
    <ul class="shots" role="listbox" aria-label="Shots" tabindex="0" onkeydown={onKeydown}>
      {#each rows as row, i (i)}
        <li
          role="option"
          aria-selected={i === selected}
          class:selected={i === selected}
          onclick={() => select(i)}
          onkeydown={(event) => onRowKeydown(event, i)}
        >
          <span class="number num">{row.number}</span>
          <span class="score num" class:scored={row.score !== "-"}>{row.score}</span>
          <span class="offset num">{row.offset}</span>
        </li>
      {/each}
    </ul>
  {/if}
</section>

<style>
  .shot-list {
    display: flex;
    flex-direction: column;
    min-height: 0;
    background: var(--panel);
    border: 1px solid var(--divider);
    border-radius: var(--radius);
  }

  .head {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    padding: var(--space-3) var(--space-4);
    border-bottom: 1px solid var(--divider);
  }

  .count {
    margin-left: auto;
    color: var(--text-muted);
    font-size: var(--text-xs);
  }

  .empty {
    margin: 0;
    padding: var(--space-5) var(--space-4);
    color: var(--text-muted);
    text-align: center;
    font-size: var(--text-sm);
  }

  .columns,
  li {
    display: grid;
    grid-template-columns: 2.5rem 1fr 1fr;
    gap: var(--space-3);
    align-items: center;
  }

  .columns {
    padding: var(--space-2) var(--space-4);
    color: var(--text-muted);
    font-size: var(--text-xs);
    letter-spacing: var(--tracking-caption);
    text-transform: uppercase;
    border-bottom: 1px solid var(--divider);
  }

  .right {
    text-align: right;
  }

  .shots {
    margin: 0;
    padding: var(--space-1) 0;
    list-style: none;
    overflow: auto;
    min-height: 0;
  }

  .shots:focus-visible {
    outline: 2px solid var(--focus);
    outline-offset: -2px;
  }

  li {
    position: relative;
    padding: 5px var(--space-4);
    cursor: pointer;
    transition: background-color 100ms ease-out;
  }

  li:hover {
    background: var(--surface-hover);
  }

  li.selected {
    background: var(--panel-raised);
  }

  /* A thin accent edge marks the selected row without recolouring it. */
  li.selected::before {
    content: "";
    position: absolute;
    inset: 0 auto 0 0;
    width: 2px;
    background: var(--accent-strong);
  }

  .number {
    color: var(--text-muted);
  }

  .score {
    text-align: right;
    color: var(--text-dim);
  }

  .score.scored {
    color: var(--accent-strong);
  }

  .offset {
    text-align: right;
    color: var(--text-dim);
    font-size: var(--text-sm);
  }
</style>
