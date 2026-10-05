<script lang="ts">
  import { drawTarget, type TargetColours } from "../lib/target/draw";
  import { wheelFactor } from "../lib/target/geometry";
  import type { TargetModel } from "../lib/target/model";
  import type { WireRing } from "../lib/wire/types";

  interface Props {
    model: TargetModel;
    rings: WireRing[];
    onextent: (extentMm: number) => void;
  }

  let { model, rings, onextent }: Props = $props();

  let canvas: HTMLCanvasElement;
  let width = $state(0);
  let height = $state(0);

  function colours(element: HTMLElement): TargetColours {
    const style = getComputedStyle(element);
    const token = (name: string): string => style.getPropertyValue(name).trim();
    return {
      face: token("--target-face"),
      ring: token("--target-ring"),
      label: token("--target-label"),
      crosshair: token("--target-crosshair"),
      shot: token("--target-shot"),
      liveAim: token("--target-live-aim"),
      holdZone: token("--target-hold-zone"),
      approach: token("--trace-approach"),
      release: token("--trace-release"),
      follow: token("--trace-follow"),
    };
  }

  // Redraws when the model version, the rings or the size change.
  $effect(() => {
    // Reference the reactive inputs so the effect re-runs on each.
    void model.version;
    void rings;
    const ratio = window.devicePixelRatio || 1;
    const pixelWidth = Math.round(width * ratio);
    const pixelHeight = Math.round(height * ratio);
    if (canvas.width !== pixelWidth || canvas.height !== pixelHeight) {
      canvas.width = pixelWidth;
      canvas.height = pixelHeight;
    }
    const context = canvas.getContext("2d");
    if (context === null || width === 0 || height === 0) {
      return;
    }
    context.setTransform(ratio, 0, 0, ratio, 0, 0);
    drawTarget(context, width, height, model, rings, colours(canvas));
  });

  function onWheel(event: WheelEvent): void {
    event.preventDefault();
    if (event.deltaY === 0) {
      return;
    }
    model.setExtent(model.extentMm * wheelFactor(event.deltaY));
    onextent(model.extentMm);
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
