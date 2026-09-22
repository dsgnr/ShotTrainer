import { decodePacket, toArrayBuffer, type FramePacket } from "./packet";

export type DrawPixels = (packet: FramePacket) => void;

/**
 * Hands pixel packets from the frame channel to the camera view. The shell
 * holds back further pixels while two packets are unreported, so every
 * packet is reported drawn, including one that cannot be decoded or drawn.
 */
export class FrameSink {
  #draws = new Set<DrawPixels>();

  /** Draws later packets with `draw`. The returned function detaches it. */
  attach(draw: DrawPixels): () => void {
    this.#draws.add(draw);
    return () => { this.#draws.delete(draw); };
  }

  present(message: unknown, drawn: () => void): void {
    try {
      const buffer = toArrayBuffer(message);
      const packet = buffer === null ? null : decodePacket(buffer);
      if (packet !== null) {
        for (const draw of this.#draws) {
          try { draw(packet); } catch { /* Other views still receive the packet. */ }
        }
      }
    } finally {
      drawn();
    }
  }
}
