<script lang="ts">
  import { currentSeries } from "../lib/shots/series";
  import TargetView from "./TargetView.svelte";
  import type { CommandSender } from "../lib/app/commands";
  import { targetScale } from "../lib/target/geometry";
  import { TargetModel } from "../lib/target/model";
  import { sessionViewport } from "../lib/target/session";
  import type { WireRing, WireShot } from "../lib/wire/types";

  interface Props {
    shots: WireShot[];
    selected: number | null;
    rings: WireRing[];
    shotDiameterMm: number;
    send: CommandSender;
    shotsPerSeries?: number;
  }

  let { shots, selected, rings, shotDiameterMm, send, shotsPerSeries = 10 }: Props = $props();
  const model = new TargetModel();
  let width = $state(0);
  let height = $state(0);
  const series = $derived(currentSeries(shots, selected, shotsPerSeries));
  const viewport = $derived(sessionViewport(rings, series.entries.map(entry => entry.shot), shotDiameterMm));
  const extent = $derived(viewport.extentMm);
  const current = $derived(selected ?? series.entries[series.entries.length - 1]?.index ?? null);
  const scale = $derived(targetScale(Math.min(width, height), extent));
  const markerPx = $derived(Math.max(10, shotDiameterMm * scale));

  $effect(() => {
    model.setExtent(extent);
  });
</script>

<section class="overview" aria-label="Session target">
  <h3 class="panel-title">Series {series.active + 1} target</h3>
  {#if shots.length === 0}
    <p class="empty">No shots yet. Recorded positions will appear here.</p>
  {:else}
    <div class="mini-target" bind:clientWidth={width} bind:clientHeight={height}>
      <TargetView {model} {rings} centre={viewport.centre} animateZoom={false} onextent={() => model.setExtent(extent)} />
      {#each series.entries as { shot, index }}
        {#if shot.xMm !== null && shot.yMm !== null}
          <button class="marker" class:selected={index === current}
            style:left={`${width / 2 + (shot.xMm - viewport.centre[0]) * scale}px`}
            style:top={`${height / 2 + (shot.yMm - viewport.centre[1]) * scale}px`}
            style:width={`${markerPx}px`} style:height={`${markerPx}px`}
            aria-label={`Select shot ${index + 1}`} aria-pressed={index === selected}
            onclick={() => void send({ type: "selectShot", index })}>
          </button>
        {/if}
      {/each}
    </div>
  {/if}
</section>

<style>
  .overview {
    flex: none;
    position: relative;
    aspect-ratio: 1;
    overflow: hidden;
    background: var(--panel);
    border: 1px solid var(--divider);
    border-radius: var(--radius);
  }
  h3 { position: absolute; top: var(--space-3); left: var(--space-3); z-index: 2; margin: 0; pointer-events: none; }
  .overview:has(.empty) { aspect-ratio: auto; min-height: 110px; }
  .mini-target {
    --target-bg: var(--panel);
    --target-face: var(--panel);
    --target-ring: var(--text-muted);
    --target-label: var(--text-dim);
    position: absolute;
    inset: 0;
    display: flex;
  }
  .marker {
    position: absolute;
    transform: translate(-50%, -50%);
    padding: 0;
    border-radius: 50%;
    border: 1px solid var(--panel);
    background: var(--text-muted);
  }
  .marker:hover {
    border-color: var(--accent-strong);
    background: var(--surface-hover);
    z-index: 2;
  }
  .marker:active { background: var(--accent); }
  .marker:focus-visible { z-index: 3; }
  .marker.selected {
    background: var(--text);
    z-index: 4;
  }
  .empty {
    margin: 0;
    padding: 40px var(--space-3) var(--space-3);    color: var(--text-muted);
    text-align: center;
    font-size: var(--text-sm);
  }
  @media (max-width: 1050px) {
    .overview { height: 100px; aspect-ratio: auto; }
    h3 { top: var(--space-2); left: var(--space-2); }
  }
</style>
