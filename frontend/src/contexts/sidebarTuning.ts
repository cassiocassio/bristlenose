/**
 * The four playground values the sidebar reads — without the playground.
 *
 * `PlaygroundStore` is dev-only (`AppLayout` lazy-loads `ResponsivePlayground`
 * under `--dev`), but `SidebarLayout` and `TocSidebar` read four of its fields
 * on every page. Importing the store for them put all 2.2 kB of it on first
 * paint (measured 4 Oct 2026, docs/design-perf-regression-gate.md). This module
 * holds the production defaults; the store connects itself when the playground
 * loads it, and from then on the sidebar sees its live values.
 *
 * Production therefore never reads a playground value left in sessionStorage by
 * an earlier `--dev` session in the same tab. It used to.
 *
 * @module sidebarTuning
 */

import { useSyncExternalStore } from "react";

/** `null` in every field means "use the reader's own default". */
export interface SidebarTuning {
  /** Overlay hover-open delay in ms. */
  hoverDelay: number | null;
  /** Overlay hover-leave grace in ms. */
  leaveGrace: number | null;
  /** Overlay content animation variant (null = "curtain"). */
  overlayStyle: "curtain" | "ios" | null;
  /** Close the overlay on a TOC anchor click. */
  overlayAutoClose: boolean | null;
}

export const SIDEBAR_TUNING_DEFAULTS: SidebarTuning = {
  hoverDelay: null,
  leaveGrace: null,
  overlayStyle: null,
  overlayAutoClose: null,
};

let getSource: (() => SidebarTuning) | null = null;
const listeners = new Set<() => void>();

function getSnapshot(): SidebarTuning {
  return getSource ? getSource() : SIDEBAR_TUNING_DEFAULTS;
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

/**
 * Called once by `PlaygroundStore` at module load. `getSnapshot` must return a
 * stable reference between changes, as `useSyncExternalStore` requires.
 */
export function connectSidebarTuning(
  sourceSnapshot: () => SidebarTuning,
  sourceSubscribe: (listener: () => void) => () => void,
): void {
  getSource = sourceSnapshot;
  sourceSubscribe(() => listeners.forEach((l) => l()));
  listeners.forEach((l) => l());
}

/** The sidebar's tuning: defaults, or the playground's values once it loads. */
export function useSidebarTuning(): SidebarTuning {
  return useSyncExternalStore(subscribe, getSnapshot);
}
