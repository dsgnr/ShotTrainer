/**
 * Text for two polite live regions. Each announcement goes to the region
 * the previous one did not use and empties the other, so a screen reader
 * reads a repeated text again.
 */
export class Announcer {
  regions: readonly [string, string] = $state.raw(["", ""]);
  #last: 0 | 1 = 1;

  announce(text: string): void {
    if (text === "") {
      return;
    }
    this.#last = this.#last === 0 ? 1 : 0;
    this.regions = this.#last === 0 ? [text, ""] : ["", text];
  }
}
