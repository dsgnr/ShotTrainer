/** Render milliseconds as `M:SS.t` with one tenth of a second. */
export function formatSeconds(milliseconds: number): string {
  const ms = Math.max(0, milliseconds);
  const totalTenths = Math.round(ms / 100);
  const minutes = Math.floor(totalTenths / 600);
  const rest = totalTenths % 600;
  const seconds = Math.floor(rest / 10);
  const tenths = rest % 10;
  return `${minutes}:${seconds.toString().padStart(2, "0")}.${tenths}`;
}

/** The transport time label, `offset / duration`. A null window shows zeroes. */
export function timeLabel(fraction: number, durationMs: number | null): string {
  const duration = durationMs ?? 0;
  const offset = Math.round(fraction * duration);
  return `${formatSeconds(offset)} / ${formatSeconds(duration)}`;
}
