<script lang="ts">
  interface Props {
    page?: "target" | "sessions" | "about";
    onabout?: () => void;
    ontarget?: () => void;
    onsessions: () => void;
    onpreferences: () => void;
    onpopout: () => void;
  }

  let { page = "target", ontarget, onabout, onsessions, onpreferences, onpopout }: Props = $props();
</script>

<div class="rail">
  <span class="item"><img src="/icon.svg" alt="ShotTrainer" width="32" height="32" /></span>
  <button type="button" class="item" class:current={page === "target"} aria-current={page === "target" ? "page" : undefined} title="Target" aria-label="Target" onclick={ontarget}>
    <svg viewBox="0 0 24 24" aria-hidden="true" width="20" height="20">
      <circle cx="12" cy="12" r="9" /><circle cx="12" cy="12" r="5" /><circle cx="12" cy="12" r="1" />
    </svg>
  </button>

  <button type="button" class="item" class:current={page === "sessions"} aria-current={page === "sessions" ? "page" : undefined} title="Sessions" aria-label="Sessions" onclick={onsessions}>
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

  <span class="spacer"></span>

  <button type="button" class="item" class:current={page === "about"} aria-current={page === "about" ? "page" : undefined} title="About" aria-label="About" onclick={onabout}>
    <svg viewBox="0 0 24 24" aria-hidden="true" width="20" height="20">
      <circle cx="12" cy="12" r="9" /><path d="M12 11v6M12 7v1" />
    </svg>
  </button>

  <button type="button" class="item" title="Preferences" aria-label="Preferences" onclick={onpreferences}>
    <svg viewBox="0 0 24 24" aria-hidden="true" width="20" height="20">
      <circle cx="12" cy="12" r="3" />
      <path d="M19.73 9.93 L21.85 10.26 L21.85 13.74 L19.73 14.07 L18.93 16.00 L20.19 17.74 L17.74 20.19 L16.00 18.93 L14.07 19.73 L13.74 21.85 L10.26 21.85 L9.93 19.73 L8.00 18.93 L6.26 20.19 L3.81 17.74 L5.07 16.00 L4.27 14.07 L2.15 13.74 L2.15 10.26 L4.27 9.93 L5.07 8.00 L3.81 6.26 L6.26 3.81 L8.00 5.07 L9.93 4.27 L10.26 2.15 L13.74 2.15 L14.07 4.27 L16.00 5.07 L17.74 3.81 L20.19 6.26 L18.93 8.00 Z" />
    </svg>
  </button>
</div>

<style>
  .rail {
    display: flex;
    flex-direction: column;
    flex: 1;
    min-height: 0;
    align-items: center;
    gap: var(--space-1);
    width: 32px;
  }

  .item {
    display: inline-flex;
    flex-shrink: 0;
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
    background: var(--panel-raised);
    box-shadow: inset 3px 0 var(--accent-strong);
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
