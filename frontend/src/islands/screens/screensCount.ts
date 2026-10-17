/**
 * How many screens the Screens lens is showing, and how many quotes sit on
 * them, for the window subtitle (LensSubtitleSync). The counts live in the
 * lens, which is lazy-loaded, so they reach the always-loaded subtitle sync
 * through this tiny store rather than by importing the lens.
 */

import { useSyncExternalStore } from "react";

export interface ScreensCount {
  screens: number;
  quotes: number;
}

const ZERO: ScreensCount = { screens: 0, quotes: 0 };
let count: ScreensCount = ZERO;
const listeners = new Set<() => void>();

export function setScreensCount(screens: number, quotes = 0): void {
  if (screens === count.screens && quotes === count.quotes) return;
  count = screens === 0 && quotes === 0 ? ZERO : { screens, quotes };
  listeners.forEach((l) => l());
}

function subscribe(l: () => void): () => void {
  listeners.add(l);
  return () => listeners.delete(l);
}

export function useScreensCount(): ScreensCount {
  return useSyncExternalStore(subscribe, () => count, () => count);
}
