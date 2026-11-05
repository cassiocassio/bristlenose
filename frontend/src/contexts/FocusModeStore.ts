/**
 * FocusModeStore — the report's distraction-free reading state.
 *
 * Module-level state + useSyncExternalStore, matching SidebarStore, so the
 * toolbar button, the `z` key handler and the native menu bridge can all reach
 * it without provider nesting.
 *
 * The store owns the DOM class as a side effect of the setter. There is
 * deliberately no `useEffect` in a component doing that: Focus is driven from
 * three places, and routing every one of them through a component's render
 * cycle is how the class ends up out of step with the state.
 *
 * **Persisted (owner, 4 Nov 2026).** Focus Mode used to be ephemeral: "a freshly-opened
 * project boots in normal view; Focus is a lean-in action, not a default state"
 * (docs/design-focus-mode.md § State & persistence). The owner reversed that: a
 * researcher who works in Focus Mode finds it still on at the next launch. Each change
 * goes through `storePref` (`utils/nativePrefs.ts`), which the Mac app mirrors across a
 * quit like zoom and the Display preferences (`bn-focus-mode`, in
 * `MIRRORED_PREF_KEYS`); `applySavedFocusMode()` puts the saved choice back before
 * first paint (`main.tsx`), with the classes already set so nothing fades in on load.
 *
 * @module FocusModeStore
 */

import { useSyncExternalStore } from "react";
import { storePref } from "../utils/nativePrefs";

/** localStorage / native-mirror key; listed in `MIRRORED_PREF_KEYS`. */
export const FOCUS_MODE_KEY = "bn-focus-mode";

// ── DOM hooks ─────────────────────────────────────────────────────────────

/** Toggled — carries the receded values. */
const CLASS_ACTIVE = "bn-focus-mode";

/**
 * Added once, never removed — carries the transitions, so the fade is
 * symmetric on the way out. A transition declared only alongside the active
 * class disappears the instant that class is removed, which snaps the exit.
 */
const CLASS_READY = "bn-focus-ready";

// ── State ─────────────────────────────────────────────────────────────────

let active = false;

const listeners = new Set<() => void>();

function emit(): void {
  for (const listener of listeners) listener();
}

/**
 * Subscribe to state changes. Exported because it is the store's real
 * notification path — `useSyncExternalStore` uses it, and so should anything
 * that needs to observe Focus without rendering.
 */
export function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

function getSnapshot(): boolean {
  return active;
}

/** Server snapshot for SSR/prerender parity — there is no storage to read, so off. */
function getServerSnapshot(): boolean {
  return false;
}

// ── DOM sync ──────────────────────────────────────────────────────────────

function syncDom(): void {
  // Guarded for the jsdom-less and prerender cases; the store still works as
  // pure state if there is no document to decorate.
  if (typeof document === "undefined") return;
  const root = document.documentElement;
  root.classList.add(CLASS_READY);
  root.classList.toggle(CLASS_ACTIVE, active);
}

// ── Public API ────────────────────────────────────────────────────────────

/** Subscribe to focus-mode state. */
export function useFocusMode(): boolean {
  return useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);
}

/** Read focus-mode state outside React (keyboard handlers, bridge). */
export function isFocusMode(): boolean {
  return active;
}

/** Set focus mode explicitly. No-op when already in the requested state. */
export function setFocusMode(next: boolean): void {
  if (active === next) return;
  active = next;
  storePref(FOCUS_MODE_KEY, next ? "on" : "off");
  syncDom();
  emit();
}

/**
 * Put the saved choice back, before first paint (`main.tsx`). Restoring is not
 * choosing, so it writes nothing. Never throws on unavailable storage.
 */
export function applySavedFocusMode(): void {
  let saved = false;
  try {
    saved = localStorage.getItem(FOCUS_MODE_KEY) === "on";
  } catch {
    // storage unavailable: boots off
  }
  active = saved;
  syncDom();
  emit();
}

/** Flip focus mode. The single entry point for all three affordances. */
export function toggleFocusMode(): void {
  setFocusMode(!active);
}

/** Test seam — reset to the boot state. */
export function _resetFocusMode(): void {
  active = false;
  syncDom();
  emit();
}
