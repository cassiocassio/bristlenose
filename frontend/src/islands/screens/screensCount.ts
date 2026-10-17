/**
 * How many screens the Screens lens is showing, the screenshots behind them and
 * the quotes on them, for the window subtitle (LensSubtitleSync). The counts live in the
 * lens, which is lazy-loaded, so they reach the always-loaded subtitle sync
 * through this tiny store rather than by importing the lens.
 */

import { useSyncExternalStore } from "react";

export interface ScreensCount {
  screens: number;
  screenshots: number;
  quotes: number;
}

export const ZERO_SCREENS_COUNT: ScreensCount = { screens: 0, screenshots: 0, quotes: 0 };
let count: ScreensCount = ZERO_SCREENS_COUNT;
const listeners = new Set<() => void>();

export function setScreensCount(next: ScreensCount): void {
  if (next.screens === count.screens && next.screenshots === count.screenshots && next.quotes === count.quotes) return;
  count = next;
  listeners.forEach((l) => l());
}

function subscribe(l: () => void): () => void {
  listeners.add(l);
  return () => listeners.delete(l);
}

export function useScreensCount(): ScreensCount {
  return useSyncExternalStore(subscribe, () => count, () => count);
}
