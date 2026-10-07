<script lang="ts">
  import { untrack } from "svelte";
  import type { CommandSender } from "../lib/app/commands";
  import { ROW_HEIGHT, SERIES_HEIGHT, itemHeight, layoutShots, visibleRange } from "../lib/shots/layout";
  import { shotRows, stepSelection } from "../lib/shots/rows";
  import type { WireShot } from "../lib/wire/types";

  /** Assumed viewport height before the list has been measured. */
  const DEFAULT_VIEWPORT = 20 * ROW_HEIGHT;

  interface Props {
    shots: WireShot[];
    selected: number | null;
    send: CommandSender;
    shotsPerSeries?: number;
    showOffsets?: boolean;
  }

  let { shots, selected, send, shotsPerSeries = 10, showOffsets = true }: Props = $props();

  let list = $state<HTMLDivElement>();
  let keyboardNavigation = $state(false);
  let scrollTop = $state(0);
  let viewport = $state(0);

  const rows = $derived(shotRows(shots));
  const layout = $derived(layoutShots(shots, shotsPerSeries));
  const range = $derived(visibleRange(layout.items, scrollTop, viewport || DEFAULT_VIEWPORT));
  const visible = $derived(layout.items.slice(range.start, range.end));
  // Padding stands in for the rows that are not rendered, so the scroll height is the full list.
  const padTop = $derived(layout.items[range.start]?.top ?? 0);
  const padBottom = $derived.by(() => {
    const last = layout.items[range.end - 1];
    return last ? layout.height - last.top - itemHeight(last) : 0;
  });
  // Only one row is tabbable, so it has to be one that is rendered.
  const tabStop = $derived.by(() => {
    const indexes = visible.flatMap(item => (item.kind === "shot" ? [item.index] : []));
    return selected !== null && indexes.includes(selected) ? selected : (indexes[0] ?? 0);
  });

  // Scrolling moves the rendered rows, so the selected row can be missing from the DOM.
  let focusWithin = false;
  let pendingFocus: number | null = null;

  function ensureVisible(index: number): void {
    const top = layout.shotTops[index];
    if (top === undefined || !list) return;
    const height = list.clientHeight || DEFAULT_VIEWPORT;
    let next = scrollTop;
    if (top < next) next = top;
    else if (top + ROW_HEIGHT > next + height) next = top + ROW_HEIGHT - height;
    next = Math.max(0, next);
    if (next !== scrollTop) {
      list.scrollTop = next;
      scrollTop = next;
    }
  }

  function focusRow(index: number): boolean {
    const row = list?.querySelector<HTMLElement>(`[data-index="${index}"]`);
    row?.focus({ preventScroll: true });
    return !!row;
  }

  // Deriveds only notify when the value changes, so a new `shots` array of the same
  // length, or a repeated selection, does not move the scroll position.
  const count = $derived(shots.length);
  const selectedIndex = $derived(selected);

  $effect(() => {
    const index = selectedIndex;
    if (index === null || !list) return;
    untrack(() => {
      ensureVisible(index);
      if (focusWithin && !focusRow(index)) pendingFocus = index;
    });
  });

  // The window moves after the scroll offset changes, so focus waits for the new rows.
  $effect(() => {
    void visible;
    if (pendingFocus !== null && focusRow(pendingFocus)) pendingFocus = null;
  });

  // Follow new shots as they arrive.
  $effect(() => {
    const last = count - 1;
    if (last >= 0 && list) untrack(() => ensureVisible(last));
  });

  $effect(() => {
    const element = list;
    if (!element || typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(() => (viewport = element.clientHeight));
    observer.observe(element);
    return () => observer.disconnect();
  });

  function onScroll(): void {
    if (!list) return;
    scrollTop = list.scrollTop;
    viewport = list.clientHeight;
  }

  function onFocusOut(event: FocusEvent): void {
    if (!list?.contains(event.relatedTarget as Node | null)) focusWithin = false;
  }

  function select(index: number): void {
    void send({ type: "selectShot", index });
  }

  function onRowKeydown(event: KeyboardEvent, index: number): void {
    if (event.key === "Enter") {
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

<section class="shot-list" class:hide-offsets={!showOffsets} aria-label="Shots">
  <header class="head">
    <h3 class="panel-title">Shot list</h3>
    {#if shots.length > 0}
      <span class="count num">{shots.length}</span>
    {/if}
  </header>

  {#if shots.length === 0}
    <p class="empty">No shots yet. Start a session and the microphone will pick up each one.</p>
  {:else}
    <div class="columns" aria-hidden="true">
      <span>No</span>
      <span class="right">Score</span>
      {#if showOffsets}<span class="right">Offset</span>{/if}
    </div>
    <!-- The scroller is separate from the list because a flex item can shrink its content but not its padding. -->
    <div
      bind:this={list}
      class="scroller"
      role="presentation"
      onscroll={onScroll}
      onfocusin={() => focusWithin = true}
      onfocusout={onFocusOut}
    >
      <!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
      <ul
        class="shots"
        class:keyboard-navigation={keyboardNavigation}
        role="listbox"
        aria-label="Shots"
        tabindex="-1"
        style:padding-top="{padTop}px"
        style:padding-bottom="{padBottom}px"
        style:--row-height="{ROW_HEIGHT}px"
        style:--series-height="{SERIES_HEIGHT}px"
        onkeydown={onKeydown}
        onpointermove={() => keyboardNavigation = false}
      >
        {#each visible as item (`${item.kind}${item.index}`)}
          {#if item.kind === "series"}
            <li class="series" class:first={item.index === 0} role="presentation">Series {item.series + 1}</li>
          {:else}
            {@const i = item.index}
            {@const row = rows[i]!}
            <li
              data-index={i}
              role="option"
              aria-setsize={shots.length}
              aria-posinset={i + 1}
              tabindex={i === tabStop ? 0 : -1}
              aria-selected={i === selected}
              class:selected={i === selected}
              onclick={() => select(i)}
              onkeydown={(event) => onRowKeydown(event, i)}
            >
              <span class="number num">{row.number}</span>
              <span class="score num" class:scored={row.score !== "-"}>{row.score}</span>
              {#if showOffsets}
                <span class="offset num">
                  <span>{row.offset}</span>
                  {#if row.centreDirection !== null}
                    <svg viewBox="0 0 20 20" width="14" height="14" role="img" aria-label="Towards target centre"
                      style:transform={`rotate(${row.centreDirection}deg)`}>
                      <path d="M10 16V4M5 9l5-5 5 5" />
                    </svg>
                  {/if}
                </span>
              {/if}
            </li>
          {/if}
        {/each}
      </ul>
    </div>
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

  .hide-offsets .columns, .hide-offsets li { grid-template-columns: 1.8rem minmax(0, 1fr); }

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

  .scroller {
    min-height: 0;
    overflow: auto;
    overscroll-behavior: contain;
    scrollbar-gutter: stable;
  }

  .shots {
    margin: 0;
    padding: 0;
    list-style: none;
  }

  .series {
    display: flex;
    align-items: flex-end;
    box-sizing: border-box;
    height: var(--series-height);
    padding: 0 var(--space-4) 4px;
    border-top: 1px solid var(--divider);
    color: var(--text-muted);
    font-size: var(--text-xs);
    cursor: default;
  }
  .series.first { border-top: 0; }

  .shots:focus-visible {
    outline: none;
  }

  li {
    position: relative;
    box-sizing: border-box;
    height: var(--row-height);
    padding: 0 var(--space-4);
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
    display: flex;
    justify-content: flex-end;
    align-items: center;
    gap: 4px;
    text-align: right;
    color: var(--text-dim);
    font-size: var(--text-sm);
  }
  .offset svg { flex: none; fill: none; stroke: currentColor; stroke-width: 1.6; stroke-linecap: round; stroke-linejoin: round; }
</style>
