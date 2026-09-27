<script lang="ts">
  import Dropdown from "./Dropdown.svelte";
  import { clampExtent, DEFAULT_EXTENT_MM, extentFromRatio, ratioFromExtent, ZOOM_MIN_MM, ZOOM_MAX_MM } from "../lib/target/geometry";

  interface Props {
    extentMm: number;
    auto: boolean;
    onauto: () => void;
    referenceExtentMm?: number;
    onextent: (extentMm: number) => void;
  }
  let { extentMm, auto, onauto, referenceExtentMm = DEFAULT_EXTENT_MM, onextent }: Props = $props();
  const SLIDER_MAX = 1000;
  const STEP = 25;
  const sliderValue = $derived(Math.round((1 - ratioFromExtent(extentMm)) * SLIDER_MAX));
  const percentage = $derived(Math.round(referenceExtentMm / extentMm * 100));

  const options = $derived([
    { value: "auto", label: "Auto" },
    { value: "100", label: "100%" },
    ...(percentage === 100 ? [] : [{ value: String(percentage), label: `${percentage}%` }]),
  ]);
  const selected = $derived(auto ? "auto" : String(percentage));

  function choose(value: string): void {
    if (value === "auto") onauto();
    else onextent(clampExtent(referenceExtentMm * 100 / Number(value)));
  }

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
  <div class="readout num">
    <Dropdown value={selected} {options} label="Target zoom mode" upwards onchange={choose} />
  </div>
</div>

<style>
  .zoom { flex: 1 1 260px; }
  .step { width: 32px; padding: 0; font-size: var(--text-lg); }
  input { flex: 1; min-width: 40px; width: 80px; }
  .readout { width: 88px; flex-shrink: 0; }
  @media (max-width: 480px) {
    .zoom { gap: var(--space-1); padding: var(--space-1); }
    .tool-caption { display: none; }
    .readout { width: 72px; }
  }
</style>
