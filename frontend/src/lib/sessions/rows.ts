import { isFiniteNumber } from "../wire/numbers";
import type { WireSessionSummary } from "../wire/types";

const MONTHS = [
  "Jan",
  "Feb",
  "Mar",
  "Apr",
  "May",
  "Jun",
  "Jul",
  "Aug",
  "Sep",
  "Oct",
  "Nov",
  "Dec",
];

const DOT = "\u00b7";

/** The dim secondary line: date, shot count and duration. */
export function sessionMeta(summary: WireSessionSummary): string {
  const started = new Date(summary.startedAt);
  const date = Number.isNaN(started.getTime())
    ? summary.startedAt
    : `${started.getDate()} ${MONTHS[started.getMonth()]} ${started.getFullYear()}, ` +
      `${pad(started.getHours())}:${pad(started.getMinutes())}`;
  const shots = summary.shotCount === 1 ? "1 shot" : `${summary.shotCount} shots`;
  return `${date}  ${DOT}  ${shots}  ${DOT}  ${duration(summary)}`;
}

function duration(summary: WireSessionSummary): string {
  if (summary.endedAt === null) {
    return "in progress";
  }
  const start = Date.parse(summary.startedAt);
  const end = Date.parse(summary.endedAt);
  if (Number.isNaN(start) || Number.isNaN(end)) {
    return "in progress";
  }
  const seconds = Math.max(0, Math.round((end - start) / 1000));
  const minutes = Math.floor(seconds / 60);
  const rest = seconds % 60;
  return minutes > 0 ? `${minutes}m ${pad(rest)}s` : `${rest}s`;
}

function pad(value: number): string {
  return value.toString().padStart(2, "0");
}

/** The score badge, `N pts` when the session scored, otherwise empty. */
export function scoreBadge(summary: WireSessionSummary): string {
  if (summary.shotCount > 0 && isFiniteNumber(summary.totalScore) && summary.totalScore > 0) {
    return `${summary.totalScore.toFixed(1)} pts`;
  }
  return "";
}

/** Sessions whose name or notes contain `query` and match `category`, both optional. */
export function filterSessions(
  sessions: WireSessionSummary[],
  query: string,
  category: string,
): WireSessionSummary[] {
  const needle = query.trim().toLowerCase();
  return sessions.filter(
    (s) =>
      (needle === "" ||
        s.name.toLowerCase().includes(needle) ||
        s.notes.toLowerCase().includes(needle)) &&
      (category === "" || s.category === category),
  );
}
