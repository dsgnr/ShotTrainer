/** Reproducible approaches, settling, breathing and follow-through in millimetres. */
function uniform(seed: number): number {
  let value = (seed + 0x9e3779b9) >>> 0;
  value = Math.imul(value ^ (value >>> 16), 0x21f0aaad) >>> 0;
  value = Math.imul(value ^ (value >>> 15), 0x735a2d97) >>> 0;
  return ((value ^ (value >>> 15)) >>> 0) / 4294967296;
}
function normal(seed: number): number {
  return Math.sqrt(-2 * Math.log(Math.max(1e-9, uniform(seed)))) * Math.cos(2 * Math.PI * uniform(seed + 1));
}
function tremor(t: number, seed: number): number {
  const n = Math.floor(t * 12);
  const fraction = t * 12 - n;
  const p = fraction * fraction * (3 - 2 * fraction);
  return normal(seed + n) * (1 - p) + normal(seed + n + 1) * p;
}
function smoothstep(value: number): number {
  const p = Math.max(0, Math.min(1, value));
  return p * p * (3 - 2 * p);
}
function approach(shot: number, phase: number): [number, number] {
  const seed = shot * 31;
  const cx = normal(seed + 7) * 1.5;
  const cy = normal(seed + 11) * 1.5;
  const entryY = 110 + uniform(seed + 17) * 10;
  const angle = Math.atan2(entryY - cy, -cx);
  const distance = Math.hypot(cx, entryY - cy);
  const start = shot === 0 ? 0 : 1.5;
  phase = Math.max(phase, start);
  const p = Math.max(0, Math.min(1, (phase - start) / (4.85 - start)));
  const progress = 0.35 * p + 0.65 * smoothstep(p);
  const remaining = (1 - progress) ** 1.4 * distance;
  const movement = 2.5 + (1 - p) * 18;
  const seconds = shot * 5 + phase;
  const sway = phase * 2 * Math.PI * 3.2 + uniform(seed + 29) * 2 * Math.PI;
  const winding = movement * Math.sin(sway);
  return [cx + Math.cos(angle) * remaining - Math.sin(angle) * winding + tremor(seconds, 101) * 0.55,
    cy + Math.sin(angle) * remaining + Math.cos(angle) * winding + 0.25 * Math.cos(sway) + tremor(seconds, 303) * 0.55 + 1.2 * Math.sin(2 * Math.PI * 0.2 * seconds)];
}
function followThrough(shot: number, elapsed: number): [number, number] {
  const [x, y] = approach(shot, 5);
  const seed = shot * 31;
  const response = smoothstep(elapsed / 0.015);
  const duration = 0.22 + uniform(seed + 23) * 0.12;
  const progress = Math.max(0, Math.min(1, elapsed / duration)) ** 0.35;
  const angle = 2 * Math.PI * progress;
  const direction = Math.sign(normal(seed + 27));
  const width = 140 + uniform(seed + 31) * 50;
  const height = 240 + uniform(seed + 33) * 30;
  const skew = (uniform(seed + 35) - 0.5) * 14;
  const ripple = 3 * Math.sin(angle * 3);
  return [x + response * (direction * width * (1 - Math.cos(angle)) / 1.5 + skew * Math.sin(angle) + ripple),
    y - response * (height * Math.sin(angle) + 25 * (1 - Math.cos(angle)) + 8 * Math.sin(angle * 3))];
}
export function simulatedAim(seconds: number): [number, number] {
  const shot = Math.floor(seconds / 5);
  const phase = seconds % 5;
  if (shot > 0 && phase <= 1) return followThrough(shot - 1, phase);
  const target = approach(shot, phase);
  if (shot > 0 && phase < 1.5) {
    const previous = followThrough(shot - 1, 1);
    const p = smoothstep((phase - 1) / 0.5);
    return [previous[0] * (1 - p) + target[0] * p, previous[1] * (1 - p) + target[1] * p];
  }
  return target;
}
