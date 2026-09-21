<script lang="ts">
  import type { Snippet } from "svelte";

  interface Props {
    /** The uppercase panel label. */
    title: string;
    /** Optional small leading icon, rendered before the title. */
    icon?: Snippet;
    /** Optional trailing content on the header row, such as a status. */
    aside?: Snippet;
    /** The panel body. */
    children: Snippet;
    /** A region label for assistive technology. Defaults to the title. */
    label?: string;
  }

  let { title, icon, aside, children, label }: Props = $props();
</script>

<section class="panel" aria-label={label ?? title}>
  <header class="head">
    {#if icon}<span class="icon">{@render icon()}</span>{/if}
    <h3 class="panel-title">{title}</h3>
    {#if aside}<span class="aside">{@render aside()}</span>{/if}
  </header>
  <div class="body">{@render children()}</div>
</section>

<style>
  .panel {
    background: var(--panel);
    border: 1px solid var(--divider);
    border-radius: var(--radius);
  }

  .head {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    padding: var(--space-3) var(--space-4);
    border-bottom: 1px solid var(--divider);
  }

  .icon {
    display: inline-flex;
    color: var(--text-muted);
  }

  .aside {
    margin-left: auto;
  }

  .body {
    padding: var(--space-4);
  }
</style>
