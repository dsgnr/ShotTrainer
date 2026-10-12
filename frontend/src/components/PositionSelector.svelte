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
          <path class="ground" d="M6 82H114" />
          {#if position === "prone"}
            <path class="limb" d="M10 79L31 76M10 74L31 73" />
            <path class="torso" d="M31 75L58 70" />
            <path class="limb" d="M58 70L68 79L88 68" />
            <circle class="body" cx="68" cy="63" r="7" />
            <path class="rifle" d="M62 66L112 68" />
          {:else if position === "standing"}
            <path class="limb" d="M55 50L46 81M55 50L65 81" />
            <path class="torso" d="M55 50L52 28" />
            <circle class="body" cx="54" cy="17" r="6.5" />
            <path class="limb" d="M54 31L68 44L82 27M52 30L44 40L60 27" />
            <path class="rifle" d="M54 27L112 23" />
          {:else}
            <path class="limb" d="M48 64L36 79L22 80M48 64L70 62L70 80L79 80" />
            <path class="torso" d="M48 64L50 36" />
            <circle class="body" cx="52" cy="25" r="6.5" />
            <path class="limb" d="M52 38L64 52L82 35M50 38L42 48L60 36" />
            <path class="rifle" d="M52 36L112 32" />
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
  .body { fill: currentColor; }
  .limb, .torso, .rifle { fill: none; stroke: currentColor; stroke-linecap: round; stroke-linejoin: round; }
  .limb { stroke-width: 6; }
  .torso { stroke-width: 10; }
  .rifle { stroke-width: 3; }
  .ground { fill: none; stroke: currentColor; opacity: 0.2; stroke-width: 1; }
  span { font-size: var(--text-xs); }
</style>
