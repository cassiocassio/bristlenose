/**
 * SignalWorkingStore: whether the Signals cards show their working (the metrics chart).
 *
 * One answer for every card on every page, so opening the chart on one card opens it on all of
 * them, and it stays that way as the researcher moves between sections, themes and lenses. It was
 * per-card `useState`, so each card forgot. The chart is a reading mode, not a per-card choice
 * (owner, 30 Oct 2026).
 *
 * Module-level, like TranscriptTimelineStore. A per-viewer reading mode in localStorage, and since
 * decision #182 (9 Nov 2026) one of the R89 report preferences (`utils/nativePrefs.ts`), so the
 * Mac app keeps it past a relaunch; it survives navigating between lenses and a reload in a
 * browser. It is the panel-level answer, not a card's state: the quotes' own "Show all" disclosure
 * stays per card, and is not remembered.
 */

import { useSyncExternalStore } from "react";

import { storePref } from "../utils/nativePrefs";

const LS_KEY = "bn-signal-working-open";

function read(): boolean {
  try {
    return localStorage.getItem(LS_KEY) === "1";
  } catch {
    return false; // Storage unavailable: closed, the default.
  }
}

let open = read();
const listeners = new Set<() => void>();

export function setSignalWorkingOpen(next: boolean): void {
  if (next === open) return;
  open = next;
  // Storage unavailable: `storePref` swallows it, and module state still carries it within this page.
  storePref(LS_KEY, open ? "1" : "0");
  listeners.forEach((l) => l());
}

export function toggleSignalWorking(): void {
  setSignalWorkingOpen(!open);
}

export function getSignalWorkingOpen(): boolean {
  return open;
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

/** True while the working is shown on every card. */
export function useSignalWorkingOpen(): boolean {
  return useSyncExternalStore(subscribe, getSignalWorkingOpen, getSignalWorkingOpen);
}

/** Tests only. */
export function resetSignalWorkingStore(): void {
  try {
    localStorage.removeItem(LS_KEY);
  } catch {
    // nothing to clear
  }
  open = false;
  listeners.forEach((l) => l());
}
