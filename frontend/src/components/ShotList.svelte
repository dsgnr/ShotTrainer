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

{#if rows.length === 0}
  <p class="empty">No shots yet. Start a session and the microphone will pick up each one.</p>
{:else}
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
        <span class="number">#{row.number}</span>
        <span class="score">{row.score}</span>
        <span class="offset">{row.offset}</span>
      </li>
    {/each}
  </ul>
{/if}

<style>
  .empty {
    margin: 0;
    padding: 16px;
    color: var(--text-dim);
    text-align: center;
  }

  .shots {
    margin: 0;
    padding: 0;
    list-style: none;
    overflow: auto;
  }

  .shots:focus-visible {
    outline: 2px solid var(--focus);
    outline-offset: -2px;
  }

  li {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 8px 10px;
    border-radius: var(--radius);
    cursor: pointer;
  }

  li.selected {
    background: var(--panel-raised);
  }

  .number {
    width: 36px;
    color: var(--text-dim);
  }

  .score {
    min-width: 40px;
    text-align: center;
  }

  .offset {
    flex: 1;
    text-align: right;
    color: var(--text-dim);
  }
</style>
