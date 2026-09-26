<script lang="ts">
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

  let menuOpen = $state(false);
  let picker: HTMLDivElement;
  let trigger: HTMLButtonElement;
  const options = $derived([
    { value: "auto", label: "Auto" },
    { value: "100", label: "100%" },
    ...(percentage === 100 ? [] : [{ value: String(percentage), label: `${percentage}%` }]),
  ]);
  const selected = $derived(auto ? "auto" : String(percentage));

  function openMenu(): void {
    menuOpen = true;
  }

  function focusSelected(menu: HTMLElement): void {
    menu.querySelector<HTMLButtonElement>('[aria-checked="true"]')?.focus();
  }

  function choose(value: string): void {
    menuOpen = false;
    if (value === "auto") onauto();
    else onextent(clampExtent(referenceExtentMm * 100 / Number(value)));
    trigger.focus();
  }

  function menuKey(event: KeyboardEvent): void {
    event.stopPropagation();
    const items = [...picker.querySelectorAll<HTMLButtonElement>('[role="menuitemradio"]')];
    const index = items.indexOf(document.activeElement as HTMLButtonElement);
    let next: number | null = null;
    if (event.key === "ArrowDown") next = (index + 1) % items.length;
    if (event.key === "ArrowUp") next = (index - 1 + items.length) % items.length;
    if (event.key === "Home") next = 0;
    if (event.key === "End") next = items.length - 1;
    if (next !== null) {
      event.preventDefault();
      items[next]?.focus();
    } else if (event.key === "Escape") {
      event.preventDefault();
      menuOpen = false;
      trigger.focus();
    } else if (event.key === "Tab") {
      menuOpen = false;
      trigger.focus();
    }
  }

  function emitFromSlider(value: number): void {
    const clamped = Math.max(0, Math.min(SLIDER_MAX, value));
    onextent(clampExtent(extentFromRatio(1 - clamped / SLIDER_MAX)));
  }
</script>

<svelte:window onpointerdown={(event) => {
  if (menuOpen && event.target instanceof Node && !picker.contains(event.target)) menuOpen = false;
}} />

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
  <div class="picker" bind:this={picker}>
    <button type="button" class="tool-button readout num" bind:this={trigger}
      aria-label="Target zoom mode" aria-haspopup="menu" aria-expanded={menuOpen}
      onclick={() => menuOpen ? menuOpen = false : void openMenu()}
      onkeydown={(event) => {
        if (event.key === "ArrowDown" || event.key === "ArrowUp") {
          event.preventDefault();
          event.stopPropagation();
          void openMenu();
        }
      }}>
      {auto ? "Auto" : `${percentage}%`}
      <svg width="10" height="10" viewBox="0 0 10 10" aria-hidden="true">
        <path d="m2 4 3 3 3-3" fill="none" stroke="currentColor" stroke-width="1.5" />
      </svg>
    </button>
    {#if menuOpen}
      <div class="zoom-menu" role="menu" aria-label="Target zoom mode" tabindex="-1" use:focusSelected onkeydown={menuKey}>
        {#each options as option (option.value)}
          <button type="button" role="menuitemradio" aria-checked={selected === option.value}
            tabindex="-1" onclick={() => choose(option.value)}>{option.label}</button>
        {/each}
      </div>
    {/if}
  </div>
</div>

<style>
  .zoom { flex: 1 1 260px; }
  .step { width: 32px; padding: 0; font-size: var(--text-lg); }
  input { flex: 1; min-width: 40px; width: 80px; }
  .picker { position: relative; flex-shrink: 0; }
  .zoom-menu {
    position: absolute;
    bottom: calc(100% + var(--space-2));
    right: 0;
    z-index: 5;
    display: grid;
    min-width: 120px;
    padding: var(--space-1);
    background: var(--panel-raised);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    box-shadow: 0 8px 24px rgb(0 0 0 / 30%);
  }
  .zoom-menu button {
    justify-content: flex-start;
    text-align: left;
    border-color: transparent;
    background: transparent;
  }
  .zoom-menu button:hover, .zoom-menu button:focus-visible { background: var(--surface-hover); }
  .zoom-menu button[aria-checked="true"] { color: var(--accent-strong); background: var(--bg-sunken); }
  .readout { min-width: 80px; padding: 0 var(--space-2); color: var(--text-dim); }
  @media (max-width: 480px) {
    .zoom { gap: var(--space-1); padding: var(--space-1); }
    .tool-caption { display: none; }
    .readout { min-width: 56px; }
  }
</style>
