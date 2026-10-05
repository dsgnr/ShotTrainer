import type { WireFrame } from "../wire/types";
import { fitFrame, markerInView, pointInView, reticle, trackingRegion, type Circle } from "./geometry";

const AIM = "#00ff00";
const REJECTED = "#d35400";
const ZERO = "#ff1493";
const ZERO_OUTLINE = "rgba(0, 0, 0, 0.78)";
const RETICLE = "rgba(255, 255, 255, 0.78)";
const REGION = "rgba(255, 255, 255, 0.35)";

function circle(context: CanvasRenderingContext2D, { x, y, radius }: Circle): void {
  context.beginPath();
  context.arc(x, y, radius, 0, Math.PI * 2);
  context.stroke();
}

function line(context: CanvasRenderingContext2D, x1: number, y1: number, x2: number, y2: number): void {
  context.beginPath();
  context.moveTo(x1, y1);
  context.lineTo(x2, y2);
  context.stroke();
}

/**
 * Draws the tracking overlays for one frame over a view of the given size in
 * CSS pixels. The status and manual zero badges are HTML elements in
 * `CameraView.svelte`.
 */
export function drawOverlay(
  context: CanvasRenderingContext2D,
  viewWidth: number,
  viewHeight: number,
  frame: WireFrame,
  regionFraction: number,
): void {
  const fit = fitFrame(frame.width, frame.height, viewWidth, viewHeight);
  if (fit === null) {
    return;
  }

  const aim = markerInView(fit, frame.width, frame.aim);
  if (aim !== null) {
    context.strokeStyle = AIM;
    context.lineWidth = 2;
    circle(context, aim);
    line(context, aim.x - aim.radius - 6, aim.y, aim.x - aim.radius + 2, aim.y);
    line(context, aim.x + aim.radius - 2, aim.y, aim.x + aim.radius + 6, aim.y);
    line(context, aim.x, aim.y - aim.radius - 6, aim.x, aim.y - aim.radius + 2);
    line(context, aim.x, aim.y + aim.radius - 2, aim.x, aim.y + aim.radius + 6);
  }

  const rejected = markerInView(fit, frame.width, frame.rejected);
  if (rejected !== null) {
    const slash = rejected.radius * 0.7;
    context.strokeStyle = REJECTED;
    context.lineWidth = 2;
    context.setLineDash([6, 4]);
    circle(context, rejected);
    line(context, rejected.x - slash, rejected.y + slash, rejected.x + slash, rejected.y - slash);
    context.setLineDash([]);
  }

  const centre = reticle(fit);
  context.strokeStyle = RETICLE;
  context.lineWidth = 1;
  circle(context, centre);
  line(context, centre.x - centre.radius - 6, centre.y, centre.x - centre.gap, centre.y);
  line(context, centre.x + centre.gap, centre.y, centre.x + centre.radius + 6, centre.y);
  line(context, centre.x, centre.y - centre.radius - 6, centre.x, centre.y - centre.gap);
  line(context, centre.x, centre.y + centre.gap, centre.x, centre.y + centre.radius + 6);

  const zero = pointInView(fit, frame.width, frame.zeroPx);
  if (zero !== null) {
    const arm = 9;
    for (const [colour, width] of [
      [ZERO_OUTLINE, 3],
      [ZERO, 2],
    ] as const) {
      context.strokeStyle = colour;
      context.lineWidth = width;
      line(context, zero.x - arm, zero.y, zero.x + arm, zero.y);
      line(context, zero.x, zero.y - arm, zero.x, zero.y + arm);
    }
  }

  const region = trackingRegion(fit, regionFraction);
  if (region !== null) {
    context.strokeStyle = REGION;
    context.lineWidth = 1;
    context.setLineDash([4, 4]);
    context.strokeRect(region.x, region.y, region.width, region.height);
    context.setLineDash([]);
  }
}
