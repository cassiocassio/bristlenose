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
export const SNAP_CLOSE_THRESHOLD = 60;

const LS_OPEN = "bn-inspector-open";
const LS_HEIGHT = "bn-inspector-height";
const LS_TAB = "bn-inspector-tab";

// ── Types ────────────────────────────────────────────────────────────────

export interface InspectorState {
  open: boolean;
  height: number;
  /** Key of the active heatmap tab (empty string = first available). */
  activeTab: string;
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
  return {
    open: readBool(LS_OPEN, false),
    height: readNumber(LS_HEIGHT, DEFAULT_HEIGHT, MIN_HEIGHT, MAX_HEIGHT),
    activeTab: readString(LS_TAB, ""),
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
    return { ...prev, height: clamped };
  });
}

export function setInspectorTab(key: string): void {
  setState((prev) => {
    writeString(LS_TAB, key);
    return { ...prev, activeTab: key };
  });
}

/** Reset to defaults. Used for test isolation. */
export function resetInspectorStore(): void {
  state = {
    open: false,
    height: DEFAULT_HEIGHT,
    activeTab: "",
  };
  listeners.forEach((l) => l());
}

// ── React hook ────────────────────────────────────────────────────────────

/** Subscribe to the inspector store. Re-renders on any mutation. */
export function useInspectorStore(): InspectorState {
  return useSyncExternalStore(subscribe, getSnapshot);
}
