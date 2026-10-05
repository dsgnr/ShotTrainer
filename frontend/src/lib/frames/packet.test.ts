import { describe, expect, it } from "vitest";

import { HEADER_LEN, decodePacket, encodePacket, toArrayBuffer } from "./packet";

// `rgba_packet` for a 3 by 2 frame with id 41, captured at 12.5 s and sent
// at 1_700_000_000_123 ms, as in `header_carries_size_id_and_both_times`.
const RUST_HEADER = [
  3, 0, 0, 0, 2, 0, 0, 0, 41, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 41, 64, 0, 176, 135, 86, 254,
  188, 120, 66,
];

function rustPacket(): ArrayBuffer {
  const bytes = new Uint8Array(HEADER_LEN + 3 * 2 * 4);
  bytes.set(RUST_HEADER);
  for (let i = HEADER_LEN; i < bytes.length; i += 1) {
    bytes[i] = i - HEADER_LEN;
  }
  return bytes.buffer;
}

describe("decodePacket", () => {
  it("reads the header the shell writes", () => {
    const packet = decodePacket(rustPacket());
    expect(packet).not.toBeNull();
    expect(packet?.width).toBe(3);
    expect(packet?.height).toBe(2);
    expect(packet?.frameId).toBe(41);
    expect(packet?.timestamp).toBe(12.5);
    expect(packet?.sentAtMs).toBe(1_700_000_000_123);
  });

  it("gives the RGBA bytes after the header", () => {
    const pixels = decodePacket(rustPacket())?.pixels;
    expect(pixels?.length).toBe(24);
    expect(pixels?.[0]).toBe(0);
    expect(pixels?.[23]).toBe(23);
  });

  it("refuses a packet shorter than its header or its pixels", () => {
    expect(decodePacket(new ArrayBuffer(HEADER_LEN - 1))).toBeNull();
    expect(decodePacket(rustPacket().slice(0, HEADER_LEN + 23))).toBeNull();
  });

  it("refuses a frame without pixels", () => {
    const empty = encodePacket({ width: 0, height: 0, frameId: 7, timestamp: 1, sentAtMs: 2 }, new Uint8Array());
    expect(empty.byteLength).toBe(HEADER_LEN);
    expect(decodePacket(empty)).toBeNull();
  });
});

describe("encodePacket", () => {
  it("writes the shell's layout", () => {
    const pixels = new Uint8Array(24).map((_, i) => i);
    const buffer = encodePacket(
      { width: 3, height: 2, frameId: 41, timestamp: 12.5, sentAtMs: 1_700_000_000_123 },
      pixels,
    );
    expect([...new Uint8Array(buffer)]).toEqual([...new Uint8Array(rustPacket())]);
  });
});

describe("toArrayBuffer", () => {
  it("passes an ArrayBuffer through", () => {
    const buffer = new ArrayBuffer(4);
    expect(toArrayBuffer(buffer)).toBe(buffer);
  });

  it("copies only the viewed bytes of a typed array", () => {
    const view = new Uint8Array([9, 1, 2, 9]).subarray(1, 3);
    expect([...new Uint8Array(toArrayBuffer(view) ?? new ArrayBuffer(0))]).toEqual([1, 2]);
  });

  it("accepts an array of byte values", () => {
    expect([...new Uint8Array(toArrayBuffer([1, 2, 255]) ?? new ArrayBuffer(0))]).toEqual([1, 2, 255]);
  });

  it("refuses anything else", () => {
    for (const message of [null, undefined, "pixels", 3, { width: 1 }, [1, "2"]]) {
      expect(toArrayBuffer(message)).toBeNull();
    }
  });
});
