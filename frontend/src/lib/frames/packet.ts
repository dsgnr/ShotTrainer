// The binary packet the shell sends on the frame channel, written by
// `rgba_packet` in `src-tauri/src/pixels.rs`. A 32 byte little-endian header
// is followed by RGBA rows from the top.
//
// | Offset | Type | Field |
// | 0      | u32  | width |
// | 4      | u32  | height |
// | 8      | i64  | frame id, matching the `frame` event |
// | 16     | f64  | capture time in seconds on the controller clock |
// | 24     | f64  | send time in milliseconds since the Unix epoch |

export const HEADER_LEN = 32;

export interface FramePacket {
  width: number;
  height: number;
  frameId: number;
  timestamp: number;
  sentAtMs: number;
  /** `width * height * 4` bytes, a view into the received buffer. */
  pixels: Uint8ClampedArray<ArrayBuffer>;
}

/**
 * The bytes of a channel message. Tauri delivers a raw body as an
 * `ArrayBuffer`, and older paths deliver a typed array or a plain array of
 * numbers.
 */
export function toArrayBuffer(message: unknown): ArrayBuffer | null {
  if (message instanceof ArrayBuffer) {
    return message;
  }
  if (ArrayBuffer.isView(message)) {
    const bytes = new Uint8Array(message.byteLength);
    bytes.set(new Uint8Array(message.buffer, message.byteOffset, message.byteLength));
    return bytes.buffer;
  }
  if (Array.isArray(message) && message.every((value) => typeof value === "number")) {
    return Uint8Array.from(message).buffer;
  }
  return null;
}

/** The packet, or `null` when it is too short or has no pixels. */
export function decodePacket(buffer: ArrayBuffer): FramePacket | null {
  if (buffer.byteLength < HEADER_LEN) {
    return null;
  }
  const view = new DataView(buffer);
  const width = view.getUint32(0, true);
  const height = view.getUint32(4, true);
  const length = width * height * 4;
  if (length === 0 || buffer.byteLength < HEADER_LEN + length) {
    return null;
  }
  return {
    width,
    height,
    frameId: Number(view.getBigInt64(8, true)),
    timestamp: view.getFloat64(16, true),
    sentAtMs: view.getFloat64(24, true),
    pixels: new Uint8ClampedArray(buffer, HEADER_LEN, length),
  };
}

/** A packet in the shell's layout, for the browser mock and the tests. */
export function encodePacket(
  header: Omit<FramePacket, "pixels">,
  pixels: Uint8Array | Uint8ClampedArray,
): ArrayBuffer {
  const buffer = new ArrayBuffer(HEADER_LEN + pixels.byteLength);
  const view = new DataView(buffer);
  view.setUint32(0, header.width, true);
  view.setUint32(4, header.height, true);
  view.setBigInt64(8, BigInt(header.frameId), true);
  view.setFloat64(16, header.timestamp, true);
  view.setFloat64(24, header.sentAtMs, true);
  new Uint8Array(buffer, HEADER_LEN).set(pixels);
  return buffer;
}
