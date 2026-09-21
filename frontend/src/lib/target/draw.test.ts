import { describe, expect, it } from "vitest";

import type { WireRing } from "../wire/types";
import { drawTarget, type TargetColours } from "./draw";
import { TargetModel } from "./model";

const COLOURS: TargetColours = {
  face: "#181e25",
  ring: "#7a8796",
  label: "#929cab",
  crosshair: "#303c48",
  shot: "#e2e9ed",
  liveAim: "#27ae60",
  holdZone: "#f39c12",
  approach: "#00c83c",
  release: "#ffdc00",
  follow: "#ff4a4a",
};

interface Call {
  method: string;
  args: unknown[];
  strokeStyle: unknown;
  fillStyle: unknown;
  /** The path accumulated since the last beginPath, for stroke calls. */
  path: [number, number][];
}

/** A 2D context that records the drawing calls with the style and path active at each. */
function fakeContext(): { ctx: CanvasRenderingContext2D; calls: Call[] } {
  const calls: Call[] = [];
  const state = { strokeStyle: "", fillStyle: "", lineWidth: 1 };
  let path: [number, number][] = [];
  const record =
    (method: string) =>
    (...args: unknown[]) => {
      if (method === "beginPath") {
        path = [];
      } else if (method === "moveTo" || method === "lineTo") {
        path.push([args[0] as number, args[1] as number]);
      }
      calls.push({
        method,
        args,
        strokeStyle: state.strokeStyle,
        fillStyle: state.fillStyle,
        path: [...path],
      });
    };
  const ctx = new Proxy(state, {
    get(target, prop: string) {
      if (prop in target) {
        return (target as Record<string, unknown>)[prop];
      }
      if (prop === "setLineDash" || prop === "save" || prop === "restore") {
        return () => undefined;
      }
      return record(prop);
    },
    set(target, prop: string, value) {
      (target as Record<string, unknown>)[prop] = value;
      return true;
    },
  }) as unknown as CanvasRenderingContext2D;
  return { ctx, calls };
}

const RINGS: WireRing[] = [
  { diameterMm: 100, label: "1" },
  { diameterMm: 50, label: "X" },
];

function strokes(calls: Call[]): Call[] {
  return calls.filter((call) => call.method === "stroke");
}

describe("drawTarget", () => {
  it("strokes one path for each non-empty trace phase", () => {
    const model = new TargetModel();
    model.setExtent(90);
    model.setTrace([
      [0, 0],
      [1, 1],
      [2, 2],
      [3, 3],
    ]);
    model.setTraceSegments(1, 2);
    const { ctx, calls } = fakeContext();
    drawTarget(ctx, 300, 300, model, RINGS, COLOURS);
    const traceStrokes = strokes(calls).filter((call) =>
      [COLOURS.approach, COLOURS.release, COLOURS.follow].includes(call.strokeStyle as string),
    );
    // One stroked path per phase, not one per segment.
    expect(traceStrokes).toHaveLength(3);

    // The release path begins at the approach's last point so the phases
    // join without a gap.
    const approachStroke = strokes(calls).find((c) => c.strokeStyle === COLOURS.approach);
    const releaseStroke = strokes(calls).find((c) => c.strokeStyle === COLOURS.release);
    expect(releaseStroke?.path[0]).toEqual(approachStroke?.path.at(-1));
  });

  it("hides the live aim dot during replay", () => {
    const model = new TargetModel();
    model.setTrace([
      [0, 0],
      [1, 1],
    ]);
    model.setPlayhead(0);
    const { ctx, calls } = fakeContext();
    drawTarget(ctx, 300, 300, model, RINGS, COLOURS);
    expect(strokes(calls).some((call) => call.strokeStyle === COLOURS.liveAim)).toBe(false);
  });

  it("shows the live aim dot in live view", () => {
    const model = new TargetModel();
    model.appendTracePoint(1, 1);
    const { ctx, calls } = fakeContext();
    drawTarget(ctx, 300, 300, model, RINGS, COLOURS);
    expect(strokes(calls).some((call) => call.strokeStyle === COLOURS.liveAim)).toBe(true);
  });

  it("draws the hold zone only when set", () => {
    const model = new TargetModel();
    const bare = fakeContext();
    drawTarget(bare.ctx, 300, 300, model, RINGS, COLOURS);
    const holdBefore = bare.calls.filter((c) => c.method === "stroke" && c.strokeStyle === COLOURS.holdZone);
    expect(holdBefore).toHaveLength(0);

    model.setHoldZone([0, 0], 5);
    const withZone = fakeContext();
    drawTarget(withZone.ctx, 300, 300, model, RINGS, COLOURS);
    const holdAfter = withZone.calls.filter((c) => c.method === "stroke" && c.strokeStyle === COLOURS.holdZone);
    expect(holdAfter.length).toBeGreaterThan(0);
  });

  it("rings the selected shot with the accent and leaves the rest plain", () => {
    const model = new TargetModel();
    model.setShots([
      { xMm: 1, yMm: 1, label: "1" },
      { xMm: 2, yMm: 2, label: "2" },
    ]);
    const none = fakeContext();
    drawTarget(none.ctx, 300, 300, model, RINGS, COLOURS);
    expect(strokes(none.calls).some((c) => c.strokeStyle === COLOURS.liveAim)).toBe(false);

    model.setSelectedShot(1);
    const withSelection = fakeContext();
    drawTarget(withSelection.ctx, 300, 300, model, RINGS, COLOURS);
    const accentRings = strokes(withSelection.calls).filter((c) => c.strokeStyle === COLOURS.liveAim);
    expect(accentRings).toHaveLength(1);
  });

  it("gates an isolated shot on the playhead reaching it", () => {
    const model = new TargetModel();
    model.setShots([{ xMm: 1, yMm: 1, label: "1" }]);
    model.setSelectedShot(0);
    model.setIsolateSelectedShot(true);
    model.setTraceSegments(null, 2);
    model.setPlayhead(0);
    const before = fakeContext();
    drawTarget(before.ctx, 300, 300, model, RINGS, COLOURS);
    const shotFillsBefore = before.calls.filter((c) => c.method === "fill" && c.fillStyle === COLOURS.shot);
    model.setPlayhead(3);
    const after = fakeContext();
    drawTarget(after.ctx, 300, 300, model, RINGS, COLOURS);
    const shotFillsAfter = after.calls.filter((c) => c.method === "fill" && c.fillStyle === COLOURS.shot);
    expect(shotFillsAfter.length).toBeGreaterThan(shotFillsBefore.length);
  });
});
