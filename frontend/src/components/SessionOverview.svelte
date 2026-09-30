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
  const scale = $derived(targetScale(Math.min(width, height), extent));

  $effect(() => {
    model.setShots(series.entries.map(({ shot, index }) => ({ xMm: shot.xMm, yMm: shot.yMm, label: String(index + 1) })));
    const local = series.entries.findIndex(entry => entry.index === selected);
    model.setSelectedShot(local < 0 ? null : local);
    model.setShotDiameter(shotDiameterMm);
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
          <button class="marker" class:selected={index === selected}
            style:left={`${width / 2 + (shot.xMm - viewport.centre[0]) * scale}px`}
            style:top={`${height / 2 + (shot.yMm - viewport.centre[1]) * scale}px`}
            aria-label={`Select shot ${index + 1}`} aria-pressed={index === selected}
            onclick={() => void send({ type: "selectShot", index })}>
            {index + 1}
          </button>
        {/if}
      {/each}
    </div>
  {/if}
</section>

<style>
  .overview {
    flex: none;
    padding: var(--space-3);
    background: var(--panel);
    border: 1px solid var(--divider);
    border-radius: var(--radius);
  }
  h3 { margin: 0 0 var(--space-3); }
  .mini-target {
    --target-bg: var(--panel);
    --target-face: var(--panel);
    --target-ring: var(--text-muted);
    --target-label: var(--text-dim);
    position: relative;
    display: flex;
    aspect-ratio: 1;
  }
  .marker {
    position: absolute;
    transform: translate(-50%, -50%);
    min-width: 20px;
    height: 20px;
    padding: 0 3px;
    border-radius: 50%;
    border: 1px solid var(--target-shot);
    color: var(--text);
    background: var(--panel);
    font-size: var(--text-xs);
  }
  .marker:hover {
    border-color: var(--accent-strong);
    background: var(--surface-hover);
    z-index: 2;
  }
  .marker:active { background: var(--accent); }
  .marker:focus-visible { z-index: 3; }
  .marker.selected {
    border-color: var(--accent-strong);
    color: var(--accent-strong);
    z-index: 1;
  }
  .empty {
    color: var(--text-muted);
    text-align: center;
    font-size: var(--text-sm);
  }
  @media (max-width: 1050px) {
    .overview { padding: var(--space-2); }
    .mini-target { height: 100px; aspect-ratio: auto; }
    h3 { margin-bottom: var(--space-2); }
  }
</style>
