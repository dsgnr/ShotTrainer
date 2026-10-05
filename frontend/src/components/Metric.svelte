<script lang="ts">
  interface Props {
    /** The small uppercase label above the value. */
    caption: string;
    /** The headline figure. */
    value: string;
    /** Optional dim text under the value, such as a unit or sub-measure. */
    sub?: string;
    /** Optional tooltip on the value. */
    title?: string;
    /** Larger value for the single most important figure in a group. */
    size?: "md" | "lg";
    /** Colours the value with the accent for a live or headline figure. */
    accent?: boolean;
  }

  let { caption, value, sub, title, size = "md", accent = false }: Props = $props();
</script>

<div class="metric">
  <p class="caption panel-title">{caption}</p>
  <p class="value num" class:accent data-size={size} {title}>{value}</p>
  {#if sub !== undefined}<p class="sub">{sub}</p>{/if}
</div>

<style>
  .metric {
    display: flex;
    flex-direction: column;
    gap: 2px;
    min-width: 0;
  }

  .caption {
    color: var(--text-muted);
  }

  .value {
    margin: 0;
    color: var(--text-heading);
    font-weight: 600;
    line-height: 1.1;
    letter-spacing: -0.01em;
  }

  .value[data-size="md"] {
    font-size: var(--text-xl);
  }

  .value[data-size="lg"] {
    font-size: var(--text-2xl);
  }

  .value.accent {
    color: var(--accent-strong);
  }

  .sub {
    margin: 0;
    color: var(--text-dim);
    font-size: var(--text-xs);
  }
</style>
