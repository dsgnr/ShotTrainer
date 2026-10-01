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
  font: string;
  textAlign: string;
  textBaseline: string;
  lineWidth: number;
  /** The path accumulated since the last beginPath, for stroke calls. */
  path: [number, number][];
}

/** A 2D context that records the drawing calls with the style and path active at each. */
function fakeContext(): { ctx: CanvasRenderingContext2D; calls: Call[] } {
  const calls: Call[] = [];
  const state = { strokeStyle: "", fillStyle: "", lineWidth: 1, font: "", textAlign: "left", textBaseline: "alphabetic" };
  let path: [number, number][] = [];
  const record =
    (method: string) =>
    (...args: unknown[]) => {
      if (method === "beginPath") {
        path = [];
      } else if (method === "moveTo" || method === "lineTo") {
        path.push([args[0] as number, args[1] as number]);
      }
      if (method === "bezierCurveTo") path.push([args[4] as number, args[5] as number]);
      calls.push({
        method,
        args,
        strokeStyle: state.strokeStyle,
        fillStyle: state.fillStyle,
        font: state.font,
        textAlign: state.textAlign,
        textBaseline: state.textBaseline,
        lineWidth: state.lineWidth,
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

it("zooms the face, rings and shot coordinates together around a fixed centre", () => {
  const model = new TargetModel();
  model.setShots([{ xMm: 10, yMm: -5, label: "1" }]);
  const wide = fakeContext();
  const close = fakeContext();
  drawTarget(wide.ctx, 416, 416, model, RINGS, COLOURS, 100);
  drawTarget(close.ctx, 416, 416, model, RINGS, COLOURS, 50);
  const before = wide.calls.filter((call) => call.method === "arc");
  const after = close.calls.filter((call) => call.method === "arc");
  for (let i = 0; i < before.length; i++) {
    const a = before[i]!.args as number[];
    const b = after[i]!.args as number[];
    expect(b[0]! - 208).toBeCloseTo((a[0]! - 208) * 2);
    expect(b[1]! - 208).toBeCloseTo((a[1]! - 208) * 2);
    expect(b[2]).toBeCloseTo(a[2]! * 2);
  }
});

it("uses the same translated origin for target rings and session shot markers", () => {
  const model = new TargetModel();
  model.setShots([{ xMm: 10, yMm: -5, label: "1" }]);
  const { ctx, calls } = fakeContext();
  drawTarget(ctx, 416, 416, model, RINGS, COLOURS, 100, [10, -5]);
  const arcs = calls.filter((call) => call.method === "arc");
  expect(arcs[0]!.args.slice(0, 2)).toEqual([188, 218]);
  expect(arcs.at(-1)!.args.slice(0, 2)).toEqual([208, 208]);
});

it.each([50, 100])("centres readable labels within scoring bands at extent %d", (extent) => {
  const rings: WireRing[] = [
    { diameterMm: 100, label: "7" },
    { diameterMm: null, label: "unknown" },
    { diameterMm: 20, label: "X" },
    { diameterMm: 60, label: "9" },
    { diameterMm: 40, label: null },
  ];
  const original = structuredClone(rings);
  const model = new TargetModel();
  const { ctx, calls } = fakeContext();
  drawTarget(ctx, 416, 416, model, rings, COLOURS, extent, [10, -5]);
  const scale = 200 / extent;
  const cx = 208 - 10 * scale;
  const cy = 208 + 5 * scale;
  const labels = calls.filter((call) => call.method === "fillText");
  expect(labels.map((call) => call.args)).toEqual([
    ["X", cx, cy], ["9", cx + 25 * scale, cy], ["7", cx + 40 * scale, cy],
  ]);
  for (const label of labels) {
    expect(label.font).toContain("600 14px");
    expect(label.textAlign).toBe("center");
    expect(label.textBaseline).toBe("middle");
    const halo = calls[calls.indexOf(label) - 1]!;
    expect(halo.method).toBe("strokeText");
    expect(halo.args).toEqual(label.args);
    expect(halo.strokeStyle).toBe(COLOURS.face);
    expect(halo.lineWidth).toBe(4);
  }
  expect(rings).toEqual(original);
});

 it("scales thin trace strokes with zoom and caps extreme widths", () => {
  const widths = [200, 100, 50, 5].map((extent) => {
    const model = new TargetModel();
    model.setExtent(extent);
    model.setTrace([[0, 0], [1, 1], [2, 2], [3, 3]]);
    model.setTraceSegments(1, 2);
    const { ctx, calls } = fakeContext();
    drawTarget(ctx, 416, 416, model, RINGS, COLOURS);
    const phases = strokes(calls).filter((call) =>
      [COLOURS.approach, COLOURS.release, COLOURS.follow].includes(call.strokeStyle as string));
    expect(phases).toHaveLength(3);
    expect(new Set(phases.map((call) => call.lineWidth)).size).toBe(1);
    return phases[0]!.lineWidth;
  });
  expect(widths).toEqual([0.5, 0.8, 1.6, 3]);
});


it("draws live shot colours in chronological runs without joining separate approaches", () => {
  const model = new TargetModel();
  for (const [i, timestamp] of [1, 1.8, 2, 2.1, 3, 3.8, 4, 4.1].entries()) model.appendTracePoint(i, 0, timestamp);
  model.setLiveShotWindows([2, 4], 250, 800);
  const {ctx, calls} = fakeContext();
  drawTarget(ctx, 300, 300, model, RINGS, COLOURS);
  const paths = strokes(calls).filter(call => [COLOURS.approach, COLOURS.release, COLOURS.follow].includes(call.strokeStyle as string));
  expect(paths.map(call => call.strokeStyle)).toEqual([COLOURS.approach, COLOURS.release, COLOURS.follow, COLOURS.approach, COLOURS.release, COLOURS.follow]);
  for (let i = 1; i < paths.length; i++) expect(paths[i]!.path[0]).toEqual(paths[i - 1]!.path.at(-1));
});


it("smooths trace segments through their sampled positions", () => {
  const model = new TargetModel();
  model.setExtent(50);
  model.setTrace([[0, 0], [10, 10], [20, 0], [30, -10]]);
  const {ctx, calls} = fakeContext();
  drawTarget(ctx, 116, 116, model, RINGS, COLOURS);
  const curves = calls.filter(call => call.method === "bezierCurveTo" && call.strokeStyle === COLOURS.approach);
  expect(curves.map(call => call.args.slice(4))).toEqual([[68, 68], [78, 58], [88, 48]]);
  expect(curves[0]!.args.slice(2, 4)).toEqual(curves[1]!.args.slice(0, 2).map((value, i) => 2 * [68, 68][i]! - Number(value)));
});
