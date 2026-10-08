<script lang="ts">
  import type { CommandSender } from "../lib/app/commands";
  import { timeLabel } from "../lib/replay/format";
  import type { ReplayState } from "../lib/stores/replay";

  interface Props {
    replay: ReplayState;
    send: CommandSender;
  }

  let { replay, send }: Props = $props();

  const SLIDER_MAX = 1000;

  const enabled = $derived(replay.loaded?.enabled ?? false);
  const playing = $derived(replay.playing);
  const sliderValue = $derived(Math.round(replay.progress * SLIDER_MAX));
  const label = $derived(timeLabel(replay.progress, replay.loaded?.durationMs ?? null));

  function togglePlay(): void {
    void send({ type: playing ? "replayPause" : "replayPlay" });
  }

  function reset(): void {
    void send({ type: "replayReset" });
  }

  function onSeek(event: Event): void {
    const value = Number((event.currentTarget as HTMLInputElement).value);
    void send({ type: "replaySeek", fraction: value / SLIDER_MAX });
  }
</script>

<div class="replay instrument" role="group" aria-label="Replay">
  <span class="tool-caption">Replay</span>
  <button
    type="button"
    class="transport tool-button"
    aria-label="Reset replay"
    title="Reset to the start of the shot window"
    disabled={!enabled}
    onclick={reset}
  >
    <svg viewBox="0 0 20 20" aria-hidden="true" width="16" height="16">
      <path d="M4 4v12M15 4l-8 6 8 6z" />
    </svg>
  </button>
  <button
    type="button"
    class="transport play tool-button"
    aria-label={playing ? "Pause replay" : "Play replay"}
    title={!enabled ? "Select a shot with a saved trace to replay" : playing ? "Pause replay" : "Play replay"}
    aria-pressed={playing}
    disabled={!enabled}
    onclick={togglePlay}
  >
    <svg viewBox="0 0 20 20" aria-hidden="true" width="16" height="16">
      {#if playing}<path d="M6 4v12M14 4v12" />{:else}<path d="M6 3l10 7-10 7z" />{/if}
    </svg>
    <span>{playing ? "Pause" : "Play"}</span>
  </button>
  <input
    type="range"
    min="0"
    max={SLIDER_MAX}
    value={sliderValue}
    aria-label="Replay scrubber"
    title="Scrub through the shot window"
    disabled={!enabled}
    oninput={onSeek}
  />
  <span class="time">{label}</span>
</div>

<style>
  .replay { flex: 1 1 310px; }
  .transport { width: 32px; padding: 0; }
  .play { width: auto; min-width: 76px; padding: 0 var(--space-2); }
  svg { fill: none; stroke: currentColor; stroke-width: 1.5; stroke-linecap: round; stroke-linejoin: round; }
  input { flex: 1; min-width: 36px; width: 80px; }
  .time {
    flex: 0 1 100px;
    min-width: 0;
    overflow: hidden;
    white-space: nowrap;
    text-overflow: ellipsis;
    text-align: right;
    color: var(--text-dim);
    font-size: var(--text-xs);
    font-variant-numeric: tabular-nums;
  }
  @media (max-width: 480px) {
    .tool-caption { display: none; }
    .replay { gap: var(--space-1); padding: var(--space-1); }
  }
</style>
