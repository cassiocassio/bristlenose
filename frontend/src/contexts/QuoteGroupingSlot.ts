/**
 * The Quotes lens's grouping, as the page has worked it out, for the two
 * readers outside the page: the content sidebar's header (AppLayout) and its
 * list (TocSidebar).
 *
 * `QuotesTab` owns the decision — the remembered choice and the run-time rule
 * that keeps a researcher on Sessions until they pick (QuoteGroupingToggle,
 * docs/design-progressive-lenses.md §2). It publishes the result here and
 * clears it when the page unmounts. Readers never decide; they only follow.
 */

import { useSyncExternalStore } from "react";
import type { QuoteGrouping } from "../islands/QuoteGroupingToggle";

export interface QuoteGroupingView {
  /** The grouping the column is drawing. */
  shown: QuoteGrouping;
  /** False during a first analysis, when Sessions is the only grouping. */
  controlVisible: boolean;
  /** Choose a grouping (remembered per project). */
  choose: (g: QuoteGrouping) => void;
}

let view: QuoteGroupingView | null = null;
const listeners = new Set<() => void>();

function emit(): void {
  for (const l of listeners) l();
}

export function publishQuoteGrouping(next: QuoteGroupingView): void {
  if (
    view &&
    view.shown === next.shown &&
    view.controlVisible === next.controlVisible &&
    view.choose === next.choose
  ) {
    return;
  }
  view = next;
  emit();
}

export function clearQuoteGrouping(): void {
  if (view === null) return;
  view = null;
  emit();
}

/** The published grouping, or null when the Quotes page is not mounted. */
export function useQuoteGroupingView(): QuoteGroupingView | null {
  return useSyncExternalStore(
    (l) => {
      listeners.add(l);
      return () => listeners.delete(l);
    },
    () => view,
  );
}

/** For test isolation. */
export function resetQuoteGroupingSlot(): void {
  view = null;
  emit();
}
