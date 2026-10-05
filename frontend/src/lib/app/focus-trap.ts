/**
 * The index to focus next when Tab moves within a trap. `current` is the index
 * of the focused element, or -1 when focus is outside. `null` when the trap
 * holds nothing focusable.
 */
export function nextFocusIndex(current: number, count: number, backward: boolean): number | null {
  if (count === 0) {
    return null;
  }
  if (current < 0) {
    return backward ? count - 1 : 0;
  }
  return backward ? (current - 1 + count) % count : (current + 1) % count;
}

const FOCUSABLE =
  'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), ' +
  'textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

function focusable(container: HTMLElement): HTMLElement[] {
  return [...container.querySelectorAll<HTMLElement>(FOCUSABLE)].filter(
    (element) => element.offsetParent !== null || element === document.activeElement,
  );
}

/**
 * Keeps Tab focus inside `container` while it is mounted. Focus moves into the
 * container on mount and returns to the previously focused element on destroy,
 * so a modal does not leak focus to the view behind it.
 */
export function focusTrap(container: HTMLElement): { destroy: () => void } {
  const previous = document.activeElement instanceof HTMLElement ? document.activeElement : null;

  const items = focusable(container);
  (items[0] ?? container).focus();

  function onKeydown(event: KeyboardEvent): void {
    if (event.key !== "Tab") {
      return;
    }
    const current = focusable(container);
    if (current.length === 0) {
      event.preventDefault();
      return;
    }
    const activeIndex = current.indexOf(document.activeElement as HTMLElement);
    const index = nextFocusIndex(activeIndex, current.length, event.shiftKey);
    if (index !== null) {
      event.preventDefault();
      current[index]?.focus();
    }
  }

  container.addEventListener("keydown", onKeydown);

  return {
    destroy() {
      container.removeEventListener("keydown", onKeydown);
      previous?.focus();
    },
  };
}
