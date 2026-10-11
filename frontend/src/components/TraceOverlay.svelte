<script lang="ts">
  import { onMount } from "svelte";
  import { focusTrap } from "../lib/app/focus-trap";
  import type { CommandSender } from "../lib/app/commands";
  import { seriesIndex } from "../lib/shots/series";
  import { themeColours } from "../lib/target/colours";
  import { drawTarget, drawTrace } from "../lib/target/draw";
  import { clampExtent, extentForRings, targetScale, wheelFactor } from "../lib/target/geometry";
  import { TargetModel } from "../lib/target/model";
    import type { WireRing, WireShot, WireShotTrace } from "../lib/wire/types";
  import ZoomControls from "./ZoomControls.svelte";
  import Dropdown from "./Dropdown.svelte";

  interface Props {
    shots: WireShot[];
    traces: WireShotTrace[];
    rings: WireRing[];
    shotsPerSeries: number;
    shotDiameterMm: number;
    send: CommandSender;
    onclose: () => void;
  }
  let { shots, traces, rings, shotsPerSeries, shotDiameterMm, send, onclose }: Props = $props();

  const ALL = -1;
  let selected = $state(ALL);
  let canvas: HTMLCanvasElement;
  let width = $state(0);
  let height = $state(0);
  // `null` fits the face, as the main target does until the user zooms.
  let zoom = $state<number | null>(null);
  const faceExtent = $derived(extentForRings(rings));
  const extent = $derived(zoom ?? faceExtent);

  function onWheel(event: WheelEvent): void {
    event.preventDefault();
    if (event.deltaY !== 0) zoom = clampExtent(extent * wheelFactor(event.deltaY));
  }

  const seriesList = $derived([...new Set(shots.map((shot, i) => seriesIndex(shot, i, shotsPerSeries)))]);
  const options = $derived([
    { value: ALL, label: "All series" },
    ...seriesList.map(series => ({ value: series, label: `Series ${series + 1}` })),
  ]);
  const visible = $derived(shots.flatMap((shot, index) =>
    selected === ALL || seriesIndex(shot, index, shotsPerSeries) === selected ? [{ shot, index }] : []));

  onMount(() => { void send({ type: "loadShotTraces" }); });

  $effect(() => {
    const context = canvas.getContext("2d");
    if (context === null || width === 0 || height === 0) return;
    const ratio = window.devicePixelRatio || 1;
    canvas.width = Math.round(width * ratio);
    canvas.height = Math.round(height * ratio);
    const model = new TargetModel();
    model.setExtent(extent);
    model.setShotDiameter(shotDiameterMm);
    model.setShots(visible.map(({ shot, index }) => ({ xMm: shot.xMm, yMm: shot.yMm, label: String(index + 1) })));
    context.setTransform(ratio, 0, 0, ratio, 0, 0);
    const palette = themeColours(canvas);
    drawTarget(context, width, height, model, rings, palette, extent);
    const scale = targetScale(Math.min(width, height), extent);
    for (const { index } of visible) {
      const trace = traces[index];
      if (trace === undefined) continue;
      const layer = new TargetModel();
      layer.setIsolateSelectedShot(true);
      layer.setTrace(trace.points.map(([x, y]) => [x ?? 0, y ?? 0]));
      layer.setTraceSegments(trace.releaseIndex, trace.splitIndex);
      drawTrace(context, width / 2, height / 2, scale, layer, palette);
    }
  });
</script>

<!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
<div class="backdrop" role="presentation" onclick={onclose} onkeydown={(event) => {
  event.stopPropagation(); if (event.key === "Escape") onclose();
}}>
  <!-- svelte-ignore a11y_click_events_have_key_events -->
  <div class="dialog" role="dialog" aria-modal="true" aria-labelledby="trace-overlay-title"
    tabindex="-1" use:focusTrap onclick={(event) => event.stopPropagation()}>
    <header>
      <h2 id="trace-overlay-title">Shot traces</h2>
      <div class="series"><Dropdown bind:value={selected} {options} label="Series" /></div>
    </header>
    <div class="stage" bind:clientWidth={width} bind:clientHeight={height}>
      <canvas bind:this={canvas} onwheel={onWheel} aria-label="Overlaid shot traces"></canvas>
    </div>
    <footer>
      <ZoomControls extentMm={extent} auto={zoom === null} onauto={() => zoom = null}
        referenceExtentMm={faceExtent} onextent={(next) => zoom = next} />
      <button type="button" onclick={onclose}>Close</button>
    </footer>
  </div>
</div>

<style>
  .backdrop { position: fixed; inset: 0; z-index: 10; display: grid; place-items: center; background: #0008; padding: 16px; }
  .dialog { width: min(720px, 100%); height: min(780px, 100%); display: flex; flex-direction: column; overflow: hidden; background: var(--panel); border: 1px solid var(--border); border-radius: var(--radius); }
  header, footer { flex: none; display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 12px 16px; }
  header { border-bottom: 1px solid var(--divider); }
  footer { border-top: 1px solid var(--divider); }
  h2 { margin: 0; color: var(--text-heading); }
  .series { width: 200px; }
  .stage { position: relative; flex: 1; min-height: 0; background: var(--bg-sunken); }
  canvas { position: absolute; inset: 0; width: 100%; height: 100%; }
</style>
