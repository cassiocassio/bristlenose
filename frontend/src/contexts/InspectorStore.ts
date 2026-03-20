/**
 * InspectorStore — module-level store for the analysis bottom panel.
 *
 * DevTools-style collapsible inspector containing heatmap matrices.
 * Follows the same pattern as SidebarStore: plain module-level state +
 * useSyncExternalStore + localStorage persistence.
 *
 * @module InspectorStore
 */

import { useSyncExternalStore } from "react";

// ── Constants ─────────────────────────────────────────────────────────────

export const DEFAULT_HEIGHT = 320;
export const MIN_HEIGHT = 150;
export const MAX_HEIGHT = 600;
export const SNAP_CLOSE_THRESHOLD = 80;

const LS_OPEN = "bn-inspector-open";
const LS_HEIGHT = "bn-inspector-height";
const LS_SOURCE = "bn-inspector-source";
const LS_DIMENSION = "bn-inspector-dimension";

// ── Types ────────────────────────────────────────────────────────────────

export type InspectorDimension = "section" | "theme";

export interface InspectorState {
  open: boolean;
  height: number;
  /** Whether the user has manually dragged to set a height. */
  hasManualHeight: boolean;
  /** Key of the active heatmap source (empty string = first available). */
  activeSource: string;
  /** Whether to show the section or theme dimension of the active source. */
  activeDimension: InspectorDimension;
}

// ── localStorage helpers ──────────────────────────────────────────────────

function readBool(key: string, fallback: boolean): boolean {
  try {
    const v = localStorage.getItem(key);
    if (v === null) return fallback;
    return v === "true";
  } catch {
    return fallback;
  }
}

function readNumber(key: string, fallback: number, min: number, max: number): number {
  try {
    const v = localStorage.getItem(key);
    if (v === null) return fallback;
    const n = parseInt(v, 10);
    if (isNaN(n)) return fallback;
    return Math.max(min, Math.min(max, n));
  } catch {
    return fallback;
  }
}

function readString(key: string, fallback: string): string {
  try {
    return localStorage.getItem(key) ?? fallback;
  } catch {
    return fallback;
  }
}

function writeBool(key: string, value: boolean): void {
  try {
    localStorage.setItem(key, String(value));
  } catch {
    // localStorage full or unavailable — ignore
  }
}

function writeNumber(key: string, value: number): void {
  try {
    localStorage.setItem(key, String(value));
  } catch {
    // localStorage full or unavailable — ignore
  }
}

function writeString(key: string, value: string): void {
  try {
    localStorage.setItem(key, value);
  } catch {
    // localStorage full or unavailable — ignore
  }
}

// ── Module-level store ────────────────────────────────────────────────────

function loadState(): InspectorState {
  const height = readNumber(LS_HEIGHT, 0, 0, MAX_HEIGHT);
  return {
    open: readBool(LS_OPEN, false),
    height: height || DEFAULT_HEIGHT,
    hasManualHeight: height > 0,
    activeSource: readString(LS_SOURCE, ""),
    activeDimension: readString(LS_DIMENSION, "section") as InspectorDimension,
  };
}

let state: InspectorState = loadState();
const listeners = new Set<() => void>();

function getSnapshot(): InspectorState {
  return state;
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

function setState(updater: (prev: InspectorState) => InspectorState): void {
  state = updater(state);
  listeners.forEach((l) => l());
}

// ── Actions ───────────────────────────────────────────────────────────────

export function toggleInspector(): void {
  setState((prev) => {
    const open = !prev.open;
    writeBool(LS_OPEN, open);
    return { ...prev, open };
  });
}

export function openInspector(): void {
  setState((prev) => {
    if (prev.open) return prev;
    writeBool(LS_OPEN, true);
    return { ...prev, open: true };
  });
}

export function closeInspector(): void {
  setState((prev) => {
    if (!prev.open) return prev;
    writeBool(LS_OPEN, false);
    return { ...prev, open: false };
  });
}

export function setInspectorHeight(height: number): void {
  const clamped = Math.max(MIN_HEIGHT, Math.min(MAX_HEIGHT, height));
  setState((prev) => {
    writeNumber(LS_HEIGHT, clamped);
    return { ...prev, height: clamped, hasManualHeight: true };
  });
}

export function setInspectorSource(key: string): void {
  setState((prev) => {
    writeString(LS_SOURCE, key);
    return { ...prev, activeSource: key };
  });
}

export function setInspectorDimension(dim: InspectorDimension): void {
  setState((prev) => {
    writeString(LS_DIMENSION, dim);
    return { ...prev, activeDimension: dim };
  });
}

export function setInspectorSourceAndDimension(
  key: string,
  dim: InspectorDimension,
): void {
  setState((prev) => {
    writeString(LS_SOURCE, key);
    writeString(LS_DIMENSION, dim);
    return { ...prev, activeSource: key, activeDimension: dim };
  });
}

/** Reset to defaults. Used for test isolation. */
export function resetInspectorStore(): void {
  state = {
    open: false,
    height: DEFAULT_HEIGHT,
    hasManualHeight: false,
    activeSource: "",
    activeDimension: "section",
  };
  listeners.forEach((l) => l());
}

// ── React hook ────────────────────────────────────────────────────────────

/** Subscribe to the inspector store. Re-renders on any mutation. */
export function useInspectorStore(): InspectorState {
  return useSyncExternalStore(subscribe, getSnapshot);
}
