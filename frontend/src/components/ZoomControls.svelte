<script lang="ts">
  import { extentFromRatio, ratioFromExtent } from "../lib/target/geometry";

  interface Props {
    extentMm: number;
    onextent: (extentMm: number) => void;
  }

  let { extentMm, onextent }: Props = $props();

  const SLIDER_MAX = 1000;
  const STEP = 50;

  const ratio = $derived(ratioFromExtent(extentMm));
  const sliderValue = $derived(Math.round(ratio * SLIDER_MAX));

  function emitFromSlider(value: number): void {
    const clamped = Math.max(0, Math.min(SLIDER_MAX, value));
    onextent(extentFromRatio(clamped / SLIDER_MAX));
  }

  function onInput(event: Event): void {
    emitFromSlider(Number((event.currentTarget as HTMLInputElement).value));
  }

  function zoomIn(): void {
    emitFromSlider(sliderValue - STEP);
  }

  function zoomOut(): void {
    emitFromSlider(sliderValue + STEP);
  }
</script>

<div class="zoom">
  <span class="caption">Zoom</span>
  <button type="button" class="step" aria-label="Zoom out" onclick={zoomOut}>&minus;</button>
  <input
    type="range"
    min="0"
    max={SLIDER_MAX}
    value={sliderValue}
    aria-label="Target zoom"
    title="Drag or scroll to zoom the target view."
    oninput={onInput}
  />
  <button type="button" class="step" aria-label="Zoom in" onclick={zoomIn}>+</button>
  <span class="readout">{Math.round(extentMm)} mm</span>
</div>

<style>
  .zoom {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 0 8px 4px;
  }

  .caption {
    color: var(--text-dim);
  }

  .step {
    width: 32px;
    height: 28px;
    padding: 0;
  }

  input {
    flex: 1;
    min-width: 32px;
  }

  .readout {
    min-width: 56px;
    color: var(--text-dim);
  }
</style>
