import type { TargetColours } from "./draw";

/** The target palette from the theme's CSS custom properties, as resolved on `element`. */
export function themeColours(element: HTMLElement): TargetColours {
  const style = getComputedStyle(element);
  const token = (name: string): string => style.getPropertyValue(name).trim();
  return {
    face: token("--target-face"),
    ring: token("--target-ring"),
    label: token("--target-label"),
    crosshair: token("--target-crosshair"),
    shot: token("--target-shot"),
    liveAim: token("--target-live-aim"),
    holdZone: token("--target-hold-zone"),
    approach: token("--trace-approach"),
    release: token("--trace-release"),
    follow: token("--trace-follow"),
  };
}
