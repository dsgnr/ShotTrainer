import { decodePacket, toArrayBuffer, type FramePacket } from "./packet";

export type DrawPixels = (packet: FramePacket) => void;

/**
 * Hands pixel packets from the frame channel to the camera view. The shell
 * holds back further pixels while two packets are unreported, so every
 * packet is reported drawn, including one that cannot be decoded or drawn.
 */
export class FrameSink {
  #draw: DrawPixels | null = null;

  /** Draws later packets with `draw`. The returned function detaches it. */
  attach(draw: DrawPixels): () => void {
    this.#draw = draw;
    return () => {
      if (this.#draw === draw) {
        this.#draw = null;
      }
    };
  }

  present(message: unknown, drawn: () => void): void {
    try {
      const buffer = toArrayBuffer(message);
      const packet = buffer === null ? null : decodePacket(buffer);
      if (packet !== null && this.#draw !== null) {
        this.#draw(packet);
      }
    } finally {
      drawn();
    }
  }
}
