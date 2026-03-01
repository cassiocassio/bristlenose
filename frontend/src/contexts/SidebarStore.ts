/**
 * SidebarStore — module-level store for dual-sidebar layout state.
 *
 * Uses the same pattern as QuotesStore: plain module-level state object +
 * useSyncExternalStore. Accessible from keyboard shortcuts and layout
 * components without provider nesting.
 *
 * State is persisted to localStorage so sidebar open/close and widths
 * survive page reloads. `hiddenTagGroups` is persisted to SQLite via
 * the `/hidden-tag-groups` API (fire-and-forget PUTs).
 *
 * @module SidebarStore
 */

import { useSyncExternalStore } from "react";
import { putHiddenTagGroups } from "../utils/api";

// ── Constants ─────────────────────────────────────────────────────────────

const DEFAULT_WIDTH = 280;
const MIN_WIDTH = 200;
const MAX_WIDTH = 320;

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
  /**
   * Tag group names whose badges are hidden on quote cards (eye toggle).
   * Persisted to SQLite via /hidden-tag-groups API.
   */
  hiddenTagGroups: Set<string>;
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
    hiddenTagGroups: new Set(),
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

export function openToc(): void {
  setState((prev) => {
    if (prev.tocOpen) return prev;
    writeBool(LS_TOC_OPEN, true);
    return { ...prev, tocOpen: true };
  });
}

export function openTags(): void {
  setState((prev) => {
    if (prev.tagsOpen) return prev;
    writeBool(LS_TAGS_OPEN, true);
    return { ...prev, tagsOpen: true };
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

/**
 * Hydrate hidden tag groups from the API on mount.
 * Replaces any existing set wholesale.
 */
export function initHiddenTagGroups(groupNames: string[]): void {
  setState((prev) => ({
    ...prev,
    hiddenTagGroups: new Set(groupNames),
  }));
}

/**
 * Toggle a tag group's badge visibility on quote cards.
 * When hidden, badges for tags in this group are suppressed.
 * Persists to SQLite via fire-and-forget PUT.
 */
export function toggleTagGroupHidden(groupName: string): void {
  setState((prev) => {
    const next = new Set(prev.hiddenTagGroups);
    if (next.has(groupName)) next.delete(groupName);
    else next.add(groupName);
    putHiddenTagGroups([...next]);
    return { ...prev, hiddenTagGroups: next };
  });
}

/**
 * Hide all tag groups within a framework (bulk eye toggle).
 * Pass the group names belonging to that framework.
 * Persists to SQLite via fire-and-forget PUT.
 */
export function setTagGroupsHidden(groupNames: string[], hidden: boolean): void {
  setState((prev) => {
    const next = new Set(prev.hiddenTagGroups);
    for (const name of groupNames) {
      if (hidden) next.add(name);
      else next.delete(name);
    }
    putHiddenTagGroups([...next]);
    return { ...prev, hiddenTagGroups: next };
  });
}

/** Reset to defaults. Used for test isolation. */
export function resetSidebarStore(): void {
  state = {
    tocOpen: false,
    tagsOpen: false,
    tocWidth: DEFAULT_WIDTH,
    tagsWidth: DEFAULT_WIDTH,
    hiddenTagGroups: new Set(),
  };
  listeners.forEach((l) => l());
}

// ── React hook ────────────────────────────────────────────────────────────

/** Subscribe to the sidebar store. Re-renders on any mutation. */
export function useSidebarStore(): SidebarState {
  return useSyncExternalStore(subscribe, getSnapshot);
}
