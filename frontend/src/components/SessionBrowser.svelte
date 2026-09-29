<script lang="ts">
  import Dropdown from "./Dropdown.svelte";
  import type { CommandSender } from "../lib/app/commands";
  import { filterSessions, scoreBadge, sessionMeta } from "../lib/sessions/rows";
  import { SESSION_CATEGORIES, categoryLabel } from "../lib/wire/categories";
  import type { WireSessionSummary } from "../lib/wire/types";

  interface Props {
    open: boolean;
    sessions: WireSessionSummary[];
    send: CommandSender;
    onopen: () => void;
    onnew: () => void;
    recording?: boolean;
  }

  let { open, sessions, send, onopen, onnew, recording = false }: Props = $props();

  let query = $state("");
  let categoryFilter = $state("");
  let selected = $state<number | null>(null);

  // Ask the controller to refresh the list each time the browser opens.
  $effect(() => {
    if (open) {
      void send({ type: "listSessions" });
    }
  });

  const matches = $derived(filterSessions(sessions, query, categoryFilter));
  const selectedSession = $derived(matches.find((s) => s.id === selected) ?? null);

  function openSession(): void {
    if (selected !== null) {
      void send({ type: "openSession", id: selected });
      onopen();
    }
  }

  function rename(): void {
    if (selectedSession === null) {
      return;
    }
    const name = window.prompt("Session name", selectedSession.name);
    if (name !== null) {
      void send({ type: "renameSession", id: selectedSession.id, name });
    }
  }

  function setCategory(): void {
    if (selectedSession === null) {
      return;
    }
    const next = window.prompt(
      `Category (${SESSION_CATEGORIES.join(", ")})`,
      selectedSession.category,
    );
    if (next !== null && (SESSION_CATEGORIES as readonly string[]).includes(next)) {
      void send({ type: "setSessionCategory", id: selectedSession.id, category: next });
    }
  }

  function remove(): void {
    if (selected !== null && window.confirm("Delete this session and all its trace data?")) {
      void send({ type: "deleteSession", id: selected });
      selected = null;
    }
  }

  function exportSession(): void {
    if (selectedSession === null) {
      return;
    }
    const dir = window.prompt("Export folder");
    if (dir !== null && dir !== "") {
      void send({ type: "exportSession", id: selectedSession.id, dir });
    }
  }
</script>

{#if open}
  <section class="sessions-page" aria-label="Sessions">
      <header><h2>Sessions</h2><button type="button" class="primary" disabled={recording} onclick={onnew}>New session</button></header>

      <div class="filters">
        <input type="search" placeholder="Search session names..." bind:value={query} />
        <Dropdown label="Filter by category" bind:value={categoryFilter}
          options={[{ value: "", label: "All categories" }, ...SESSION_CATEGORIES.map((value) => ({ value, label: categoryLabel(value) }))]} />
      </div>

      {#if matches.length === 0}
        <p class="empty">
          {sessions.length === 0 ? "No saved sessions yet." : "No sessions match your filter."}
        </p>
      {:else}
        <ul class="list" role="listbox" aria-label="Saved sessions">
          {#each matches as session (session.id)}
            <li
              role="option"
              tabindex="0"
              aria-selected={session.id === selected}
              class:selected={session.id === selected}
              onclick={() => (selected = session.id)}
              ondblclick={openSession}
              onkeydown={(event) => (event.key === "Enter" || event.key === " ") && (selected = session.id)}
            >
              <span class="info">
                <span class="title">{session.name || `Session #${session.id}`}</span>
                <span class="meta">{sessionMeta(session)}</span>
              </span>
              {#if scoreBadge(session) !== ""}
                <span class="score">{scoreBadge(session)}</span>
              {/if}
            </li>
          {/each}
        </ul>
      {/if}

      <div class="actions">
        <button type="button" disabled={selected === null} onclick={openSession}>Open</button>
        <button type="button" disabled={selected === null} onclick={rename}>Rename...</button>
        <button type="button" disabled={selected === null} onclick={setCategory}>Category...</button>
        <button type="button" disabled={selected === null} onclick={remove}>Delete</button>
        <button type="button" disabled={selected === null} onclick={exportSession}>Export CSV...</button>
      </div>
  </section>
{/if}

<style>
  .sessions-page {
    width: 100%; min-width: 0; min-height: 0;
    display: flex; flex-direction: column; gap: 16px;
    padding: clamp(16px, 4vw, 48px);
  }
  .actions { flex-wrap: wrap; flex: none; }
  .filters { flex-wrap: wrap; flex: none; }
  .list { min-height: 0; }

  header { display: flex; align-items: center; justify-content: space-between; gap: 16px; }

  h2 {
    margin: 0;
    color: var(--text-heading);
  }

  .filters {
    display: flex;
    gap: 8px;
  }

  .filters input {
    flex: 1;
  }

  input {
    padding: 6px 8px;
    color: var(--text);
    background: var(--panel-raised);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    font: inherit;
  }

  .list {
    flex: 1;
    margin: 0;
    padding: 0;
    list-style: none;
    overflow: auto;
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

  .info {
    display: flex;
    flex: 1;
    flex-direction: column;
  }

  .meta {
    color: var(--text-dim);
    font-size: 12px;
  }

  .score {
    color: var(--text-heading);
    font-variant-numeric: tabular-nums;
  }

  .empty {
    margin: 0;
    padding: 24px;
    color: var(--text-dim);
    text-align: center;
  }

  .actions {
    display: flex;
    align-items: center;
    gap: 8px;
  }

</style>
