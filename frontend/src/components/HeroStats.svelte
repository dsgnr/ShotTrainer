<script lang="ts">
  import {
    groupFigure,
    timeOnTargetFigure,
    totalScoreFigure,
    tremorFigure,
  } from "../lib/stats/hero";
  import type { F64, WireRing, WireShotStats, WireTraceStats } from "../lib/wire/types";
  import Metric from "./Metric.svelte";
  import Panel from "./Panel.svelte";

  interface Props {
    total: F64;
    shotCount: number;
    group: WireShotStats | null;
    traceStats: WireTraceStats | null;
    tracePoints: [number, number][];
    rings: WireRing[];
  }

  let { total, shotCount, group, traceStats, tracePoints, rings }: Props = $props();

  const totalText = $derived(totalScoreFigure(total, shotCount));
  const groupText = $derived(group === null ? { value: "-", tooltip: "" } : groupFigure(group));
  const tremorText = $derived(tremorFigure(traceStats));
  const timeOnTarget = $derived(timeOnTargetFigure(tracePoints, rings));
</script>

<div class="hero">
  <Panel title="Result">
    <div class="grid">
      <Metric caption="Total score" value={totalText} size="lg" accent />
      <Metric
        caption="Group size"
        value={groupText.value}
        sub="extreme spread"
        title={groupText.tooltip}
      />
      <Metric caption={timeOnTarget.caption} value={timeOnTarget.value} />
    </div>
  </Panel>

  <Panel title="Hold">
    <Metric caption="Hold tremor" value={tremorText} sub="RMS deviation" />
  </Panel>
</div>

<style>
  .hero {
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
  }

  .grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: var(--space-4) var(--space-3);
  }

  /* The headline figure spans the row above the two secondary measures. */
  .grid :global(.metric:first-child) {
    grid-column: 1 / -1;
  }
</style>
