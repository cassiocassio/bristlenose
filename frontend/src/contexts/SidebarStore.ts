/**
 * SidebarStore — module-level store for dual-sidebar layout state.
 *
 * Uses the same pattern as QuotesStore: plain module-level state object +
 * useSyncExternalStore. Accessible from keyboard shortcuts and layout
 * components without provider nesting.
 *
 * State is persisted to localStorage so sidebar open/close and widths
 * survive page reloads.
 *
 * @module SidebarStore
 */

import { useSyncExternalStore } from "react";

// ── Constants ─────────────────────────────────────────────────────────────

const DEFAULT_WIDTH = 280;
const MIN_WIDTH = 200;
const MAX_WIDTH = 480;

const LS_TOC_OPEN = "bn-toc-open";
const LS_TAGS_OPEN = "bn-tags-open";
const LS_TOC_WIDTH = "bn-toc-width";
const LS_TAGS_WIDTH = "bn-tags-width";

// ── State shape ───────────────────────────────────────────────────────────

export interface SidebarState {
  tocOpen: boolean;
  tagsOpen: boolean;
  tocWidth: number;
  tagsWidth: number;
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

function readWidth(key: string): number {
  try {
    const v = localStorage.getItem(key);
    if (v === null) return DEFAULT_WIDTH;
    const n = parseInt(v, 10);
    if (isNaN(n)) return DEFAULT_WIDTH;
    return Math.max(MIN_WIDTH, Math.min(MAX_WIDTH, n));
  } catch {
    return DEFAULT_WIDTH;
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

// ── Module-level store ────────────────────────────────────────────────────

function loadState(): SidebarState {
  return {
    tocOpen: readBool(LS_TOC_OPEN, false),
    tagsOpen: readBool(LS_TAGS_OPEN, false),
    tocWidth: readWidth(LS_TOC_WIDTH),
    tagsWidth: readWidth(LS_TAGS_WIDTH),
  };
}

let state: SidebarState = loadState();
const listeners = new Set<() => void>();

function getSnapshot(): SidebarState {
  return state;
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

function setState(updater: (prev: SidebarState) => SidebarState): void {
  state = updater(state);
  listeners.forEach((l) => l());
}

// ── Actions ───────────────────────────────────────────────────────────────

export function toggleToc(): void {
  setState((prev) => {
    const tocOpen = !prev.tocOpen;
    writeBool(LS_TOC_OPEN, tocOpen);
    return { ...prev, tocOpen };
  });
}

export function toggleTags(): void {
  setState((prev) => {
    const tagsOpen = !prev.tagsOpen;
    writeBool(LS_TAGS_OPEN, tagsOpen);
    return { ...prev, tagsOpen };
  });
}

export function toggleBoth(): void {
  setState((prev) => {
    // Any open → close all; all closed → open both
    const anyOpen = prev.tocOpen || prev.tagsOpen;
    const tocOpen = !anyOpen;
    const tagsOpen = !anyOpen;
    writeBool(LS_TOC_OPEN, tocOpen);
    writeBool(LS_TAGS_OPEN, tagsOpen);
    return { ...prev, tocOpen, tagsOpen };
  });
}

export function closeToc(): void {
  setState((prev) => {
    writeBool(LS_TOC_OPEN, false);
    return { ...prev, tocOpen: false };
  });
}

export function closeTags(): void {
  setState((prev) => {
    writeBool(LS_TAGS_OPEN, false);
    return { ...prev, tagsOpen: false };
  });
}

export function setTocWidth(width: number): void {
  const clamped = Math.max(MIN_WIDTH, Math.min(MAX_WIDTH, width));
  setState((prev) => {
    writeNumber(LS_TOC_WIDTH, clamped);
    return { ...prev, tocWidth: clamped };
  });
}

export function setTagsWidth(width: number): void {
  const clamped = Math.max(MIN_WIDTH, Math.min(MAX_WIDTH, width));
  setState((prev) => {
    writeNumber(LS_TAGS_WIDTH, clamped);
    return { ...prev, tagsWidth: clamped };
  });
}

/** Reset to defaults. Used for test isolation. */
export function resetSidebarStore(): void {
  state = {
    tocOpen: false,
    tagsOpen: false,
    tocWidth: DEFAULT_WIDTH,
    tagsWidth: DEFAULT_WIDTH,
  };
  listeners.forEach((l) => l());
}

// ── React hook ────────────────────────────────────────────────────────────

/** Subscribe to the sidebar store. Re-renders on any mutation. */
export function useSidebarStore(): SidebarState {
  return useSyncExternalStore(subscribe, getSnapshot);
}
