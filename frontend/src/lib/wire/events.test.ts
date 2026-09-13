import { describe, expect, it } from "vitest";

import { EVENT_TYPES, parseEvent } from "./events";
import { finiteOr, finitePair, isFiniteNumber } from "./numbers";
import { SAMPLE_COMMANDS, SAMPLE_EVENTS } from "./samples";

describe("parseEvent", () => {
  it("accepts every event the shell emits", () => {
    for (const sample of Object.values(SAMPLE_EVENTS)) {
      expect(parseEvent(sample)).toBe(sample);
    }
  });

  it("knows exactly the 26 event types", () => {
    expect([...EVENT_TYPES].sort()).toEqual(Object.keys(SAMPLE_EVENTS).sort());
    expect(EVENT_TYPES).toHaveLength(26);
  });

  it("refuses payloads that are not tagged events", () => {
    for (const payload of [
      null,
      undefined,
      "frame",
      3,
      [],
      {},
      { type: 3 },
      { type: "launchMissiles" },
      { type: "toString" },
      { type: "FRAME" },
    ]) {
      expect(parseEvent(payload)).toBeNull();
    }
  });
});

describe("samples", () => {
  it("tag each sample with its own key", () => {
    for (const [key, sample] of Object.entries(SAMPLE_EVENTS)) {
      expect(sample.type).toBe(key);
    }
    for (const [key, sample] of Object.entries(SAMPLE_COMMANDS)) {
      expect(sample.type).toBe(key);
    }
  });

  it("cover the 30 commands the shell accepts", () => {
    expect(Object.keys(SAMPLE_COMMANDS)).toHaveLength(30);
  });
});

describe("numbers that may be null", () => {
  it("treat null and non-finite values as missing", () => {
    expect(isFiniteNumber(0)).toBe(true);
    expect(isFiniteNumber(-2.5)).toBe(true);
    expect(isFiniteNumber(null)).toBe(false);
    expect(isFiniteNumber(undefined)).toBe(false);
    expect(isFiniteNumber(Number.NaN)).toBe(false);
    expect(isFiniteNumber(Number.POSITIVE_INFINITY)).toBe(false);
  });

  it("give a pair only when both numbers are finite", () => {
    expect(finitePair([1, -2])).toEqual([1, -2]);
    expect(finitePair([1, null])).toBeNull();
    expect(finitePair([null, 2])).toBeNull();
    expect(finitePair(null)).toBeNull();
    expect(finitePair(undefined)).toBeNull();
  });

  it("fall back for a missing number", () => {
    expect(finiteOr(3, 0)).toBe(3);
    expect(finiteOr(null, 7)).toBe(7);
  });
});
