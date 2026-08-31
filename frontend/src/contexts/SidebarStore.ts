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
 * Left sidebar (TOC) has three modes: closed, overlay (temporary peek),
 * and push (permanent, content narrows). Overlay is transient — never
 * persisted to localStorage.
 *
 * @module SidebarStore
 */

import { useSyncExternalStore } from "react";
import { getFrameworkStates, putFrameworkStates, putHiddenTagGroups } from "../utils/api";
import type { FrameworkStatesPutResult } from "../utils/api";
import type { TagFilterState } from "../utils/filter";

// ── Constants ─────────────────────────────────────────────────────────────

// Left nav 240, tag sidebar 280. The left nav deliberately keeps ONE width
// across every lens — switching lens shouldn't resize the furniture — accepting that
// the best width for Signals isn't the best width for Quotes.
//
// Creep this up, never jump it. A 16" screen invites generosity, but
// Bristlenose is usually one window among several — the product under test,
// the report, the mail to the client — and `.center` is `min-width: 0` with no
// viewport-driven collapse, so every px here comes straight out of content.
// The nav trialled its own 200px minimum from 14 Aug 2026; Signals answered
// the question that trial shipped with, its rows being a name plus a
// right-aligned badge that ellipsed on arrival ("Top Navig…", "Beds Cat…").
// 240 is the smaller of the two steps considered — it clears Sessions'
// duration and day-of-week tiers and un-ellipses the shorter Signals rows,
// and leaves the longer titles to a better row layout rather than to width.
const DEFAULT_TOC_WIDTH = 240;
const DEFAULT_TAGS_WIDTH = 280;
const MIN_WIDTH = 200;
const MAX_WIDTH = 480;

const LS_TOC_OPEN = "bn-toc-open";
const LS_TAGS_OPEN = "bn-tags-open";
const LS_TOC_WIDTH = "bn-toc-width";
const LS_TAGS_WIDTH = "bn-tags-width";

// ── Types ────────────────────────────────────────────────────────────────

export type TocMode = "closed" | "overlay" | "push";

// ── State shape ───────────────────────────────────────────────────────────

export interface SidebarState {
  tocMode: TocMode;
  tagsOpen: boolean;
  tocWidth: number;
  tagsWidth: number;
  /**
   * Tag group names whose badges are hidden on quote cards (eye toggle).
   * Persisted to SQLite via /hidden-tag-groups API.
   */
  hiddenTagGroups: Set<string>;
  /**
   * Framework ids the researcher has disabled (the codebook enable/disable
   * switch). Absence = enabled. View-only per design-codebook-library.md
   * Decision A: drives the codebook fold AND report-wide badge hide, never
   * re-apply. Persisted to SQLite via /framework-states API.
   */
  disabledFrameworks: Set<string>;
  /** Lowercase tag name when in solo/focus mode, null otherwise. Ephemeral. */
  soloTag: string | null;
  /** Snapshot of tagFilter from before entering solo mode. */
  savedTagFilter: TagFilterState | null;
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

function readWidth(key: string, fallback: number): number {
  try {
    const v = localStorage.getItem(key);
    if (v === null) return fallback;
    const n = parseInt(v, 10);
    if (isNaN(n)) return fallback;
    return Math.max(MIN_WIDTH, Math.min(MAX_WIDTH, n));
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

// ── Module-level store ────────────────────────────────────────────────────

function loadState(): SidebarState {
  // Backward compat: LS_TOC_OPEN stores "true"/"false". Map to push/closed.
  const tocPersisted = readBool(LS_TOC_OPEN, false);
  return {
    tocMode: tocPersisted ? "push" : "closed",
    tagsOpen: readBool(LS_TAGS_OPEN, false),
    tocWidth: readWidth(LS_TOC_WIDTH, DEFAULT_TOC_WIDTH),
    tagsWidth: readWidth(LS_TAGS_WIDTH, DEFAULT_TAGS_WIDTH),
    hiddenTagGroups: new Set(),
    disabledFrameworks: new Set(),
    soloTag: null,
    savedTagFilter: null,
  };
}

let state: SidebarState = loadState();
const listeners = new Set<() => void>();

/**
 * Framework-state hydration is fetched once per session and guarded — so a
 * later remount (e.g. switching to the Quotes tab after toggling on the Codebook
 * tab) can't refetch stale state. Reset by resetSidebarStore for test isolation.
 *
 * That example only holds while every writer mirrors into this store. A writer
 * that persists to the server WITHOUT mirroring inverts the guard: the remount
 * declines to re-fetch and keeps serving the state from page load, so the toggle
 * appears to do nothing outside the lens it was made in. That is what the
 * navigator did between `baa1aa0e` and `adoptFrameworkDisabled` below.
 */
let frameworkStatesHydrated = false;

/**
 * Bumped on every local framework toggle. The hydrate fetch captures this before
 * awaiting and re-checks it after: if a toggle landed while the GET was in flight,
 * the fetch's (now-stale) result is discarded rather than clobbering the user's
 * just-made choice. Closes the initial-load-latency race the guard alone can't.
 */
let frameworkEditGeneration = 0;

/**
 * The arrangement stashed by the last `hideAllSidebars()`, put back by the next
 * `showAllSidebars()`. Ephemeral on purpose — not persisted, so a fresh session
 * that opens with everything closed has nothing to restore and "show all"
 * falls through to opening all. Reset by resetSidebarStore for test isolation.
 */
let allSidebarsStash: { tocMode: TocMode; tagsOpen: boolean } | null = null;

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

/** Toggle TOC between closed and push (keyboard shortcut `[`). Skips overlay. */
export function toggleToc(): void {
  setState((prev) => {
    const tocMode: TocMode = prev.tocMode === "closed" ? "push" : "closed";
    writeBool(LS_TOC_OPEN, tocMode === "push");
    return { ...prev, tocMode };
  });
}

export function toggleTags(): void {
  setState((prev) => {
    const tagsOpen = !prev.tagsOpen;
    writeBool(LS_TAGS_OPEN, tagsOpen);
    return { ...prev, tagsOpen };
  });
}

/** True when either content sidebar is showing. Drives the Hide↔Show verb. */
export function anySidebarOpen(): boolean {
  return state.tocMode !== "closed" || state.tagsOpen;
}

/**
 * Close both content sidebars, remembering the arrangement so
 * `showAllSidebars()` can put back exactly what was there.
 *
 * The stash is what makes this a Photoshop-style hide-all rather than a plain
 * toggle. Without it, "TOC open, tags closed → hide → show" hands back BOTH —
 * you gain a sidebar you never had. Figma gets away with a bare toggle because
 * its panels are always both present; mixed arrangements are the norm here.
 *
 * No-ops when nothing is open, so a stray second Hide can't overwrite a good
 * stash with an empty one.
 */
export function hideAllSidebars(): void {
  if (!anySidebarOpen()) return;
  allSidebarsStash = { tocMode: state.tocMode, tagsOpen: state.tagsOpen };
  setState((prev) => {
    writeBool(LS_TOC_OPEN, false);
    writeBool(LS_TAGS_OPEN, false);
    return { ...prev, tocMode: "closed", tagsOpen: false };
  });
}

/**
 * Restore the stashed arrangement. With no stash — nothing was hidden this
 * session — "show all" means all, which keeps the menu item live rather than
 * dead on a first press.
 */
export function showAllSidebars(): void {
  // An overlay peek is transient by design and was never a resting state, so a
  // stashed overlay comes back as a real push panel.
  const stashedToc = allSidebarsStash?.tocMode ?? "push";
  const tocMode: TocMode = stashedToc === "overlay" ? "push" : stashedToc;
  const tagsOpen = allSidebarsStash?.tagsOpen ?? true;
  allSidebarsStash = null;
  setState((prev) => {
    writeBool(LS_TOC_OPEN, tocMode === "push");
    writeBool(LS_TAGS_OPEN, tagsOpen);
    return { ...prev, tocMode, tagsOpen };
  });
}

export function toggleBoth(): void {
  if (anySidebarOpen()) hideAllSidebars();
  else showAllSidebars();
}

/** Open TOC as a temporary overlay (hover/rail click). Not persisted. */
export function openTocOverlay(): void {
  setState((prev) => {
    if (prev.tocMode !== "closed") return prev;
    return { ...prev, tocMode: "overlay" };
  });
}

/** Open TOC in push mode (click the list icon). Persisted. */
export function openTocPush(): void {
  setState((prev) => {
    writeBool(LS_TOC_OPEN, true);
    return { ...prev, tocMode: "push" };
  });
}

/** Close TOC from any mode. Persists closed state. */
export function closeToc(): void {
  setState((prev) => {
    writeBool(LS_TOC_OPEN, false);
    return { ...prev, tocMode: "closed" };
  });
}

export function closeTags(): void {
  setState((prev) => {
    writeBool(LS_TAGS_OPEN, false);
    return { ...prev, tagsOpen: false };
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

// ── Framework enable/disable (codebook switch) ────────────────────────────

/**
 * Fetch the persisted per-framework disable state once per session and apply it.
 * Guarded so a remount (Codebook tab ↔ Quotes tab) doesn't refetch and clobber
 * a just-made local toggle whose fire-and-forget PUT hasn't landed yet. Safe to
 * call from any consumer mount (the codebook lens for the fold, TagSidebar for the
 * report-wide badge hide) — the first caller wins.
 */
export function hydrateFrameworkStates(): void {
  if (frameworkStatesHydrated) return;
  frameworkStatesHydrated = true;
  const genAtFetch = frameworkEditGeneration;
  getFrameworkStates()
    .then((states) => {
      if (!states) return;
      // A local toggle landed while this GET was in flight → its result is stale;
      // discard it rather than clobber the user's just-made (and PUT-persisted)
      // choice.
      if (frameworkEditGeneration !== genAtFetch) return;
      const disabled = new Set(
        Object.entries(states)
          .filter(([, enabled]) => !enabled)
          .map(([fid]) => fid),
      );
      setState((prev) => ({ ...prev, disabledFrameworks: disabled }));
    })
    .catch(() => {
      // Allow a later mount to retry if the first fetch failed.
      frameworkStatesHydrated = false;
    });
}

/**
 * Toggle a framework's disabled state (the codebook switch). Disable is functional —
 * "off means off" (design-codebook-state-model.md §8): it folds the section, hides
 * badges report-wide, drops the codebook from the sidebar + autocomplete, and gates
 * re-apply. Persists the full disabled set as {fid: false} (absence = enabled) and
 * returns the PUT result so the caller can surface an on-enable catch-up chip.
 */
export function setFrameworkDisabled(
  frameworkId: string,
  disabled: boolean,
): Promise<FrameworkStatesPutResult> {
  frameworkEditGeneration += 1; // mark a local edit so an in-flight hydrate defers
  const next = new Set(state.disabledFrameworks);
  if (disabled) next.add(frameworkId);
  else next.delete(frameworkId);
  setState((prev) => ({ ...prev, disabledFrameworks: next }));
  const map: Record<string, boolean> = {};
  for (const fid of next) map[fid] = false;
  return putFrameworkStates(map);
}

/**
 * Forget a framework's disabled opinion locally — no network call. Used when a
 * codebook is **uninstalled**: the server drops its ProjectFrameworkState row
 * (absence = enabled), so the in-memory set must shed it too, or a same-session
 * reinstall would resurrect the folded/greyed disabled state (once-per-session
 * hydration won't re-fetch to correct it). Bumps the edit generation so a stale
 * in-flight hydrate can't re-add it.
 */
export function dropFrameworkDisabled(frameworkId: string): void {
  if (!state.disabledFrameworks.has(frameworkId)) return;
  frameworkEditGeneration += 1;
  const next = new Set(state.disabledFrameworks);
  next.delete(frameworkId);
  setState((prev) => ({ ...prev, disabledFrameworks: next }));
}

/**
 * Adopt an authoritative disabled set computed elsewhere — the codebook
 * navigator, which has owned the switch since v1's deletion (`baa1aa0e`).
 *
 * `setFrameworkDisabled` cannot serve that caller. It derives its payload from
 * `state.disabledFrameworks`, which stays empty until `hydrateFrameworkStates`
 * runs — and hydration is called from `TagSidebar`'s mount alone. Opening the
 * codebook lens by deep link therefore reaches the switch with an empty set, and
 * a derive-then-PUT would send an incomplete map to a replacement endpoint: the
 * same wipe as the A5 defect, by a different route. So the navigator owns the
 * write and this owns the mirror.
 *
 * Without it the once-per-session hydration guard means the opposite of what its
 * comment claims: switching to Quotes after toggling on the Codebook lens shows
 * the state from page load, so badges, the tag sidebar and autocomplete keep
 * offering a codebook that is off. Bumping the edit generation matters too — a
 * hydrate GET already in flight then discards its own result instead of
 * clobbering the choice just made.
 */
export function adoptFrameworkDisabled(disabled: Set<string>): void {
  frameworkEditGeneration += 1;
  // The set is authoritative, so a later first mount need not re-fetch.
  frameworkStatesHydrated = true;
  setState((prev) => ({ ...prev, disabledFrameworks: new Set(disabled) }));
}

// ── Solo / focus mode ────────────────────────────────────────────────────

/**
 * Enter solo mode: show only quotes with `tagName`. Snapshots the current
 * tag filter on first entry; switching tags preserves the original snapshot.
 */
export function enterSoloMode(
  tagName: string,
  allTagNames: string[],
  currentTagFilter: TagFilterState,
  applyTagFilter: (f: TagFilterState) => void,
): void {
  const lower = tagName.toLowerCase();
  setState((prev) => {
    const savedTagFilter =
      prev.soloTag === null ? currentTagFilter : prev.savedTagFilter;
    return { ...prev, soloTag: lower, savedTagFilter };
  });
  applyTagFilter({
    unchecked: allTagNames.filter((n) => n.toLowerCase() !== lower),
    noTagsUnchecked: true,
    clearAll: false,
  });
}

/** Exit solo mode and restore the tag filter snapshot. */
export function exitSoloMode(
  applyTagFilter: (f: TagFilterState) => void,
): void {
  const saved = state.savedTagFilter;
  setState((prev) => ({ ...prev, soloTag: null, savedTagFilter: null }));
  applyTagFilter(saved ?? { unchecked: [], noTagsUnchecked: false, clearAll: false });
}

/** Reset to defaults. Used for test isolation. */
export function resetSidebarStore(): void {
  state = {
    tocMode: "closed",
    tagsOpen: false,
    tocWidth: DEFAULT_TOC_WIDTH,
    tagsWidth: DEFAULT_TAGS_WIDTH,
    hiddenTagGroups: new Set(),
    disabledFrameworks: new Set(),
    soloTag: null,
    savedTagFilter: null,
  };
  frameworkStatesHydrated = false;
  frameworkEditGeneration = 0;
  allSidebarsStash = null;
  listeners.forEach((l) => l());
}

// ── React hook ────────────────────────────────────────────────────────────

/** Subscribe to the sidebar store. Re-renders on any mutation. */
export function useSidebarStore(): SidebarState {
  return useSyncExternalStore(subscribe, getSnapshot);
}
