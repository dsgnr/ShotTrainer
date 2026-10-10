<script lang="ts">
  import { onMount, untrack } from "svelte";
  import { themeColours } from "../lib/target/colours";
  import { drawTarget } from "../lib/target/draw";
  import { clampExtent, wheelFactor } from "../lib/target/geometry";
  import type { TargetModel } from "../lib/target/model";
  import type { WireRing } from "../lib/wire/types";

  interface Props {
    model: TargetModel;
    rings: WireRing[];
    onextent: (extentMm: number) => void;
    animateZoom?: boolean;
    centre?: readonly [number, number];
  }

  let { model, rings, onextent, animateZoom = true, centre = [0, 0] }: Props = $props();

  let version = $state(0);
  onMount(() => model.subscribe(() => { untrack(() => { version += 1; }); }));

  let canvas: HTMLCanvasElement;
  let width = $state(0);
  let height = $state(0);

  let displayedExtent: number | undefined;
  let zoomFrom = 0;
  let zoomTo = 0;
  let zoomStarted = 0;

  $effect(() => {
    void version;
    const currentRings = rings;
    const currentCentre = centre;
    const currentWidth = width;
    const currentHeight = height;
    const now = performance.now();
    if (zoomTo !== model.extentMm) {
      zoomFrom = displayedExtent ?? model.extentMm;
      zoomTo = model.extentMm;
      zoomStarted = now;
    }
    const ratio = window.devicePixelRatio || 1;
    const pixelWidth = Math.round(currentWidth * ratio);
    const pixelHeight = Math.round(currentHeight * ratio);
    if (canvas.width !== pixelWidth || canvas.height !== pixelHeight) {
      canvas.width = pixelWidth;
      canvas.height = pixelHeight;
    }
    const context = canvas.getContext("2d");
    if (context === null || currentWidth === 0 || currentHeight === 0) return;
    const palette = themeColours(canvas);
    const reduceMotion = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;
    const animate = animateZoom && !reduceMotion;
    let frame: number | undefined;
    function draw(time: number): void {
      const progress = animate ? Math.min(1, (time - zoomStarted) / 120) : 1;
      const eased = 1 - (1 - progress) ** 3;
      displayedExtent = zoomFrom + (zoomTo - zoomFrom) * eased;
      context!.setTransform(ratio, 0, 0, ratio, 0, 0);
      drawTarget(context!, currentWidth, currentHeight, model, currentRings, palette, displayedExtent, currentCentre);
      if (progress < 1) frame = requestAnimationFrame(draw);
    }
    draw(now);
    return () => { if (frame !== undefined) cancelAnimationFrame(frame); };
  });

  function onWheel(event: WheelEvent): void {
    event.preventDefault();
    if (event.deltaY === 0) {
      return;
    }
    onextent(clampExtent(model.extentMm * wheelFactor(event.deltaY)));
  }
</script>

<div
  class="target"
  role="group"
  aria-label="Target view"
  bind:clientWidth={width}
  bind:clientHeight={height}
>
  <canvas bind:this={canvas} aria-hidden="true" onwheel={onWheel}></canvas>
</div>

<style>
  .target {
    position: relative;
    flex: 1;
    min-width: 0;
    min-height: 0;
    background: var(--target-bg);
  }

  canvas {
    position: absolute;
    inset: 0;
    width: 100%;
    height: 100%;
  }
</style>
