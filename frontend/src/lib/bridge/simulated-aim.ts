import { RECORDED_AIM } from "./recorded-aim";

/** Seconds into the recording at which the shot fires. The follow-through starts here. */
const SHOT_AT = 8.067;
const RECORDING_END = RECORDED_AIM[RECORDED_AIM.length - 1]![0];
const FOLLOW_SECONDS = RECORDING_END - SHOT_AT;
/** Cycle phase at which the recording starts, so that its shot lands on the 10 second boundary. */
const APPROACH_START = 10 - SHOT_AT;

function uniform(seed: number): number {
  let value = (seed + 0x9e3779b9) >>> 0;
  value = Math.imul(value ^ (value >>> 16), 0x21f0aaad) >>> 0;
  value = Math.imul(value ^ (value >>> 15), 0x735a2d97) >>> 0;
  return ((value ^ (value >>> 15)) >>> 0) / 4294967296;
}
function recorded(seconds: number): [number, number] {
  const time = Math.min(RECORDING_END, Math.max(0, seconds));
  let low = 0;
  let high = RECORDED_AIM.length - 1;
  while (high - low > 1) {
    const middle = (low + high) >> 1;
    if (RECORDED_AIM[middle]![0] <= time) low = middle;
    else high = middle;
  }
  const from = RECORDED_AIM[low]!;
  const to = RECORDED_AIM[high]!;
  const p = to[0] === from[0] ? 0 : (time - from[0]) / (to[0] - from[0]);
  return [from[1] + (to[1] - from[1]) * p, from[2] + (to[2] - from[2]) * p];
}

export function simulatedAim(seconds: number): [number, number] {
  const shot = Math.floor(seconds / 10);
  const phase = seconds % 10;
  // The follow-through ends with the post-shot window. The next approach then starts off target, not at the last shot.
  const following = shot > 0 && phase <= FOLLOW_SECONDS;
  return recorded(following ? SHOT_AT + phase : phase - APPROACH_START);
}

/** Where the preview records each shot. The centre lies inside the X ring of the recorded face, which is 2.25 mm in radius. */
export function simulatedShot(shot: number): [number, number] {
  const radius = 0.8 + uniform(shot * 31 + 5) * 0.8;
  const angle = -0.5 + (uniform(shot * 31 + 9) - 0.5) * 1.6;
  return [Math.cos(angle) * radius, Math.sin(angle) * radius];
}
