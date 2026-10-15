/**
 * The Screens lens's narrative: who said what on a screen, in what order (docs/design-screens.md
 * S5, "Narrative"). Pure functions, unit-tested.
 *
 * - Sequence numbers are per person, in time order: each card shows its person's badge with that
 *   person's place among their own quotes on this screen (p1 ①②③, p2 ①②). There is no global
 *   sequence: a researcher reads one participant's path through a page, not an interleaving.
 * - J/K step through the screen's quotes in time order, only the chosen people's when a person
 *   filter is on. `stepFrom` moves as FocusContext's `moveFocus` does (from nothing to an end,
 *   one at a time, clamped), over the lens's own narrative list rather than the registered visible
 *   quotes. On Screens the report's global handler leaves the arrows and j/k to the lens, which
 *   owns them (ScreensLens.tsx says how the two handlers meet).
 */

export interface Said {
  id: string;
  person: string;
  t: number;
}

export interface Sequence {
  person: string;
  /** 1-based place among this person's quotes on this screen, by time. */
  n: number;
  total: number;
}

/** Each quote's place among its own person's quotes, by time (ties keep the given order). */
export function sequenceByPerson(said: Said[]): Record<string, Sequence> {
  const byPerson = new Map<string, Said[]>();
  for (const s of said) {
    const list = byPerson.get(s.person) ?? [];
    list.push(s);
    byPerson.set(s.person, list);
  }
  const out: Record<string, Sequence> = {};
  for (const [person, list] of byPerson) {
    const sorted = [...list].sort((a, b) => a.t - b.t);
    sorted.forEach((s, i) => (out[s.id] = { person, n: i + 1, total: sorted.length }));
  }
  return out;
}

/** The people who spoke on a screen, in the report's order (p2 before p10). */
export function peopleOf(said: Said[]): string[] {
  return [...new Set(said.map((s) => s.person))].sort((a, b) => a.localeCompare(b, undefined, { numeric: true }));
}

/**
 * The next quote from `current` in `order`, moving as FocusContext's `moveFocus` does — from nothing (or
 * from a quote no longer in the list) the first going forward and the last going back; clamped at
 * either end.
 */
export function stepFrom(order: string[], current: string | null, dir: 1 | -1): string | null {
  if (!order.length) return null;
  const i = current ? order.indexOf(current) : -1;
  if (i === -1) return dir > 0 ? order[0] : order[order.length - 1];
  return order[Math.max(0, Math.min(order.length - 1, i + dir))];
}
