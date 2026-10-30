/**
 * SignalWorkingStore: whether the Signals cards show their working (the metrics chart).
 *
 * One answer for every card on every page, so opening the chart on one card opens it on all of
 * them, and it stays that way as the researcher moves between sections, themes and lenses. It was
 * per-card `useState`, so each card forgot. The chart is a reading mode, not a per-card choice
 * (owner, 30 Oct 2026).
 *
 * Module-level, like TranscriptTimelineStore. A per-viewer convenience in localStorage: the Mac
 * app's web views forget it on quit, and that is fine; it survives navigating between lenses and
 * a reload in a browser. The quotes' own "Show all" disclosure stays per card.
 */

import { useSyncExternalStore } from "react";

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
  try {
    localStorage.setItem(LS_KEY, open ? "1" : "0");
  } catch {
    // Storage unavailable: module state still carries it within this page.
  }
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
