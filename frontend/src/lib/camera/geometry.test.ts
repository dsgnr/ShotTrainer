import { describe, expect, it } from "vitest";

import { initialCamera } from "../stores/camera";
import { SAMPLE_EVENTS } from "../wire/samples";
import { MIN_MARKER_RADIUS, fitFrame, markerInView, pointInView, reticle, trackingRegion } from "./geometry";
import { statusBadge } from "./status";

describe("fitFrame", () => {
  it("centres a frame in a wider view at full height", () => {
    expect(fitFrame(640, 480, 400, 240)).toEqual({ x: 40, y: 0, width: 320, height: 240 });
  });

  it("centres a frame in a taller view at full width", () => {
    expect(fitFrame(640, 480, 320, 400)).toEqual({ x: 0, y: 80, width: 320, height: 240 });
  });

  it("has no position while a size is unknown", () => {
    expect(fitFrame(0, 480, 320, 240)).toBeNull();
    expect(fitFrame(640, 480, 0, 240)).toBeNull();
  });
});

describe("markers", () => {
  const fit = { x: 10, y: 20, width: 320, height: 240 };

  it("scale a marker from frame to view pixels", () => {
    expect(markerInView(fit, 640, { xPx: 320, yPx: 240, radiusPx: 40 })).toEqual({ x: 170, y: 140, radius: 20 });
  });

  it("keep a small marker visible", () => {
    expect(markerInView(fit, 640, { xPx: 0, yPx: 0, radiusPx: 2 })?.radius).toBe(MIN_MARKER_RADIUS);
    expect(markerInView(fit, 640, { xPx: 0, yPx: 0, radiusPx: null })?.radius).toBe(MIN_MARKER_RADIUS);
  });

  it("are not drawn without a finite position", () => {
    expect(markerInView(fit, 640, null)).toBeNull();
    expect(markerInView(fit, 640, { xPx: null, yPx: 10, radiusPx: 5 })).toBeNull();
    expect(markerInView(fit, 640, { xPx: 10, yPx: Number.NaN, radiusPx: 5 })).toBeNull();
    expect(pointInView(fit, 640, [1, null])).toBeNull();
    expect(pointInView(fit, 640, null)).toBeNull();
    expect(pointInView(fit, 640, [64, 32])).toEqual({ x: 42, y: 36 });
  });
});

describe("reticle", () => {
  it("is at least 20 pixels across and 5 % of a large view", () => {
    expect(reticle({ x: 0, y: 0, width: 200, height: 100 })).toEqual({ x: 100, y: 50, radius: 20, gap: 7 });
    expect(reticle({ x: 0, y: 0, width: 1000, height: 800 }).radius).toBe(40);
  });
});

describe("trackingRegion", () => {
  const fit = { x: 0, y: 0, width: 400, height: 300 };

  it("is the given fraction of the frame, centred", () => {
    const region = trackingRegion(fit, 0.5);
    expect(region).toEqual({ x: 100, y: 75, width: 200, height: 150 });
  });

  it("is hidden when it covers the whole frame", () => {
    expect(trackingRegion(fit, 1)).toBeNull();
    expect(trackingRegion(fit, 0.9995)).toBeNull();
    expect(trackingRegion(fit, 3)).toBeNull();
  });

  it("is never smaller than 5 % of the frame", () => {
    expect(trackingRegion(fit, 0.01)?.width).toBeCloseTo(20);
  });
});

describe("statusBadge", () => {
  it("shows the frame's tracking status in Python's words", () => {
    const frame = { ...SAMPLE_EVENTS.frame, status: "lost" as const };
    expect(statusBadge({ frame, idle: false })).toEqual({ label: "No target", colour: "#e67e22" });
    expect(statusBadge({ frame: SAMPLE_EVENTS.frame, idle: false })?.label).toBe("Outside region");
  });

  it("shows idle once the camera stops and nothing before the first frame", () => {
    expect(statusBadge({ frame: null, idle: true })?.label).toBe("Idle");
    expect(statusBadge(initialCamera)).toBeNull();
  });
});
