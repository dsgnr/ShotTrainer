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

interface Parts {
  year: number;
  month: number;
  day: number;
  hour: number;
  minute: number;
  second: number;
}

/** Parse an ISO local timestamp without a zone as wall-clock components. */
function parse(stamp: string): Parts | null {
  const match = /^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2}):(\d{2})/.exec(stamp);
  if (match === null) {
    return null;
  }
  const [, year, month, day, hour, minute, second] = match.map(Number);
  return {
    year: year!,
    month: month!,
    day: day!,
    hour: hour!,
    minute: minute!,
    second: second!,
  };
}

/** The dim secondary line: date, shot count and duration. */
export function sessionMeta(summary: WireSessionSummary): string {
  const started = parse(summary.startedAt);
  const date =
    started === null
      ? summary.startedAt
      : `${started.day} ${MONTHS[started.month - 1]} ${started.year}, ` +
        `${pad(started.hour)}:${pad(started.minute)}`;
  const shots = summary.shotCount === 1 ? "1 shot" : `${summary.shotCount} shots`;
  return `${date}  ${DOT}  ${shots}  ${DOT}  ${duration(summary)}`;
}

function duration(summary: WireSessionSummary): string {
  if (summary.endedAt === null) {
    return "in progress";
  }
  const start = parse(summary.startedAt);
  const end = parse(summary.endedAt);
  if (start === null || end === null) {
    return "in progress";
  }
  const seconds = Math.max(0, toSeconds(end) - toSeconds(start));
  const minutes = Math.floor(seconds / 60);
  const rest = seconds % 60;
  return minutes > 0 ? `${minutes}m ${pad(rest)}s` : `${rest}s`;
}

function toSeconds(p: Parts): number {
  return Date.UTC(p.year, p.month - 1, p.day, p.hour, p.minute, p.second) / 1000;
}

function pad(value: number): string {
  return value.toString().padStart(2, "0");
}

/** The score badge, `N pts` when the session scored, otherwise empty. */
export function scoreBadge(summary: WireSessionSummary): string {
  if (summary.shotCount > 0 && isFiniteNumber(summary.totalScore) && summary.totalScore > 0) {
    return `${summary.totalScore} pts`;
  }
  return "";
}

/** Sessions whose name contains `query` and match `category`, both optional. */
export function filterSessions(
  sessions: WireSessionSummary[],
  query: string,
  category: string,
): WireSessionSummary[] {
  const needle = query.trim().toLowerCase();
  return sessions.filter(
    (s) =>
      (needle === "" || s.name.toLowerCase().includes(needle)) &&
      (category === "" || s.category === category),
  );
}
