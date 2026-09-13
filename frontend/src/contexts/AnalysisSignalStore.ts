/**
 * AnalysisSignalStore — module-level store for analysis sidebar signal list.
 *
 * Populated by AnalysisPage after de-duplication. Read by
 * AnalysisSidebar for navigation. Also owns `focusedKey` so card focus
 * state is shared between the sidebar, signal cards, and inspector panel.
 *
 * No localStorage — signals re-fetch on mount.
 *
 * @module AnalysisSignalStore
 */

import { useSyncExternalStore } from "react";
import type { UnifiedSignal } from "../utils/types";

// ── Types ────────────────────────────────────────────────────────────────

export interface AnalysisSignalState {
  /**
   * One de-duplicated list, strongest first.
   *
   * This was two lists split by kind, because the lens drew two grids split by
   * kind. It draws one run of locations now, and a card is a (location × tag
   * group) with sentiment as a group like any other — so there is one list, and
   * the sidebar and the cards column read it through the same grouping.
   */
  signals: UnifiedSignal[];
  focusedKey: string | null;
}

// ── Module-level store ──────────────────────────────────────────────────

const INITIAL: AnalysisSignalState = {
  signals: [],
  focusedKey: null,
};

let state: AnalysisSignalState = { ...INITIAL };
const listeners = new Set<() => void>();

function getSnapshot(): AnalysisSignalState {
  return state;
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

function setState(updater: (prev: AnalysisSignalState) => AnalysisSignalState): void {
  state = updater(state);
  listeners.forEach((l) => l());
}

// ── Actions ─────────────────────────────────────────────────────────────

/** Populate the store with the de-duplicated signal list from AnalysisPage. */
export function setAnalysisSignals(signals: UnifiedSignal[]): void {
  setState((prev) => {
    if (prev.signals === signals) return prev;
    return { ...prev, signals };
  });
}

/** Set the focused signal key (synced with card blue-wash + inspector). */
export function setFocusedSignalKey(key: string | null): void {
  setState((prev) => {
    if (prev.focusedKey === key) return prev;
    return { ...prev, focusedKey: key };
  });
}

/** Reset to defaults. Used for test isolation. */
export function resetAnalysisSignalStore(): void {
  state = { ...INITIAL };
  listeners.forEach((l) => l());
}

// ── React hook ──────────────────────────────────────────────────────────

/** Subscribe to the analysis signal store. Re-renders on any mutation. */
export function useAnalysisSignalStore(): AnalysisSignalState {
  return useSyncExternalStore(subscribe, getSnapshot);
}
