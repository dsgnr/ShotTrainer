// Target rendering. The function is pure given a context, so it is tested
// against a recording fake.
import type { WireRing } from "../wire/types";
import { DEFAULT_EXTENT_MM, targetScale } from "./geometry";
import type { TargetModel, TracePoint } from "./model";

export interface TargetColours {
  face: string;
  ring: string;
  label: string;
  crosshair: string;
  shot: string;
  liveAim: string;
  holdZone: string;
  approach: string;
  release: string;
  follow: string;
}

/** Shot labels use a compact technical face at a fixed pixel size. */
const LABEL_PX = 10;
const RING_LABEL_PX = 14;
const LABEL_FONT = 'ui-monospace, "SF Mono", "Cascadia Code", monospace';

/** Draw the target, its rings, trace, shots and live aim into a view of the given CSS size. */
export function drawTarget(
  ctx: CanvasRenderingContext2D,
  width: number,
  height: number,
  model: TargetModel,
  rings: WireRing[],
  colours: TargetColours,
  extentMm = model.extentMm,
  centre: readonly [number, number] = [0, 0],
): void {
  const size = Math.min(width, height);
  const scale = targetScale(size, extentMm);
  const cx = width / 2 - centre[0] * scale;
  const cy = height / 2 - centre[1] * scale;

  ctx.clearRect(0, 0, width, height);

  const outerRadius = Math.max(0, ...rings.map((ring) => (ring.diameterMm ?? 0) / 2));
  const faceRadius = (outerRadius || DEFAULT_EXTENT_MM * 0.95) * scale;
  ctx.beginPath();
  ctx.arc(cx, cy, faceRadius, 0, Math.PI * 2);
  ctx.fillStyle = colours.face;
  ctx.fill();
  ctx.strokeStyle = colours.ring;
  ctx.lineWidth = 1;
  ctx.stroke();

  drawCrosshair(ctx, cx, cy, faceRadius * 2, colours);
  drawRings(ctx, cx, cy, scale, rings, colours);
  drawHoldZone(ctx, cx, cy, scale, model, colours);
  drawShots(ctx, cx, cy, scale, model, colours);
  drawTrace(ctx, cx, cy, scale, model, colours);
  drawLiveAim(ctx, cx, cy, scale, model, colours);
}

function drawRings(
  ctx: CanvasRenderingContext2D,
  cx: number,
  cy: number,
  scale: number,
  rings: WireRing[],
  colours: TargetColours,
): void {
  const ordered = rings.filter((ring): ring is WireRing & { diameterMm: number } =>
    ring.diameterMm !== null,
  ).sort((a, b) => a.diameterMm - b.diameterMm);
  ctx.strokeStyle = colours.ring;
  ctx.lineWidth = 1;
  for (const ring of ordered) {
    ctx.beginPath();
    ctx.arc(cx, cy, ring.diameterMm / 2 * scale, 0, Math.PI * 2);
    ctx.stroke();
  }

  ctx.font = `600 ${RING_LABEL_PX}px ${LABEL_FONT}`;
  ctx.textBaseline = "middle";
  ctx.textAlign = "center";
  ctx.fillStyle = colours.label;
  ctx.strokeStyle = colours.face;
  ctx.lineWidth = 4;
  ctx.lineJoin = "round";
  ordered.forEach((ring, index) => {
    if (ring.label === null || ring.label === "") return;
    const innerDiameter = ordered[index - 1]?.diameterMm ?? 0;
    const x = index === 0 ? cx : cx + (innerDiameter + ring.diameterMm) / 4 * scale;
    ctx.strokeText(ring.label, x, cy);
    ctx.fillText(ring.label, x, cy);
  });
  ctx.textAlign = "left";
  ctx.textBaseline = "alphabetic";
}

function drawCrosshair(
  ctx: CanvasRenderingContext2D,
  cx: number,
  cy: number,
  size: number,
  colours: TargetColours,
): void {
  ctx.strokeStyle = colours.crosshair;
  ctx.lineWidth = 1;
  ctx.setLineDash([4, 4]);
  ctx.beginPath();
  ctx.moveTo(cx - size / 2, cy);
  ctx.lineTo(cx + size / 2, cy);
  ctx.moveTo(cx, cy - size / 2);
  ctx.lineTo(cx, cy + size / 2);
  ctx.stroke();
  ctx.setLineDash([]);
}

function drawHoldZone(
  ctx: CanvasRenderingContext2D,
  cx: number,
  cy: number,
  scale: number,
  model: TargetModel,
  colours: TargetColours,
): void {
  const zone = model.holdZone;
  if (zone === null) {
    return;
  }
  const r = zone.radiusMm * scale;
  ctx.beginPath();
  ctx.arc(cx + zone.cx * scale, cy + zone.cy * scale, r, 0, Math.PI * 2);
  ctx.fillStyle = colours.holdZone;
  ctx.globalAlpha = 0.16;
  ctx.fill();
  ctx.globalAlpha = 1;
  ctx.strokeStyle = colours.holdZone;
  ctx.lineWidth = 1;
  ctx.setLineDash([5, 4]);
  ctx.stroke();
  ctx.setLineDash([]);
}

function drawShots(
  ctx: CanvasRenderingContext2D,
  cx: number,
  cy: number,
  scale: number,
  model: TargetModel,
  colours: TargetColours,
): void {
  const diameterPx = Math.max(4, model.shotDiameterMm * scale);
  const radiusPx = diameterPx / 2;
  model.shots.forEach((shot, i) => {
    if (shot.xMm === null || shot.yMm === null) {
      return;
    }
    if (model.isolate) {
      if (i !== model.selected || !model.playheadReachedShot()) {
        return;
      }
    }
    const x = cx + shot.xMm * scale;
    const y = cy + shot.yMm * scale;
    const selected = i === model.selected;
    const r = radiusPx * (selected ? 1.5 : 1.3);
    ctx.beginPath();
    ctx.arc(x, y, r, 0, Math.PI * 2);
    ctx.fillStyle = colours.shot;
    ctx.fill();
    // The selected shot wears a thin accent ring so it reads at a glance.
    if (selected) {
      ctx.strokeStyle = colours.liveAim;
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      ctx.arc(x, y, r + 2.5, 0, Math.PI * 2);
      ctx.stroke();
    }
    if (shot.label !== "") {
      ctx.fillStyle = colours.label;
      ctx.font = `${LABEL_PX}px ${LABEL_FONT}`;
      ctx.textBaseline = "middle";
      ctx.fillText(shot.label, x + r + 4, y);
      ctx.textBaseline = "alphabetic";
    }
  });
}

function strokePolyline(ctx: CanvasRenderingContext2D, points: TracePoint[], colour: string, width: number): void {
  if (points.length === 0) {
    return;
  }
  ctx.strokeStyle = colour;
  ctx.lineWidth = width;
  ctx.lineCap = "round";
  ctx.lineJoin = "round";
  ctx.beginPath();
  ctx.moveTo(points[0]![0], points[0]![1]);
  for (let i = 1; i < points.length; i++) {
    const before = points[Math.max(0, i - 2)]!;
    const start = points[i - 1]!;
    const end = points[i]!;
    const after = points[Math.min(points.length - 1, i + 1)]!;
    ctx.bezierCurveTo(
      start[0] + (end[0] - before[0]) / 6,
      start[1] + (end[1] - before[1]) / 6,
      end[0] - (after[0] - start[0]) / 6,
      end[1] - (after[1] - start[1]) / 6,
      end[0], end[1],
    );
  }
  ctx.stroke();
}

function drawTrace(
  ctx: CanvasRenderingContext2D,
  cx: number,
  cy: number,
  scale: number,
  model: TargetModel,
  colours: TargetColours,
): void {
  const palette = [colours.approach, colours.release, colours.follow];
  const width = Math.max(0.5, Math.min(3, scale * 0.4));
  for (const run of model.visibleTraceRuns()) {
    const points: TracePoint[] = run.points.map(([x, y]) => [cx + x * scale, cy + y * scale]);
    strokePolyline(ctx, points, palette[run.phase]!, width);
  }
}

function drawLiveAim(
  ctx: CanvasRenderingContext2D,
  cx: number,
  cy: number,
  scale: number,
  model: TargetModel,
  colours: TargetColours,
): void {
  // The replay's progressive trace already shows the aim at the playhead, so
  // a stale dot from the end of the recorded trace is hidden there.
  if (model.liveAim === null || model.playhead !== null || model.isolate) {
    return;
  }
  const x = cx + model.liveAim[0] * scale;
  const y = cy + model.liveAim[1] * scale;
  ctx.strokeStyle = colours.liveAim;
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.arc(x, y, 5, 0, Math.PI * 2);
  ctx.stroke();
}
