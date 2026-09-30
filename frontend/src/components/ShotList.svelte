<script lang="ts">
  import { seriesIndex } from "../lib/shots/series";
  import type { CommandSender } from "../lib/app/commands";
  import { shotRows, stepSelection } from "../lib/shots/rows";
  import type { WireShot } from "../lib/wire/types";

  interface Props {
    shots: WireShot[];
    selected: number | null;
    send: CommandSender;
    shotsPerSeries?: number;
  }

  let { shots, selected, send, shotsPerSeries = 10 }: Props = $props();

  let list = $state<HTMLUListElement>();
  let keyboardNavigation = $state(false);

  const rows = $derived(shotRows(shots));

  $effect(() => {
    if (selected !== null && list) {
      const row = list.querySelector<HTMLElement>(`[data-index="${selected}"]`);
      row?.scrollIntoView?.({ block: "nearest" });
      if (row && list.contains(document.activeElement)) {
        row.focus({ preventScroll: true });
      }
    }
  });

  function select(index: number): void {
    void send({ type: "selectShot", index });
  }

  function onRowKeydown(event: KeyboardEvent, index: number): void {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      event.stopPropagation();
      select(index);
    }
  }

  function onKeydown(event: KeyboardEvent): void {
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      const next = stepSelection(selected, event.key === "ArrowDown" ? 1 : -1, shots.length);
      if (next !== null) {
        event.preventDefault();
        event.stopPropagation();
        keyboardNavigation = true;
        select(next);
      }
    } else if ((event.key === "Delete" || event.key === "Backspace") && selected !== null) {
      event.preventDefault();
      event.stopPropagation();
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
    <ul bind:this={list} class="shots" class:keyboard-navigation={keyboardNavigation} role="listbox" aria-label="Shots" tabindex="-1" onkeydown={onKeydown} onpointermove={() => keyboardNavigation = false}>
      {#each rows as row, i (i)}
        {@const series = seriesIndex(shots[i]!, i, shotsPerSeries)}
        {#if i === 0 || series !== seriesIndex(shots[i - 1]!, i - 1, shotsPerSeries)}
          <li class="series" role="presentation">Series {series + 1}</li>
        {/if}
        <li
          data-index={i}
          role="option"
          tabindex={i === (selected ?? 0) ? 0 : -1}
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
    min-width: 0;
    overflow: hidden;
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
    overflow: auto;
    min-height: 0;
    text-align: center;
    font-size: var(--text-sm);
  }

  .columns,
  li {
    display: grid;
    grid-template-columns: 1.8rem 2.8rem minmax(0, 1fr);
    gap: var(--space-2);
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
    overscroll-behavior: contain;
    scrollbar-gutter: stable;
  }

  .series { display: block; padding: 8px var(--space-4) 4px; border-top: 1px solid var(--divider); color: var(--text-muted); font-size: var(--text-xs); cursor: default; }
  .series:first-child { border-top: 0; }

  .shots:focus-visible {
    outline: none;
  }

  li {
    position: relative;
    padding: 5px var(--space-4);
    cursor: pointer;
    transition: background-color 100ms ease-out;
  }

  .shots:not(.keyboard-navigation) li:hover:not(.selected) {
    background: var(--surface-hover);
  }

  li.selected {
    background: var(--panel-raised);
  }

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
