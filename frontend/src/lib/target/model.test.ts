import { describe, expect, it } from "vitest";

import { TargetModel, TRACE_CAPACITY } from "./model";

function trace(model: TargetModel): [number, number][] {
  return [...model.approach, ...model.release, ...model.follow];
}

describe("TargetModel trace", () => {
  it("keeps at most the capacity, dropping the oldest point", () => {
    const model = new TargetModel();
    // Points stay within the clip window (4x the 90 mm extent) so the
    // capacity, not the clip, is what trims the trace.
    for (let i = 0; i < TRACE_CAPACITY + 10; i += 1) {
      model.appendTracePoint(i % 100, 0);
    }
    expect(trace(model)).toHaveLength(TRACE_CAPACITY);
    expect(trace(model)[0]?.[0]).toBe(10 % 100);
  });

  it("drops a point beyond four times the extent without breaking the trace", () => {
    const model = new TargetModel();
    model.setExtent(90);
    model.appendTracePoint(1, 1);
    model.appendTracePoint(1000, 0);
    model.appendTracePoint(2, 2);
    expect(trace(model)).toEqual([
      [1, 1],
      [2, 2],
    ]);
  });

  it("bumps the version on every mutation", () => {
    const model = new TargetModel();
    const before = model.version;
    model.appendTracePoint(0, 0);
    expect(model.version).toBeGreaterThan(before);
  });

  it("ignores appends while a saved shot is isolated", () => {
    const model = new TargetModel();
    model.setIsolateSelectedShot(true);
    model.appendTracePoint(1, 1);
    expect(trace(model)).toEqual([]);
  });
});

describe("TargetModel phases", () => {
  it("splits the trace at the release and shot boundaries", () => {
    const model = new TargetModel();
    model.setTrace([
      [0, 0],
      [1, 1],
      [2, 2],
      [3, 3],
      [4, 4],
    ]);
    model.setTraceSegments(1, 3);
    // Boundary sample belongs to the new phase: approach <= 1, release 2..3, follow > 3.
    expect(model.approach).toEqual([
      [0, 0],
      [1, 1],
    ]);
    expect(model.release).toEqual([
      [2, 2],
      [3, 3],
    ]);
    expect(model.follow).toEqual([[4, 4]]);
  });

  it("draws a single colour with no segmentation", () => {
    const model = new TargetModel();
    model.setTrace([
      [0, 0],
      [1, 1],
    ]);
    expect(model.approach).toEqual([
      [0, 0],
      [1, 1],
    ]);
    expect(model.release).toEqual([]);
    expect(model.follow).toEqual([]);
  });
});

describe("TargetModel playhead", () => {
  it("clips the drawn trace to the playhead across phases", () => {
    const model = new TargetModel();
    model.setTrace([
      [0, 0],
      [1, 1],
      [2, 2],
      [3, 3],
      [4, 4],
    ]);
    model.setTraceSegments(1, 3);
    model.setPlayhead(2);
    const visible = model.visibleTrace();
    expect(visible.approach).toEqual([
      [0, 0],
      [1, 1],
    ]);
    expect(visible.release).toEqual([[2, 2]]);
    expect(visible.follow).toEqual([]);
  });

  it("shows the whole trace with no playhead", () => {
    const model = new TargetModel();
    model.setTrace([
      [0, 0],
      [1, 1],
    ]);
    const visible = model.visibleTrace();
    expect(visible.approach).toEqual([
      [0, 0],
      [1, 1],
    ]);
  });
});

it("notifies redraw subscribers and fully clears replay decoration", () => {
  const model = new TargetModel();
  let redraws = 0;
  const detach = model.subscribe(() => { redraws += 1; });
  model.setTrace([[1, 1], [2, 2], [3, 3]]);
  model.setTraceSegments(0, 1);
  model.setHoldZone([2, 2], 3);
  model.clearTrace();
  model.appendTracePoint(4, 4);
  expect(model.approach).toEqual([[4, 4]]);
  expect(model.release).toEqual([]);
  expect(model.follow).toEqual([]);
  expect(model.holdZone).toBeNull();
  expect(redraws).toBe(5);
  detach();
  model.setExtent(10);
  expect(redraws).toBe(5);
});

it("previews the complete saved shot before playback starts", () => {
  const model = new TargetModel();
  model.setTrace([[0, 0], [1, 1], [2, 2], [3, 3]]);
  model.setTraceSegments(1, 2);
  expect(model.visibleTrace()).toEqual({
    approach: [[0, 0], [1, 1]], release: [[2, 2]], follow: [[3, 3]],
  });
  expect(model.playheadReachedShot()).toBe(true);
  model.setPlayhead(0);
  expect(model.playheadReachedShot()).toBe(false);
  expect(model.visibleTrace().follow).toEqual([]);
  model.setPlayhead(2);
  expect(model.playheadReachedShot()).toBe(true);
});


it("colours live release and recoil samples retrospectively", () => {
  const model = new TargetModel();
  model.appendTracePoint(0, 0, 1);
  model.appendTracePoint(1, 1, 1.8);
  model.appendTracePoint(2, 2, 2);
  model.setLiveShotWindows([2], 250, 800);
  model.appendTracePoint(3, 3, 2.033);
  expect(model.approach).toEqual([[0, 0]]);
  expect(model.release).toEqual([[1, 1], [2, 2]]);
  expect(model.follow).toEqual([[3, 3]]);
  model.clearTrace();
  model.appendTracePoint(0, 0, 2);
  expect(model.release).toEqual([]);
});

it("drops the previous shot when the first point after its follow-through arrives", () => {
  const model = new TargetModel();
  model.appendTracePoint(0, 0, 1);
  model.appendTracePoint(2, 2, 2);
  model.setLiveShotWindows([2], 250, 800);
  model.appendTracePoint(3, 3, 2.8);
  model.appendTracePoint(4, 4, 2.9);
  expect(model.approach).toEqual([[4, 4]]);
  expect(model.release).toEqual([]);
  expect(model.follow).toEqual([]);
  expect(model.spentShotLabel).toBeNull();
  model.setShots([{ xMm: 0, yMm: 0, label: "1" }]);
  model.appendTracePoint(5, 5, 3.9);
  model.setLiveShotWindows([2, 3.9], 250, 800);
  model.appendTracePoint(6, 6, 4.8);
  model.appendTracePoint(7, 7, 4.9);
  expect(model.spentShotLabel).toBe("1");
});

