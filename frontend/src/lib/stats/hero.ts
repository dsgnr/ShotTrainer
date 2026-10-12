// The headline figures down the right column. The controller sends the shot
// and trace statistics, so these functions format them. Time-on-target is
// computed here from the trace points and the diagnostic ring.
import type { F64, WireAimMetrics, WireRing, WireShotStats, WireTraceStats } from "../wire/types";

/** A narrow non-breaking space, placed between a value and its unit. */
const THIN = "\u202f";

export interface GroupFigure {
  value: string;
  tooltip: string;
}

export interface TimeOnTargetFigure {
  caption: string;
  value: string;
}

/** The total score figure. Dash when empty, the count when nothing scored. */
export function totalScoreFigure(total: F64, shotCount: number): string {
  if (shotCount === 0) {
    return "-";
  }
  if (total === null || total <= 0) {
    return `${shotCount} shots`;
  }
  return formatCompact(total);
}

/** The group size figure, extreme spread with the mean radius on the tooltip. */
export function groupFigure(stats: WireShotStats): GroupFigure {
  if (stats.count === 0) {
    return { value: "-", tooltip: "" };
  }
  const spread = finite(stats.extremeSpreadMm);
  const radius = finite(stats.meanRadiusMm);
  return {
    value: `${spread.toFixed(1)}${THIN}mm`,
    tooltip:
      `Extreme spread: ${spread.toFixed(1)} mm\n` +
      `Mean radius from group centre: ${radius.toFixed(1)} mm`,
  };
}

/** The hold tremor figure. Dash with no trace or no samples. */
export function tremorFigure(stats: WireTraceStats | null): string {
  if (stats === null || stats.samples === 0) {
    return "-";
  }
  return `${finite(stats.holdTremorMm).toFixed(1)}${THIN}mm`;
}

/** The diagnostic rings, the smallest and a mid-sized one. */
export function diagnosticRings(rings: WireRing[]): WireRing[] {
  if (rings.length === 0) {
    return [];
  }
  const sorted = [...rings].sort((a, b) => finite(a.diameterMm) - finite(b.diameterMm));
  if (sorted.length === 1) {
    return [sorted[0]!];
  }
  return [sorted[0]!, sorted[Math.floor(sorted.length / 2)]!];
}

/** The time-on-target figure. The caption names the smallest diagnostic ring. */
export function timeOnTargetFigure(trace: [number, number][], rings: WireRing[]): TimeOnTargetFigure {
  const chosen = diagnosticRings(rings);
  const ring = chosen[0];
  if (ring === undefined) {
    return { caption: "TIME ON TARGET", value: "-" };
  }
  const label = ring.label ?? `${finite(ring.diameterMm).toFixed(0)}${THIN}mm`;
  const caption = `TIME INSIDE ${label}`;
  if (trace.length === 0) {
    return { caption, value: "-" };
  }
  const radius = finite(ring.diameterMm) / 2;
  const inside = trace.filter(([x, y]) => Math.hypot(x, y) <= radius).length;
  return { caption, value: `${Math.round((inside / trace.length) * 100)}%` };
}

export interface AimFigure {
  caption: string;
  value: string;
  /** Whether the figure meets its target, or null when it has none or is empty. */
  met: boolean | null;
}

const AIMING_TIME_TARGET_S = 13;
const HOLD_TARGET_PCT = 90;
const SHOT_OFFSET_TARGET_MM = 3;

function aimFigure(caption: string, value: F64 | undefined, unit: string, digits: number, met: (v: number) => boolean | null): AimFigure {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    return { caption, value: "-", met: null };
  }
  return { caption, value: `${value.toFixed(digits)}${unit}`, met: met(value) };
}

/** The per-shot aiming figures. The custom ring figure appears only when a ring is set. */
export function aimFigures(aim: WireAimMetrics | null, customRingMm: number): AimFigure[] {
  const hold = (v: number) => v >= HOLD_TARGET_PCT;
  const figures = [
    aimFigure("AIMING TIME", aim?.aimingTimeS, `${THIN}s`, 1, (v) => v < AIMING_TIME_TARGET_S),
    aimFigure("STEADY IN 10", aim?.tenRingHoldPct, "%", 0, hold),
    aimFigure("STEADY ON AVERAGE", aim?.meanTenRingHoldPct, "%", 0, hold),
  ];
  if (customRingMm > 0) {
    figures.push(aimFigure(`STEADY IN ${customRingMm}${THIN}mm`, aim?.meanCustomRingHoldPct, "%", 0, () => null));
  }
  figures.push(aimFigure("SHOT OFFSET", aim?.shotOffsetMm, `${THIN}mm`, 1, (v) => v < SHOT_OFFSET_TARGET_MM));
  return figures;
}

function finite(value: F64): number {
  return typeof value === "number" && Number.isFinite(value) ? value : 0;
}

/** A compact number without trailing zeros, such as `97.5` or `100`. */
function formatCompact(value: number): string {
  return Number.parseFloat(value.toPrecision(6)).toString();
}
