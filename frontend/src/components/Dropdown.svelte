<script lang="ts" generics="T extends string | number">
  interface Props {
    value: T;
    options: { value: T; label: string }[];
    label: string;
    id?: string;
    title?: string;
    upwards?: boolean;
    onchange?: (value: T) => void;
  }
  let { value = $bindable(), options, label, id, title, upwards = false, onchange }: Props = $props();
  let menuOpen = $state(false);
  let picker: HTMLDivElement;
  let trigger: HTMLButtonElement;
  let opensAbove = $state(false);
  let bounds = $state({ left: 0, top: 0, bottom: 0, width: 0 });
  const selectedLabel = $derived(options.find((option) => option.value === value)?.label ?? String(value));

  function openMenu(): void {
    const rect = trigger.getBoundingClientRect();
    opensAbove = upwards || (window.innerHeight - rect.bottom < 240 && rect.top > window.innerHeight - rect.bottom);
    bounds = { left: Math.max(8, Math.min(rect.left, window.innerWidth - Math.max(120, rect.width) - 8)), top: rect.bottom + 8, bottom: window.innerHeight - rect.top + 8, width: rect.width };
    menuOpen = true;
  }

  function focusSelected(menu: HTMLElement): void {
    (menu.querySelector<HTMLButtonElement>('[aria-checked="true"]') ?? menu.querySelector<HTMLButtonElement>("button"))?.focus();
  }

  function choose(next: T): void {
    menuOpen = false;
    value = next;
    onchange?.(next);
    trigger.focus();
  }

  function menuKey(event: KeyboardEvent): void {
    if (event.key !== "Tab") event.stopPropagation();
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

</script>

<svelte:window onpointerdown={(event) => {
  if (menuOpen && event.target instanceof Node && !picker.contains(event.target)) menuOpen = false;
}} onresize={() => menuOpen = false} />

<div class="picker" bind:this={picker}>
  <button type="button" class="trigger" bind:this={trigger} {id} {title}
    aria-label={label} aria-haspopup="menu" aria-expanded={menuOpen}
    onclick={() => menuOpen ? menuOpen = false : openMenu()}
    onkeydown={(event) => {
      if (event.key === "ArrowDown" || event.key === "ArrowUp") {
        event.preventDefault();
        event.stopPropagation();
        openMenu();
      }
    }}>
    <span>{selectedLabel}</span>
    <svg width="10" height="10" viewBox="0 0 10 10" aria-hidden="true">
      <path d="m2 4 3 3 3-3" fill="none" stroke="currentColor" stroke-width="1.5" />
    </svg>
  </button>
  {#if menuOpen}
    <div class="menu" role="menu" aria-label={label} tabindex="-1" use:focusSelected onkeydown={menuKey}
      style:left={`${bounds.left}px`} style:top={opensAbove ? undefined : `${bounds.top}px`}
      style:bottom={opensAbove ? `${bounds.bottom}px` : undefined} style:min-width={`${Math.max(120, bounds.width)}px`}>
      {#each options as option (option.value)}
        <button type="button" role="menuitemradio" aria-checked={value === option.value}
          tabindex="-1" onclick={() => choose(option.value)}>{option.label}</button>
      {/each}
    </div>
  {/if}
</div>

<style>
  .picker { min-width: 0; width: 100%; }
  .trigger { width: 100%; justify-content: space-between; gap: var(--space-2); }
  .trigger span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .trigger svg { flex-shrink: 0; }
  .menu {
    position: fixed;
    z-index: 100;
    overflow-y: auto;
    max-height: min(240px, 45vh);
    display: grid;
    min-width: 120px;
    max-width: calc(100vw - 16px);
    padding: var(--space-1);
    background: var(--panel-raised);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    box-shadow: 0 8px 24px rgb(0 0 0 / 30%);
  }
  .menu button {
    justify-content: flex-start;
    text-align: left;
    border-color: transparent;
    background: transparent;
  }
  .menu button:hover, .menu button:focus-visible { background: var(--surface-hover); }
  .menu button[aria-checked="true"] { color: var(--accent-strong); background: var(--bg-sunken); }
</style>
