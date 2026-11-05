/**
 * DisplayPrefsStore — how the quote content looks: Layout, Density, and
 * Break long paragraphs (docs/design-display-preferences.md).
 *
 * Module-level state + useSyncExternalStore, matching FocusModeStore, so the
 * Display menu, the boot code and the quote card all reach it without provider
 * nesting. Unlike Focus Mode these persist: each choice goes through
 * `storePref`, so the Mac app keeps it across a quit (R89), and the saved
 * values are put back before first paint (`main.tsx`).
 *
 * The store owns the three `data-bn-*` attributes on `<html>`; the CSS
 * (`organisms/display-prefs.css`) scopes every rule to the Quotes lens's groups, so
 * nothing outside it ever changes size.
 *
 * A stored value that is not one of the allowed ones is ignored, so stale or
 * hand-edited storage can never break the page.
 *
 * @module DisplayPrefsStore
 */

import { useSyncExternalStore } from "react";
import { storePref } from "../utils/nativePrefs";

// ── Vocabulary ────────────────────────────────────────────────────────────

export const LAYOUTS = ["columns", "single"] as const;
export const BREAKS = ["on", "off"] as const;

export type Layout = (typeof LAYOUTS)[number];
export type Breaks = (typeof BREAKS)[number];

/** Density is a continuous value, 0 (the tightest) to 1 (the roomiest), with
 *  Normal, today's screen, at the middle. The words Compact, Normal and
 *  Spacious name the two ends and the middle; the slider is free between. */
export const DENSITY_STOPS = { compact: 0, normal: 0.5, spacious: 1 } as const;
export const DENSITY_NORMAL = DENSITY_STOPS.normal;

export interface DisplayPrefs {
  layout: Layout;
  /** 0 to 1, two decimal places; 0.5 is Normal. */
  density: number;
  breaks: Breaks;
}

/** A density value clamped to 0..1 and rounded to two places, or null if it
 *  is not a number. Rounding keeps a dragged slider's stored value short and
 *  makes "exactly Normal" a value a reader can land on. */
export function normaliseDensity(value: unknown): number | null {
  const n = typeof value === "number" ? value : typeof value === "string" ? parseFloat(value) : NaN;
  if (!Number.isFinite(n)) return null;
  return Math.round(Math.max(0, Math.min(1, n)) * 100) / 100;
}

/** The nearest named stop, for a word to say and a tick to show. */
export function densityWord(d: number): keyof typeof DENSITY_STOPS {
  if (d < 0.25) return "compact";
  if (d > 0.75) return "spacious";
  return "normal";
}

/** Break long paragraphs is ON by default (owner, 4 Nov 2026): a researcher who has
 *  never opened the Display menu gets long quotes in paragraphs; one who prefers the
 *  unbroken quote turns it off and that choice is saved. Changing the default is this
 *  line and `DisplayPrefs.standard` in desktop/.../DisplayPrefs.swift, which the Mac
 *  popover shows before the report posts. */
export const DEFAULT_BREAKS: Breaks = "on";

export const DEFAULT_PREFS: Readonly<DisplayPrefs> = Object.freeze({
  layout: "columns",
  density: DENSITY_NORMAL,
  breaks: DEFAULT_BREAKS,
});

/** localStorage / native-mirror keys; listed in `MIRRORED_PREF_KEYS`. */
export const DISPLAY_KEYS = {
  layout: "bn-display-layout",
  density: "bn-display-density",
  breaks: "bn-display-breaks",
} as const;

const ALLOWED = { layout: LAYOUTS, breaks: BREAKS } as const;

// ── State ─────────────────────────────────────────────────────────────────

let prefs: Readonly<DisplayPrefs> = DEFAULT_PREFS;

const listeners = new Set<() => void>();

function emit(): void {
  for (const listener of listeners) listener();
}

export function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

function getSnapshot(): Readonly<DisplayPrefs> {
  return prefs;
}

function getServerSnapshot(): Readonly<DisplayPrefs> {
  return DEFAULT_PREFS;
}

/** A value the setting accepts, as the setting's own type, or null. */
function accept<K extends keyof DisplayPrefs>(name: K, value: unknown): DisplayPrefs[K] | null {
  if (name === "density") return normaliseDensity(value) as DisplayPrefs[K] | null;
  const allowed = ALLOWED[name as "layout" | "breaks"] as readonly unknown[];
  return allowed.includes(value) ? (value as DisplayPrefs[K]) : null;
}

// ── DOM sync ──────────────────────────────────────────────────────────────

function syncDom(): void {
  if (typeof document === "undefined") return;
  const root = document.documentElement;
  root.setAttribute("data-bn-layout", prefs.layout);
  // Normal is today's screen: no density rule applies. Anything else is
  // "custom", and the CSS reads how far from Normal as a signed -1..1.
  const normal = prefs.density === DENSITY_NORMAL;
  root.setAttribute("data-bn-density", normal ? "normal" : "custom");
  if (normal) root.style.removeProperty("--bn-density-s");
  else root.style.setProperty("--bn-density-s", String((prefs.density - DENSITY_NORMAL) * 2));
  root.setAttribute("data-bn-breaks", prefs.breaks);
}

/** Stored words from the first build (compact, normal, spacious) still load. */
const LEGACY_DENSITY: Record<string, number> = DENSITY_STOPS;

function readSaved<K extends keyof DisplayPrefs>(name: K): DisplayPrefs[K] | null {
  try {
    const raw = localStorage.getItem(DISPLAY_KEYS[name]);
    if (name === "density" && raw !== null && Object.prototype.hasOwnProperty.call(LEGACY_DENSITY, raw)) {
      return LEGACY_DENSITY[raw] as DisplayPrefs[K];
    }
    return accept(name, raw);
  } catch {
    return null;
  }
}

// ── Public API ────────────────────────────────────────────────────────────

/** Subscribe to the display preferences. */
export function useDisplayPrefs(): Readonly<DisplayPrefs> {
  return useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);
}

/** Subscribe to Break long paragraphs alone: a card has no use for Layout or Density, which are CSS. */
export function useDisplayBreaks(): Breaks {
  return useSyncExternalStore(
    subscribe,
    () => prefs.breaks,
    () => DEFAULT_PREFS.breaks,
  );
}

/** For code outside React (the Mac bridge post). */
export const subscribeDisplayPrefs = subscribe;

/** Read the display preferences outside React. */
export function getDisplayPrefs(): Readonly<DisplayPrefs> {
  return prefs;
}

/** Set one preference: validates, saves (and mirrors to the Mac), applies. */
export function setDisplayPref<K extends keyof DisplayPrefs>(name: K, value: DisplayPrefs[K]): void {
  const next = accept(name, value);
  if (next === null) return;
  if (prefs[name] === next) return;
  prefs = Object.freeze({ ...prefs, [name]: next });
  storePref(DISPLAY_KEYS[name], String(next));
  syncDom();
  emit();
}

/**
 * Put the saved values back, before first paint (`main.tsx`), and again when
 * another window of the report changes them (the `storage` event below).
 * Never writes: restoring is not choosing.
 */
export function applySavedDisplayPrefs(): void {
  prefs = Object.freeze({
    layout: readSaved("layout") ?? DEFAULT_PREFS.layout,
    density: readSaved("density") ?? DEFAULT_PREFS.density,
    breaks: readSaved("breaks") ?? DEFAULT_PREFS.breaks,
  });
  syncDom();
  emit();
}

// Windows of the report share this storage. Without this, a window holding a
// stale in-memory value treats a choice equal to it as no change and never
// saves it, so the saved value and the screen disagree until relaunch.
if (typeof window !== "undefined") {
  window.addEventListener("storage", (e) => {
    if (e.key === null || Object.values(DISPLAY_KEYS).includes(e.key as never)) {
      applySavedDisplayPrefs();
    }
  });
}

/** Test seam — reset to the defaults, without touching storage. */
export function _resetDisplayPrefs(): void {
  prefs = DEFAULT_PREFS;
  syncDom();
  emit();
}
