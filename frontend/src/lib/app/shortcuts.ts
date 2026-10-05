import { stepSelection } from "../shots/rows";

export interface ShortcutContext {
  key: string;
  /** True when focus is in a text field, so typing is not hijacked. */
  typing: boolean;
  modalOpen: boolean;
  replayEnabled: boolean;
  replayPlaying: boolean;
  shotCount: number;
  selected: number | null;
}

export type ShortcutAction =
  | { kind: "closeModal" }
  | { kind: "replayToggle"; play: boolean }
  | { kind: "selectShot"; index: number }
  | { kind: "none" };

/**
 * The action for a keypress, or `null` when the key is not a shortcut. A `none`
 * action means the key is handled but does nothing, so the caller still
 * prevents the default. Typing in a field passes every key through.
 */
export function resolveShortcut(context: ShortcutContext): ShortcutAction | null {
  if (context.typing) {
    return null;
  }
  if (context.key === "Escape") {
    return context.modalOpen ? { kind: "closeModal" } : null;
  }
  // A modal owns the keyboard while it is open, so no view shortcut fires.
  if (context.modalOpen) {
    return { kind: "none" };
  }
  if (context.key === " " && context.replayEnabled) {
    return { kind: "replayToggle", play: !context.replayPlaying };
  }
  if (context.key === "ArrowDown" || context.key === "ArrowUp") {
    const index = stepSelection(context.selected, context.key === "ArrowDown" ? 1 : -1, context.shotCount);
    return index === null ? null : { kind: "selectShot", index };
  }
  return null;
}
