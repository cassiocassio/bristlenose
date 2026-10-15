/**
 * The Screens board's reading order: the order the report's shared keys walk (J/K and ⇧J/K, ⇧-click
 * ranges, ⌘A — FocusContext, through useKeyboardShortcuts, exactly as on the Quotes lens). The lens
 * registers it with `registerVisibleQuoteIds` (docs/design-screens.md S5, "Keys").
 *
 * The margins first, as they sit on the board — top to bottom, then left to right, so the band
 * above the screengrab, the two columns beside it interleaved by height, and the band below — then
 * the list under the screengrab in time order. Time order breaks ties and orders one person's
 * quotes; it is never drawn (the timecode already says it).
 */

export interface Seen {
  id: string;
  top: number;
  left: number;
}

export function readingOrder(margins: Seen[], listed: string[]): string[] {
  const order = margins.map((m, i) => ({ ...m, i })).sort((a, b) => a.top - b.top || a.left - b.left || a.i - b.i);
  const seen = new Set(order.map((m) => m.id));
  return [...order.map((m) => m.id), ...listed.filter((d) => !seen.has(d))];
}
