import { describe, expect, it, vi } from "vitest";

import { HEADER_LEN, encodePacket } from "./packet";
import { FrameSink } from "./sink";

const packet = encodePacket(
  { width: 2, height: 1, frameId: 5, timestamp: 0.5, sentAtMs: 1 },
  new Uint8Array(8),
);

describe("FrameSink", () => {
  it("draws a packet and reports it drawn", () => {
    const sink = new FrameSink();
    const draw = vi.fn();
    const drawn = vi.fn();
    sink.attach(draw);
    sink.present(packet, drawn);
    expect(draw).toHaveBeenCalledOnce();
    expect(draw.mock.calls[0]?.[0]).toMatchObject({ width: 2, height: 1, frameId: 5 });
    expect(drawn).toHaveBeenCalledOnce();
  });

  it("reports a packet drawn when nothing is attached", () => {
    const drawn = vi.fn();
    new FrameSink().present(packet, drawn);
    expect(drawn).toHaveBeenCalledOnce();
  });

  it("reports a truncated packet or a message without bytes drawn without drawing it", () => {
    const sink = new FrameSink();
    const draw = vi.fn();
    const drawn = vi.fn();
    sink.attach(draw);
    sink.present(packet.slice(0, HEADER_LEN + 4), drawn);
    sink.present("not pixels", drawn);
    expect(draw).not.toHaveBeenCalled();
    expect(drawn).toHaveBeenCalledTimes(2);
  });

  it("reports a packet drawn when drawing it throws", () => {
    const sink = new FrameSink();
    const drawn = vi.fn();
    sink.attach(() => {
      throw new Error("context lost");
    });
    expect(() => sink.present(packet, drawn)).toThrow("context lost");
    expect(drawn).toHaveBeenCalledOnce();
  });

  it("stops drawing once detached, but not when an older draw is detached", () => {
    const sink = new FrameSink();
    const first = vi.fn();
    const second = vi.fn();
    const detachFirst = sink.attach(first);
    const detachSecond = sink.attach(second);
    detachFirst();
    sink.present(packet, () => undefined);
    expect(second).toHaveBeenCalledOnce();
    detachSecond();
    sink.present(packet, () => undefined);
    expect(second).toHaveBeenCalledOnce();
    expect(first).not.toHaveBeenCalled();
  });
});
