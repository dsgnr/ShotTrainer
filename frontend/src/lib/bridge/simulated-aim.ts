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
/** Matches the default post-shot window. */
const FOLLOW_SECONDS = 0.8;
function approach(shot: number, phase: number): [number, number] {
  const seed = shot * 31;
  const cx = normal(seed + 7) * 1.5;
  const cy = normal(seed + 11) * 1.5;
  const entry: [number, number, number][] = [
    [0.0, -72.0, 70.0],
    [0.1, -72.0, 70.0],
    [0.2, -72.0, 70.0],
    [0.3, -68.0, 68.0],
    [0.4, -49.0, 62.0],
    [0.5, -40.0, 54.0],
    [0.6, -31.0, 46.0],
    [0.7, -26.721, 41.031],
    [0.8, -26.91, 39.609],
    [0.9, -21.681, 41.778],
    [1.0, -10.692, 43.317],
    [1.1, -9.225, 47.772],
    [1.2, -6.03, 51.138],
    [1.3, -3.609, 55.161],
    [1.4, -2.457, 59.175],
    [1.5, -1.017, 62.775],
    [1.6, 0.423, 60.975],
    [1.7, 1.152, 56.034],
    [1.8, 5.157, 51.813],
    [1.9, 4.428, 46.737],
    [2.0, 7.308, 39.789],
    [2.1, 2.097, 36.891],
    [2.2, 0.054, 32.04],
    [2.3, 0.549, 28.71],
    [2.4, -1.872, 25.371],
    [2.5, -1.53, 19.98],
    [2.6, 1.008, 17.937],
    [2.7, -0.639, 15.975],
    [2.8, -0.747, 14.463],
    [2.9, -0.666, 12.591],
    [3.0, -0.909, 11.547],
    [3.1, 1.719, 9.729],
    [3.2, 1.188, 7.353],
    [3.3, 0.828, 5.733],
    [3.4, 5.184, 4.257],
    [3.5, -1.125, 1.854],
    [3.6, 1.44, -0.54],
    [3.7, -0.09, 0.684],
    [3.8, 0.0, 0.0],
    [4.0, 0.0, 0.0],
    [4.1, -0.27, -0.54],
    [4.2, 0.189, -1.413],
    [4.3, 0.999, -1.503],
    [4.4, 0.099, -1.836],
    [4.5, -0.855, -2.124],
    [4.6, 0.108, -3.186],
    [4.7, -1.971, -3.951],
    [4.8, -1.161, -4.653],
    [4.9, 0.423, -4.527],
    [5.0, 0.504, -5.166],
    [5.1, -1.179, -4.005],
    [5.2, -0.261, -5.049],
    [5.3, 1.602, -6.507],
    [5.4, 3.672, -6.426],
    [5.5, -0.387, -6.057],
    [5.6, -0.945, -6.84],
    [5.7, 0.144, -5.031],
    [5.8, 1.368, -6.129],
    [5.9, -0.153, -5.589],
    [6.0, 0.288, -6.624],
    [6.1, 3.807, -6.48],
    [6.2, -0.027, -6.093],
    [6.3, -0.585, -6.048],
    [6.4, -0.306, -6.039],
    [6.5, -2.403, -5.598],
    [6.6, -0.99, -4.941],
    [6.7, -1.944, -4.842],
    [6.8, 1.224, -4.212],
    [6.9, -1.701, -3.366],
    [7.0, -0.684, -3.6],
    [7.1, -0.234, -4.401],
    [7.2, -0.612, -2.286],
    [7.3, -0.369, -0.909],
    [7.4, -0.954, -1.17],
    [7.5, -0.774, -1.521],
    [7.6, -2.565, -2.511],
    [7.7, 1.935, -2.871],
    [7.8, 3.267, -4.158],
    [7.9, -0.054, -2.133],
    [8.0, -0.144, -0.72],
    [8.1, -0.09, 0.135],
    [8.2, -0.648, -0.27],
  ];
  const time = phase < 7 ? Math.max(0, (phase - 1.5) / 5.5 * 4) : Math.min(8.2, 4 + (phase - 7) / 3 * 4.2);
  const index = Math.min(entry.length - 2, Math.max(0, entry.findIndex(point => point[0] >= time) - 1));
  const from = entry[index]!;
  const to = entry[index + 1]!;
  const p = (time - from[0]) / (to[0] - from[0]);
  const previous = entry[Math.max(0, index - 1)]!;
  const next = entry[Math.min(entry.length - 1, index + 2)]!;
  const curve = (axis: 1 | 2) => {
    const a = from[axis], b = to[axis];
    return (2 * p ** 3 - 3 * p ** 2 + 1) * a + (p ** 3 - 2 * p ** 2 + p) * (b - previous[axis]) * 0.5
      + (-2 * p ** 3 + 3 * p ** 2) * b + (p ** 3 - p ** 2) * (next[axis] - a) * 0.5;
  };
  const scale = 0.95 + uniform(seed + 17) * 0.1;
  const seconds = shot * 10 + Math.max(phase, shot === 0 ? 0 : 1.5);
  return [cx + curve(1) * scale + tremor(seconds * 0.45, seed + 101) * 0.25,
    cy + curve(2) * scale + tremor(seconds * 0.45, seed + 303) * 0.25
      + 0.2 * Math.sin(2 * Math.PI * 0.2 * seconds)];
}
function followThrough(shot: number, elapsed: number): [number, number] {
  const [x, y] = approach(shot, 10);
  const seed = shot * 31;
  const times = [0, 0.025, 0.07, 0.13, 0.21, 0.3, 0.45, 0.6, 0.8, 1];
  const radii = [0, 15, 120, 150, 85, 8, 18, 5, 10, 6];
  const points = radii.map((radius, i): [number, number] => {
    const angle = uniform(seed + 41 + i * 7) * 2 * Math.PI;
    const distance = radius * 1.12 * (0.8 + uniform(seed + 43 + i * 7) * 0.4);
    return [Math.cos(angle) * distance, Math.sin(angle) * distance];
  });
  const index = Math.min(times.length - 2, Math.max(0, times.findIndex(time => time >= elapsed) - 1));
  const p = Math.max(0, Math.min(1, (elapsed - times[index]!) / (times[index + 1]! - times[index]!)));
  const before = points[Math.max(0, index - 1)]!;
  const from = points[index]!;
  const to = points[index + 1]!;
  const after = points[Math.min(points.length - 1, index + 2)]!;
  return [0, 1].map(axis => {
    const a = from[axis]!;
    const b = to[axis]!;
    const tangentA = (b - before[axis]!) * 0.5;
    const tangentB = (after[axis]! - a) * 0.5;
    return (axis === 0 ? x : y) + (2 * p ** 3 - 3 * p ** 2 + 1) * a
      + (p ** 3 - 2 * p ** 2 + p) * tangentA + (-2 * p ** 3 + 3 * p ** 2) * b
      + (p ** 3 - p ** 2) * tangentB;
  }) as [number, number];
}
export function simulatedAim(seconds: number): [number, number] {
  const shot = Math.floor(seconds / 10);
  const phase = seconds % 10;
  // The recoil ends with the post-shot window. The next approach then starts off target, not at the last shot.
  if (shot > 0 && phase <= FOLLOW_SECONDS) return followThrough(shot - 1, phase);
  return approach(shot, phase);
}
