/**
 * How many screens the Screens lens is showing, for the window subtitle
 * (LensSubtitleSync). The count lives in the lens, which is lazy-loaded, so it
 * reaches the always-loaded subtitle sync through this tiny store rather than
 * by importing the lens.
 */

import { useSyncExternalStore } from "react";

let count = 0;
const listeners = new Set<() => void>();

export function setScreensCount(n: number): void {
  if (n === count) return;
  count = n;
  listeners.forEach((l) => l());
}

function subscribe(l: () => void): () => void {
  listeners.add(l);
  return () => listeners.delete(l);
}

export function useScreensCount(): number {
  return useSyncExternalStore(subscribe, () => count, () => count);
}
