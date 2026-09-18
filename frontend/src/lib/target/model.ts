// The target trace, shots and replay state. The painter reads this model and
// redraws when `version` changes.
import { DEFAULT_EXTENT_MM } from "./geometry";

export type TracePoint = [number, number];

export interface ShotMarker {
  xMm: number | null;
  yMm: number | null;
  label: string;
}

export interface VisibleTrace {
  approach: TracePoint[];
  release: TracePoint[];
  follow: TracePoint[];
}

/** Live trace length. Older points fall off the front once it is full. */
export const TRACE_CAPACITY = 600;

/** A noisy detection can land far off the face. Drop points past this multiple of the extent. */
const CLIP_EXTENT_MULTIPLE = 4;

export class TargetModel {
  version = 0;

  #trace: TracePoint[] = [];
  #releaseIndex: number | null = null;
  #shotIndex: number | null = null;
  #playhead: number | null = null;
  #isolate = false;
  #extentMm = DEFAULT_EXTENT_MM;

  shots: ShotMarker[] = [];
  selected: number | null = null;
  liveAim: TracePoint | null = null;
  holdZone: { cx: number; cy: number; radiusMm: number } | null = null;
  shotDiameterMm = 4.5;

  get extentMm(): number {
    return this.#extentMm;
  }

  /** The three phase polylines, split so a boundary sample belongs to the new phase. */
  get approach(): TracePoint[] {
    return this.#phase((i) => this.#phaseAt(i) === 0);
  }

  get release(): TracePoint[] {
    return this.#phase((i) => this.#phaseAt(i) === 1);
  }

  get follow(): TracePoint[] {
    return this.#phase((i) => this.#phaseAt(i) === 2);
  }

  appendTracePoint(xMm: number, yMm: number): void {
    // A saved shot is on display, so live frames must not corrupt its trace.
    if (this.#isolate) {
      return;
    }
    const clip = this.#extentMm * CLIP_EXTENT_MULTIPLE;
    if (Math.abs(xMm) > clip || Math.abs(yMm) > clip) {
      return;
    }
    if (this.#trace.length >= TRACE_CAPACITY) {
      this.#trace.shift();
    }
    this.#trace.push([xMm, yMm]);
    this.liveAim = [xMm, yMm];
    this.#bump();
  }

  setTrace(points: TracePoint[]): void {
    this.#trace = points.map(([x, y]) => [x, y]);
    this.liveAim = this.#trace.at(-1) ?? null;
    this.#playhead = null;
    this.#bump();
  }

  setTraceSegments(releaseIndex: number | null, shotIndex: number | null): void {
    this.#releaseIndex = releaseIndex;
    this.#shotIndex = shotIndex;
    this.#bump();
  }

  setPlayhead(index: number | null): void {
    this.#playhead = index;
    this.#bump();
  }

  setHoldZone(centre: TracePoint | null, radiusMm = 0): void {
    this.holdZone = centre === null || radiusMm <= 0 ? null : { cx: centre[0], cy: centre[1], radiusMm };
    this.#bump();
  }

  clearTrace(): void {
    this.#trace = [];
    this.#playhead = null;
    this.liveAim = null;
    this.#bump();
  }

  setShots(shots: ShotMarker[]): void {
    this.shots = shots;
    this.#bump();
  }

  setSelectedShot(index: number | null): void {
    this.selected = index;
    this.#bump();
  }

  setIsolateSelectedShot(isolate: boolean): void {
    this.#isolate = isolate;
    this.#bump();
  }

  get isolate(): boolean {
    return this.#isolate;
  }

  get playhead(): number | null {
    return this.#playhead;
  }

  setShotDiameter(diameterMm: number): void {
    this.shotDiameterMm = Math.max(0.1, diameterMm);
    this.#bump();
  }

  setExtent(extentMm: number): void {
    this.#extentMm = Math.max(1, extentMm);
    this.#bump();
  }

  /** Whether the replay cursor has reached the shot moment, gating the marker. */
  playheadReachedShot(): boolean {
    if (this.#shotIndex === null) {
      return true;
    }
    if (this.#playhead === null) {
      return false;
    }
    return this.#playhead >= this.#shotIndex;
  }

  /** The three phase polylines clipped to the playhead, as the replay draws them out. */
  visibleTrace(): VisibleTrace {
    const approach = this.approach;
    const release = this.release;
    const follow = this.follow;
    if (this.#playhead === null) {
      return { approach, release, follow };
    }
    const p = Math.max(0, this.#playhead);
    const aLen = approach.length;
    const rLen = release.length;
    if (p < aLen) {
      return { approach: approach.slice(0, p + 1), release: [], follow: [] };
    }
    if (p < aLen + rLen) {
      return { approach, release: release.slice(0, p - aLen + 1), follow: [] };
    }
    return { approach, release, follow: follow.slice(0, p - aLen - rLen + 1) };
  }

  #phaseAt(i: number): 0 | 1 | 2 {
    if (this.#shotIndex !== null && i > this.#shotIndex) {
      return 2;
    }
    if (this.#releaseIndex !== null && i > this.#releaseIndex) {
      return 1;
    }
    return 0;
  }

  #phase(keep: (i: number) => boolean): TracePoint[] {
    const out: TracePoint[] = [];
    for (let i = 0; i < this.#trace.length; i += 1) {
      const point = this.#trace[i];
      if (point !== undefined && keep(i)) {
        out.push(point);
      }
    }
    return out;
  }

  #bump(): void {
    this.version += 1;
  }
}
