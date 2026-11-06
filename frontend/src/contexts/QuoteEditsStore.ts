/**
 * QuoteEditsStore — whether the transcript shows how each quote was made.
 *
 * View ▸ Show / Hide Quote Edits on the Mac (docs/design-quote-edits-view.md).
 * Module-level state + useSyncExternalStore, matching FocusModeStore, so the
 * native menu bridge and anything that draws the view can reach it without
 * provider nesting.
 *
 * **Not persisted, on purpose.** It is off at every launch: a curious look at
 * how the raw transcript became a quote must never leave the page in the
 * harder-to-read state the next time a researcher opens it (owner, 6 Nov 2026).
 * That is the opposite of Focus Mode and the Display settings, which persist.
 *
 * Step 1 is the menu item and this state only. The setter puts a class on the
 * document root for the transcript CSS to key on; nothing styles it yet.
 *
 * @module QuoteEditsStore
 */

import { useSyncExternalStore } from "react";

/** Toggled on the document root. Nothing styles it yet. */
export const CLASS_QUOTE_EDITS = "bn-quote-edits";

let active = false;

const listeners = new Set<() => void>();

function emit(): void {
  for (const listener of listeners) listener();
}

/** Subscribe to state changes. */
export function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

function getSnapshot(): boolean {
  return active;
}

/** Server snapshot for prerender parity: off. */
function getServerSnapshot(): boolean {
  return false;
}

function syncDom(): void {
  if (typeof document === "undefined") return;
  document.documentElement.classList.toggle(CLASS_QUOTE_EDITS, active);
}

/** Subscribe to the state from a component. */
export function useQuoteEdits(): boolean {
  return useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);
}

/** Read the state outside React (the bridge). */
export function isQuoteEdits(): boolean {
  return active;
}

/** Set explicitly. No-op when already in the requested state. */
export function setQuoteEdits(next: boolean): void {
  if (active === next) return;
  active = next;
  syncDom();
  emit();
}

/** Flip it. The one entry point for the native menu. */
export function toggleQuoteEdits(): void {
  setQuoteEdits(!active);
}

/** Test seam: back to the boot state. */
export function _resetQuoteEdits(): void {
  active = false;
  syncDom();
  emit();
}
