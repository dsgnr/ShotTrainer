<script lang="ts">
  import { clampExtent, DEFAULT_EXTENT_MM, extentFromRatio, ratioFromExtent, ZOOM_MIN_MM, ZOOM_MAX_MM } from "../lib/target/geometry";

  interface Props {
    extentMm: number;
    referenceExtentMm?: number;
    onextent: (extentMm: number) => void;
  }
  let { extentMm, referenceExtentMm = DEFAULT_EXTENT_MM, onextent }: Props = $props();
  const SLIDER_MAX = 1000;
  const STEP = 25;
  const sliderValue = $derived(Math.round((1 - ratioFromExtent(extentMm)) * SLIDER_MAX));
  const percentage = $derived(Math.round(referenceExtentMm / extentMm * 100));

  function emitFromSlider(value: number): void {
    const clamped = Math.max(0, Math.min(SLIDER_MAX, value));
    onextent(clampExtent(extentFromRatio(1 - clamped / SLIDER_MAX)));
  }
</script>

<div class="zoom instrument" role="group" aria-label="Target zoom controls">
  <span class="tool-caption">Zoom</span>
  <button type="button" class="tool-button step" aria-label="Zoom out" title="Zoom out"
    disabled={extentMm >= ZOOM_MAX_MM} onclick={() => emitFromSlider(sliderValue - STEP)}>&minus;</button>
  <input type="range" min="0" max={SLIDER_MAX} value={sliderValue}
    aria-label="Target zoom" aria-valuetext={`${percentage}%`}
    title="Drag right to enlarge the target"
    oninput={(event) => emitFromSlider(Number(event.currentTarget.value))} />
  <button type="button" class="tool-button step" aria-label="Zoom in" title="Zoom in"
    disabled={extentMm <= ZOOM_MIN_MM} onclick={() => emitFromSlider(sliderValue + STEP)}>+</button>
  <button class="tool-button readout num" aria-label="Reset target zoom" title="Fit target (100%)"
    onclick={() => onextent(clampExtent(referenceExtentMm))}>{percentage}%</button>
</div>

<style>
  .zoom { flex: 1 1 260px; }
  .step { width: 32px; padding: 0; font-size: var(--text-lg); }
  input { flex: 1; min-width: 40px; width: 80px; }
  .readout { min-width: 64px; padding: 0 var(--space-2); color: var(--text-dim); }
  @media (max-width: 480px) {
    .zoom { gap: var(--space-1); padding: var(--space-1); }
    .tool-caption { display: none; }
    .readout { min-width: 56px; }
  }
</style>
