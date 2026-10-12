/**
 * Fold a fresh GET /tapestry answer into what the slices already hold.
 *
 * An open quote popover rests on the identity of `session.quotes`
 * (`SessionTapestry` resets its selection when that array changes), so a refetch
 * that replaced every object would close the popover under the reader whenever any
 * session changed. During a first analysis the grid refetches once per session
 * imported (docs/design-progressive-lenses.md, Phase 4 item 4), and the strip poll
 * refetches every few seconds. So each layer is kept by reference when its content
 * is unchanged, and a session whose every layer is unchanged keeps its object.
 * The fresh answer still decides which sessions exist.
 */

import type { TapestrySession } from "./types";

type Layers = Pick<TapestrySession, "turns" | "sections" | "quotes" | "strip">;
const LAYERS: (keyof Layers)[] = ["turns", "sections", "quotes", "strip"];

// A held layer is compared on every poll and never changes, so its serialisation is
// kept: a strip carries a data-URL image, and idle polls should cost next to nothing.
const serialised = new WeakMap<object, string>();
function text(v: unknown): string {
  if (v === null || typeof v !== "object") return JSON.stringify(v) ?? "";
  let s = serialised.get(v);
  if (s === undefined) {
    s = JSON.stringify(v);
    serialised.set(v, s);
  }
  return s;
}
const same = (a: unknown, b: unknown) => a === b || text(a) === text(b);

export function mergeTapestry(
  prev: Record<string, TapestrySession> | null,
  next: Record<string, TapestrySession>,
): Record<string, TapestrySession> {
  if (!prev) return next;
  let kept = Object.keys(prev).length === Object.keys(next).length;
  const merged = Object.fromEntries(
    Object.entries(next).map(([sid, fresh]) => {
      const held = prev[sid];
      if (!held) {
        kept = false;
        return [sid, fresh];
      }
      const out = { ...fresh } as TapestrySession;
      let changed = held.duration_seconds !== fresh.duration_seconds;
      for (const layer of LAYERS) {
        if (same(held[layer], fresh[layer])) {
          (out as unknown as Record<string, unknown>)[layer] = held[layer];
        } else {
          changed = true;
        }
      }
      if (changed) kept = false;
      return [sid, changed ? out : held];
    }),
  );
  // Nothing changed (an idle strip poll): the same record, so nothing re-renders.
  return kept ? prev : merged;
}
