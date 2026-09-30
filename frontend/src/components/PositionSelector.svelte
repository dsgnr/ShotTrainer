<script lang="ts">
  import type { WirePreferences } from "../lib/wire/types";
  let { value = $bindable() }: { value: WirePreferences["sessionPosition"] } = $props();
  const positions = ["prone", "standing", "kneeling"] as const;
</script>
<fieldset class="positions">
  <legend>Shooting position</legend>
  <div class="choices">
    {#each positions as position}
      <label class:selected={value === position}>
        <input type="radio" name="shooting-position" value={position} bind:group={value} />
        <svg viewBox="0 0 120 88" aria-hidden="true">
          <path class="ground" d="M8 82H112" />
          {#if position === "prone"}
            <path class="body" d="M8 69l20-6 16-6 19-7q7-2 12 3l-7 10-20 3-16 4-20 5H7q-3-3 1-6Zm22 0 17-3 12 4-6 5-17-1-19 6H7q-3-3 1-5Z" />
            <path class="body" d="M68 53q5-1 7 3l5 10 12-12 4 3-12 16q-3 3-6 0L66 61Zm8 1 16-3 4-3 4 3-5 6-16 4Z" />
            <path class="body" d="M73 43q1-7 8-7l7 4-1 6-5 5-7-2Z" />
            <path class="cap" d="M73 40q1-8 9-6l7 4 6 1v3H74Z" />
            <path class="rifle" d="M84 48h13v-2h15v3h-14v3H87l-4 4-4-2 3-5Z" />
            <path class="detail" d="m30 64 14-3m18-6 6 7m20-11h6" />
          {:else if position === "standing"}
            <path class="body" d="M41 29q6-4 12 1l5 15-5 13-16-1 1-17Z" />
            <path class="body" d="m38 54 9 1-6 17-2 7 6 1v3H29v-4l4-10Zm8 1 8-1 5 17 5 7h6v5H56l-5-10Z" />
            <path class="body" d="m52 30 9 13 9-13 5 3-11 20q-3 4-6 0L46 37Zm-8 1 19-3 7-4 4 4-8 7-19 6Z" />
            <path class="body" d="M43 15q0-8 8-8l7 5-1 7-5 7-7-3Z" />
            <path class="cap" d="M42 13q1-10 10-8l7 5 7 2v3H43Z" />
            <path class="rifle" d="M60 24h24v-2h27v3H86v3H64l-6 6-5-3 5-6Z" />
            <path class="detail" d="m41 46 11 2m-8 10 8-1m15-31h11" />
          {:else}
            <path class="body" d="M45 36q7-4 13 1l5 19-8 9-17-3 3-14Z" />
            <path class="body" d="m42 59 11 4-16 12 12 3 3 5H26q-4-2-2-6Zm13 0 20 4q5 1 5 6l-1 10h9v4H68V71L50 70Z" />
            <path class="body" d="m56 36 9 14 12-12 4 3-14 18q-3 3-6-1L49 42Zm-8 1 20-3 9-5 4 4-10 8-20 5Z" />
            <path class="body" d="M48 21q0-8 8-8l7 5-1 7-5 7-7-3Z" />
            <path class="cap" d="M47 19q1-10 10-8l7 5 7 2v3H48Z" />
            <path class="rifle" d="M66 30h22v-2h24v3H90v3H70l-6 6-5-3 5-6Z" />
            <path class="detail" d="m43 54 14 3m-18 18 8-6m26-37h10" />
          {/if}
        </svg>
        <span>{position[0]!.toUpperCase() + position.slice(1)}</span>
      </label>
    {/each}
  </div>
</fieldset>
<style>
  .positions { border: 0; padding: 0; margin: 8px 0; min-width: 0; }
  legend { margin-bottom: 8px; }
  .choices { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 6px; }
  label { display: grid; justify-items: center; gap: 4px; padding: 6px 2px; border: 1px solid var(--border); border-radius: var(--radius-control); cursor: pointer; color: var(--text-muted); }
  label.selected { color: var(--accent-strong); border-color: var(--accent-strong); background: var(--panel-raised); }
  label:focus-within { outline: 2px solid var(--accent-strong); outline-offset: 2px; }
  input { position: absolute; opacity: 0; width: 1px; height: 1px; }
  svg { width: 100%; max-width: 120px; height: 72px; overflow: visible; }
  .body, .rifle { fill: currentColor; }
  .cap { fill: currentColor; opacity: 0.8; }
  .detail { fill: none; stroke: var(--panel); stroke-width: 1.2; stroke-linecap: round; opacity: 0.65; }
  .ground { fill: none; stroke: currentColor; opacity: 0.2; stroke-width: 1; }
  span { font-size: var(--text-xs); }
</style>
