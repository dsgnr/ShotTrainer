<script lang="ts">
  import {
    groupFigure,
    timeOnTargetFigure,
    totalScoreFigure,
    tremorFigure,
  } from "../lib/stats/hero";
  import type { F64, WireRing, WireShotStats, WireTraceStats } from "../lib/wire/types";

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
  const groupText = $derived(
    group === null ? { value: "-", tooltip: "" } : groupFigure(group),
  );
  const tremorText = $derived(tremorFigure(traceStats));
  const timeOnTarget = $derived(timeOnTargetFigure(tracePoints, rings));
</script>

<div class="hero">
  <div class="card">
    <p class="caption">Total score</p>
    <p class="value">{totalText}</p>
  </div>
  <div class="card">
    <p class="caption">Group size</p>
    <p class="value" title={groupText.tooltip}>{groupText.value}</p>
    <p class="subcaption">extreme spread</p>
  </div>
  <div class="card">
    <p class="caption">Hold tremor</p>
    <p class="value">{tremorText}</p>
    <p class="subcaption">RMS deviation</p>
  </div>
  <div class="card">
    <p class="caption">{timeOnTarget.caption}</p>
    <p class="value">{timeOnTarget.value}</p>
  </div>
</div>

<style>
  .hero {
    display: flex;
    flex-direction: column;
    gap: 10px;
  }

  .card {
    padding: 12px 16px;
    background: var(--panel-raised);
    border: 1px solid var(--border);
    border-radius: var(--radius);
  }

  .caption {
    margin: 0;
    color: var(--text-dim);
    font-size: 11px;
    letter-spacing: 1px;
    text-transform: uppercase;
  }

  .value {
    margin: 2px 0 0;
    color: var(--text-heading);
    font-size: 28px;
    font-weight: 600;
  }

  .subcaption {
    margin: 2px 0 0;
    color: var(--text-dim);
    font-size: 11px;
  }
</style>
