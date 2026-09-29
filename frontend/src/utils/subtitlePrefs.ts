/**
 * Per-viewer subtitle preferences, shared by every surface that shows them.
 *
 * - ``playerSubtitles`` — show subtitles in the popout video player. Off by
 *   default: a researcher reviewing their own interviews is listening.
 * - ``burnSubtitles`` — clip export also writes a copy of each video clip
 *   with the subtitles in its pixels ("for slides"). Off by default: it
 *   re-encodes, and the clean clip plus its .vtt suit most uses.
 *
 * The web layer owns both (localStorage, like the palette and appearance).
 * The macOS menus show a checkmark that mirrors them over the bridge
 * (``subtitle-prefs``), the Focus Mode pattern: the menu dispatches a toggle
 * and reads the result back, so a remount can never leave it claiming a
 * state the page no longer has. Every read and write is wrapped: storage can
 * be unavailable (private mode, blocked site data) and the defaults stand.
 *
 * @module subtitlePrefs
 */

import { useSyncExternalStore } from "react";

export interface SubtitlePrefs {
  playerSubtitles: boolean;
  burnSubtitles: boolean;
}

const KEYS: Record<keyof SubtitlePrefs, string> = {
  playerSubtitles: "bristlenose-player-subtitles",
  burnSubtitles: "bristlenose-burn-subtitles",
};

function read(key: string): boolean {
  try {
    return localStorage.getItem(key) === "true";
  } catch {
    return false;
  }
}

function load(): SubtitlePrefs {
  return { playerSubtitles: read(KEYS.playerSubtitles), burnSubtitles: read(KEYS.burnSubtitles) };
}

let current: SubtitlePrefs = load();
const listeners = new Set<() => void>();

function emit(): void {
  listeners.forEach((fn) => fn());
}

/** Current preferences (synchronous — for non-React callers). */
export function getSubtitlePrefs(): SubtitlePrefs {
  return current;
}

/** Set one preference, persist it, and notify subscribers. */
export function setSubtitlePref(name: keyof SubtitlePrefs, value: boolean): void {
  if (current[name] === value) return;
  current = { ...current, [name]: value };
  try {
    localStorage.setItem(KEYS[name], String(value));
  } catch {
    // Applied for the session but not persisted.
  }
  emit();
}

/** Flip one preference (the native menus dispatch this). */
export function toggleSubtitlePref(name: keyof SubtitlePrefs): void {
  setSubtitlePref(name, !current[name]);
}

export function subscribeSubtitlePrefs(fn: () => void): () => void {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

// Another tab of the same report changed a preference.
if (typeof window !== "undefined") {
  window.addEventListener("storage", (e) => {
    if (e.key === KEYS.playerSubtitles || e.key === KEYS.burnSubtitles) {
      current = load();
      emit();
    }
  });
}

/** React hook: the current preferences, re-rendering on change. */
export function useSubtitlePrefs(): SubtitlePrefs {
  return useSyncExternalStore(subscribeSubtitlePrefs, getSubtitlePrefs, getSubtitlePrefs);
}

/** Test seam: re-read storage (tests reset localStorage between cases). */
export function _resetSubtitlePrefsForTests(): void {
  current = load();
}
