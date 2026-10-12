// The hold trace the browser preview sends for a selected shot. It mirrors
// the controller's figures closely enough for the preview and the docs media.
import type { WireHoldTrace, WireRing } from "../wire/types";

type Sample = { timestamp: number; point: [number, number] };

const mean = (values: number[]) => values.reduce((a, b) => a + b, 0) / values.length;

export function mockHoldTrace(
  trace: Sample[],
  shotTs: number,
  shotMm: [number, number] | null,
  rings: WireRing[],
  customRingMm: number,
  preShotMs: number,
): WireHoldTrace {
  const before = trace.filter((s) => s.timestamp <= shotTs);
  const points = before.filter((s) => s.timestamp >= shotTs - preShotMs / 1000).map((s) => s.point);
  const [mx, my] = [mean(points.map((p) => p[0])), mean(points.map((p) => p[1]))];
  const dist = (p: [number, number], c: [number, number] = [0, 0]) => Math.hypot(p[0] - c[0], p[1] - c[1]);
  const stats = {
    samples: points.length,
    holdTremorMm: points.length ? Math.sqrt(mean(points.map((p) => dist(p, [mx, my]) ** 2))) : 0,
    traceLengthMm: points.slice(1).reduce((sum, p, i) => sum + dist(p, points[i]!), 0),
    meanXMm: points.length ? mx : 0,
    meanYMm: points.length ? my : 0,
  };

  const radii = rings.map((r) => (r.diameterMm ?? 0) / 2);
  const tens = rings.filter((r) => r.label === "X" || Number(r.label) === 10).map((r) => (r.diameterMm ?? 0) / 2);
  if (radii.length === 0 || tens.length === 0) return { points, stats, aim: null };
  const outer = Math.max(...radii);
  const ten = Math.max(...tens);

  let start = before.length;
  while (start > 0 && dist(before[start - 1]!.point) <= outer) start -= 1;
  const last = before.filter((s) => s.timestamp >= shotTs - 1).map((s) => s.point);
  const pct = (centre: [number, number], radius: number) =>
    last.length ? (100 * last.filter((p) => dist(p, centre) <= radius).length) / last.length : null;
  const centre: [number, number] = last.length ? [mean(last.map((p) => p[0])), mean(last.map((p) => p[1]))] : [0, 0];
  return {
    points,
    stats,
    aim: {
      aimingTimeS: start < before.length ? shotTs - before[start]!.timestamp : null,
      tenRingHoldPct: pct([0, 0], ten),
      meanTenRingHoldPct: pct(centre, ten),
      meanCustomRingHoldPct: customRingMm > 0 ? pct(centre, customRingMm / 2) : null,
      shotOffsetMm: shotMm !== null && last.length ? dist(shotMm, centre) : null,
    },
  };
}
