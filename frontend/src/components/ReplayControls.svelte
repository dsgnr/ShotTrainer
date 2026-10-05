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

<div class="replay" role="group" aria-label="Replay">
  <button
    type="button"
    class="transport"
    aria-label="Reset replay"
    title="Reset to the start of the shot window"
    disabled={!enabled}
    onclick={reset}
  >
    &#9198;
  </button>
  <button
    type="button"
    class="transport"
    aria-label={playing ? "Pause replay" : "Play replay"}
    title={playing ? "Pause" : "Play"}
    disabled={!enabled}
    onclick={togglePlay}
  >
    {playing ? "\u23f8" : "\u25b6"}
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
  .replay {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 4px 8px;
  }

  .transport {
    width: 32px;
    height: 28px;
    padding: 0;
    font-size: 14px;
  }

  input {
    flex: 1;
    min-width: 48px;
    max-width: 150px;
  }

  .time {
    min-width: 112px;
    text-align: right;
    color: var(--text-dim);
    font-variant-numeric: tabular-nums;
  }
</style>
