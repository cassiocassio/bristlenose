/**
 * The report's zoom (View ▸ Zoom In / Zoom Out / Actual Size on the Mac), as
 * the root font size. Saved per viewer and put back before first paint
 * (`main.tsx`); on the Mac the saved value outlives the web view through
 * `storePref` (R89). Until then nothing read it at boot, so a relaunch, a
 * serve restart or a reload always came back at 100%.
 *
 * @module zoom
 */

import { storePref } from "./nativePrefs";

export const ZOOM_STEP = 0.1;
const ZOOM_MIN = 0.5;
const ZOOM_MAX = 2.0;
const ZOOM_KEY = "bristlenose-zoom";

function clamp(level: number): number {
  return Math.max(ZOOM_MIN, Math.min(ZOOM_MAX, Math.round(level * 100) / 100));
}

/** The saved zoom, or null when none is saved (or it is not a number). */
function savedZoom(): number | null {
  try {
    const raw = localStorage.getItem(ZOOM_KEY);
    const n = raw === null ? NaN : parseFloat(raw);
    return Number.isFinite(n) ? clamp(n) : null;
  } catch {
    return null;
  }
}

function setRootSize(level: number): void {
  document.documentElement.style.fontSize = `${Math.round(level * 100)}%`;
}

export function getZoom(): number {
  return savedZoom() ?? 1;
}

export function applyZoom(level: number): void {
  const clamped = clamp(level);
  setRootSize(clamped);
  storePref(ZOOM_KEY, String(clamped));
}

/** Put the saved zoom back. No saved value leaves the page untouched. */
export function applySavedZoom(): void {
  const z = savedZoom();
  if (z !== null) setRootSize(z);
}
