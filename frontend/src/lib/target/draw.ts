// Target rendering, ported from the paint methods of `target_view.py`. The
// function is pure given a context, so it is tested against a recording fake.
import type { WireRing } from "../wire/types";
import { targetScale } from "./geometry";
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

/** Draw the target, its rings, trace, shots and live aim into a view of the given CSS size. */
export function drawTarget(
  ctx: CanvasRenderingContext2D,
  width: number,
  height: number,
  model: TargetModel,
  rings: WireRing[],
  colours: TargetColours,
): void {
  const size = Math.min(width, height);
  const cx = width / 2;
  const cy = height / 2;
  const scale = targetScale(size, model.extentMm);

  ctx.clearRect(0, 0, width, height);

  // A low-contrast dark face keeps the coloured trace in focus.
  const faceRadius = model.extentMm * scale * 0.95;
  ctx.beginPath();
  ctx.arc(cx, cy, faceRadius, 0, Math.PI * 2);
  ctx.fillStyle = colours.face;
  ctx.fill();
  ctx.strokeStyle = colours.ring;
  ctx.lineWidth = 1;
  ctx.stroke();

  drawRings(ctx, cx, cy, scale, rings, colours);
  drawCrosshair(ctx, cx, cy, size, colours);
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
  ctx.strokeStyle = colours.ring;
  ctx.lineWidth = 1;
  for (const ring of rings) {
    if (ring.diameterMm === null) {
      continue;
    }
    const r = (ring.diameterMm / 2) * scale;
    ctx.beginPath();
    ctx.arc(cx, cy, r, 0, Math.PI * 2);
    ctx.stroke();
    if (ring.label !== null && ring.label !== "") {
      ctx.fillStyle = colours.label;
      ctx.fillText(ring.label, cx + r - 6, cy);
    }
  }
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
    if (shot.label !== "") {
      ctx.fillStyle = colours.ring;
      ctx.fillText(shot.label, x + r + 4, y);
    }
  });
}

function strokePolyline(ctx: CanvasRenderingContext2D, points: TracePoint[], colour: string): void {
  if (points.length === 0) {
    return;
  }
  ctx.strokeStyle = colour;
  ctx.lineWidth = 8;
  ctx.lineCap = "round";
  ctx.lineJoin = "round";
  ctx.beginPath();
  points.forEach(([x, y], i) => {
    if (i === 0) {
      ctx.moveTo(x, y);
    } else {
      ctx.lineTo(x, y);
    }
  });
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
  const visible = model.visibleTrace();
  // The three phases join at their boundary sample, so a release point is
  // repeated at the end of the approach path and the start of the release
  // path. Python drew them as separate polylines, which left a gap.
  const toView = (points: TracePoint[]): TracePoint[] =>
    points.map(([x, y]) => [cx + x * scale, cy + y * scale]);
  const approach = toView(visible.approach);
  const release = toView(visible.release);
  const follow = toView(visible.follow);
  const bridge = (a: TracePoint[], b: TracePoint[]): TracePoint[] => {
    const last = a.at(-1);
    return last !== undefined && b.length > 0 ? [last, ...b] : b;
  };
  strokePolyline(ctx, approach, colours.approach);
  strokePolyline(ctx, bridge(approach, release), colours.release);
  strokePolyline(ctx, bridge(release.length > 0 ? release : approach, follow), colours.follow);
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
