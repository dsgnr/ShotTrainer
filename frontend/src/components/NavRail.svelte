<script lang="ts">
  interface Props {
    onsessions: () => void;
    onpreferences: () => void;
    onpopout: () => void;
    onsheet: () => void;
  }

  let { onsessions, onpreferences, onpopout, onsheet }: Props = $props();
</script>

<div class="rail">
  <!-- The target view is the home surface, so its icon marks the current place. -->
  <span class="item current" aria-current="page" title="Target">
    <svg viewBox="0 0 24 24" aria-hidden="true" width="20" height="20">
      <circle cx="12" cy="12" r="9" />
      <circle cx="12" cy="12" r="5" />
      <circle cx="12" cy="12" r="1.5" fill="currentColor" stroke="none" />
    </svg>
  </span>

  <button type="button" class="item" title="Sessions" aria-label="Sessions" onclick={onsessions}>
    <svg viewBox="0 0 24 24" aria-hidden="true" width="20" height="20">
      <rect x="4" y="4" width="16" height="4" rx="1" />
      <rect x="4" y="10" width="16" height="4" rx="1" />
      <rect x="4" y="16" width="16" height="4" rx="1" />
    </svg>
  </button>

  <button type="button" class="item" title="Pop out camera" aria-label="Pop out camera" onclick={onpopout}>
    <svg viewBox="0 0 24 24" aria-hidden="true" width="20" height="20">
      <rect x="3" y="6" width="13" height="12" rx="2" />
      <path d="M16 10l5-3v10l-5-3z" />
    </svg>
  </button>

  <button type="button" class="item" title="Shot sheet" aria-label="Shot sheet" onclick={onsheet}>
    <svg viewBox="0 0 24 24" aria-hidden="true" width="20" height="20">
      <rect x="5" y="3" width="14" height="18" rx="2" />
      <path d="M8 8h8M8 12h8M8 16h5" />
    </svg>
  </button>

  <span class="spacer"></span>

  <button type="button" class="item" title="Preferences" aria-label="Preferences" onclick={onpreferences}>
    <svg viewBox="0 0 24 24" aria-hidden="true" width="20" height="20">
      <circle cx="12" cy="12" r="3" />
      <path d="M12 3v3M12 18v3M3 12h3M18 12h3M5.6 5.6l2.1 2.1M16.3 16.3l2.1 2.1M18.4 5.6l-2.1 2.1M7.7 16.3l-2.1 2.1" />
    </svg>
  </button>
</div>

<style>
  .rail {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: var(--space-1);
    width: 32px;
  }

  .item {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 36px;
    height: 36px;
    padding: 0;
    color: var(--text-muted);
    background: transparent;
    border: 0;
    border-radius: var(--radius-control);
  }

  button.item {
    cursor: pointer;
    transition:
      color 120ms ease-out,
      background-color 120ms ease-out;
  }

  button.item:hover {
    color: var(--text);
    background: var(--surface-hover);
  }

  .item.current {
    color: var(--accent-strong);
  }

  svg {
    fill: none;
    stroke: currentColor;
    stroke-width: 1.6;
    stroke-linecap: round;
    stroke-linejoin: round;
  }

  .spacer {
    flex: 1;
  }
</style>
