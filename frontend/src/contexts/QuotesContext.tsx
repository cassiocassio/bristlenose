/**
 * QuotesStore — module-level store for cross-island quote state.
 *
 * Uses a plain TypeScript module as the single source of truth for
 * quote mutations (star, hide, edit, tag, badge, proposed tags).
 * React components subscribe via `useQuotesStore()` which uses
 * `useSyncExternalStore` — works across separate React roots
 * without needing a shared context provider.
 *
 * Mutation flow: update store → notify subscribers (re-render) →
 * fire-and-forget PUT to API (same pattern as the old QuoteGroup
 * local state, but now shared).
 */

import { useSyncExternalStore } from "react";
import type { TagResponse, ProposedTagBrief, QuoteResponse } from "../utils/types";
import type { TagFilterState, FilterState } from "../utils/filter";
import { EMPTY_TAG_FILTER, filterQuotes } from "../utils/filter";
import {
  putHidden,
  putStarred,
  putEdits,
  putTags,
  putDeletedBadges,
  acceptProposal,
  denyProposal,
} from "../utils/api";
import { announce } from "../utils/announce";
import i18n from "../i18n";

// ── State shape ──────────────────────────────────────────────────────────

export interface QuotesState {
  hidden: Record<string, boolean>;
  starred: Record<string, boolean>;
  edits: Record<string, string>;
  tags: Record<string, TagResponse[]>;
  deletedBadges: Record<string, string[]>;
  proposedTags: Record<string, ProposedTagBrief[]>;
  /** All quotes from the API — populated by initFromQuotes. */
  quotes: QuoteResponse[];
  /** Current view mode for the quotes tab. */
  viewMode: "all" | "starred";
  /** Current search query (min 3 chars to activate filtering). */
  searchQuery: string;
  /** Tag filter state — tracks which tags are unchecked. */
  tagFilter: TagFilterState;
}

function emptyState(): QuotesState {
  return {
    hidden: {},
    starred: {},
    edits: {},
    tags: {},
    deletedBadges: {},
    proposedTags: {},
    quotes: [],
    viewMode: "all",
    searchQuery: "",
    tagFilter: EMPTY_TAG_FILTER,
  };
}

// ── Module-level store ───────────────────────────────────────────────────

let state: QuotesState = emptyState();
const listeners = new Set<() => void>();

// ── Last-used tag (for double-t quick-repeat) ─────────────────────────────

/** The most recently applied tag (full response, set by addTag). */
let lastUsedTag: TagResponse | null = null;

/** Get the last-used tag (full TagResponse for re-application with colours). */
export function getLastUsedTag(): TagResponse | null {
  return lastUsedTag;
}

function getSnapshot(): QuotesState {
  return state;
}

/** Non-hook read of current store state — for imperative event handlers. */
export function getQuotesSnapshot(): QuotesState {
  return state;
}

/** The quotes currently visible on the Quotes screen — i.e. after search,
 *  view-mode, tag-filter and hidden are applied. This is the canonical "all"
 *  for exports: hidden and filtered-out quotes are excluded. Shared with the
 *  SPA dropdown (which filters the same way) so both surfaces agree. */
export function getVisibleQuotes(store: QuotesState): QuoteResponse[] {
  const f: FilterState = {
    searchQuery: store.searchQuery,
    viewMode: store.viewMode,
    tagFilter: store.tagFilter,
    hidden: store.hidden,
    starred: store.starred,
    tags: store.tags,
  };
  return filterQuotes(store.quotes, f);
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

function setState(updater: (prev: QuotesState) => QuotesState): void {
  state = updater(state);
  listeners.forEach((l) => l());
}

// ── Initialisation ───────────────────────────────────────────────────────

/**
 * Populate the store from an API quotes response.
 *
 * On initial mount both islands (QuoteSections + QuoteThemes) call this
 * independently, each with the *full* quote set (sections + themes). The
 * merge therefore dedups by dom_id — a plain concat would double every
 * quote (and so double every tag count in the sidebar). Last writer wins
 * per dom_id; the two islands fetch identical data, so copies are
 * equivalent. The dom_id-keyed state maps below are already idempotent.
 *
 * Pass `replace: true` on re-fetch (bn:tags-changed) to atomically
 * clear-and-set, avoiding race conditions between the two islands.
 */
export function initFromQuotes(quotes: QuoteResponse[], replace = false): void {
  setState((prev) => {
    const base = replace ? emptyState() : prev;
    const hidden = { ...base.hidden };
    const starred = { ...base.starred };
    const edits = { ...base.edits };
    const tags = { ...base.tags };
    const deletedBadges = { ...base.deletedBadges };
    const proposedTags = { ...base.proposedTags };

    for (const q of quotes) {
      if (q.is_hidden) hidden[q.dom_id] = true;
      if (q.is_starred) starred[q.dom_id] = true;
      if (q.edited_text) edits[q.dom_id] = q.edited_text;
      if (q.tags.length > 0) tags[q.dom_id] = [...q.tags];
      if (q.deleted_badges.length > 0) deletedBadges[q.dom_id] = [...q.deleted_badges];
      if (q.proposed_tags.length > 0) proposedTags[q.dom_id] = [...q.proposed_tags];
    }

    // Merge quotes by dom_id (idempotent): both islands call this with the
    // full set on mount, so a plain concat would double-count. Last writer
    // wins per dom_id.
    const byId = new Map<string, QuoteResponse>();
    if (!replace) for (const q of base.quotes) byId.set(q.dom_id, q);
    for (const q of quotes) byId.set(q.dom_id, q);
    const mergedQuotes = [...byId.values()];

    return {
      ...base,
      hidden,
      starred,
      edits,
      tags,
      deletedBadges,
      proposedTags,
      quotes: mergedQuotes,
    };
  });
}

/** Clear all state. Used for test isolation and before re-fetch. */
export function resetStore(): void {
  state = emptyState();
  lastUsedTag = null;
  listeners.forEach((l) => l());
}

// ── Tag-name extraction helper ───────────────────────────────────────────

function tagNamesMap(tags: Record<string, TagResponse[]>): Record<string, string[]> {
  const result: Record<string, string[]> = {};
  for (const [id, ts] of Object.entries(tags)) {
    if (ts.length > 0) result[id] = ts.map((t) => t.name);
  }
  return result;
}

// ── Action functions ─────────────────────────────────────────────────────

export function toggleStar(domId: string, newState: boolean): void {
  setState((prev) => {
    const starred = { ...prev.starred };
    if (newState) starred[domId] = true;
    else delete starred[domId];
    putStarred(starred);
    return { ...prev, starred };
  });
  announce(i18n.t(newState ? "announce.starred" : "announce.unstarred"));
}

export function toggleHide(domId: string, newState: boolean): void {
  setState((prev) => {
    const hidden = { ...prev.hidden };
    if (newState) hidden[domId] = true;
    else delete hidden[domId];
    putHidden(hidden);
    return { ...prev, hidden };
  });
  announce(i18n.t(newState ? "announce.hidden" : "announce.restored"));
}

export function commitEdit(domId: string, newText: string): void {
  setState((prev) => {
    const edits = { ...prev.edits };
    edits[domId] = newText;
    putEdits(edits);
    return { ...prev, edits };
  });
}

export function addTag(domId: string, tag: TagResponse): void {
  setState((prev) => {
    const existing = prev.tags[domId] || [];
    // Prevent duplicate tags (case-insensitive).
    if (existing.some((t) => t.name.toLowerCase() === tag.name.toLowerCase())) {
      return prev;
    }
    const tags = { ...prev.tags };
    tags[domId] = [...existing, tag];
    putTags(tagNamesMap(tags));
    lastUsedTag = tag;
    announce(i18n.t("announce.tagAdded", { name: tag.name }));
    return { ...prev, tags };
  });
}

export function removeTag(domId: string, tagName: string): void {
  setState((prev) => {
    const tags = { ...prev.tags };
    tags[domId] = (tags[domId] || []).filter((t) => t.name !== tagName);
    if (tags[domId].length === 0) delete tags[domId];
    putTags(tagNamesMap(tags));
    announce(i18n.t("announce.tagRemoved", { name: tagName }));
    return { ...prev, tags };
  });
}

export function deleteBadge(domId: string, sentiment: string): void {
  setState((prev) => {
    const deletedBadges = { ...prev.deletedBadges };
    deletedBadges[domId] = [...(deletedBadges[domId] || []), sentiment];
    putDeletedBadges(deletedBadges);
    return { ...prev, deletedBadges };
  });
}

export function restoreBadges(domId: string): void {
  setState((prev) => {
    const deletedBadges = { ...prev.deletedBadges };
    delete deletedBadges[domId];
    putDeletedBadges(deletedBadges);
    return { ...prev, deletedBadges };
  });
}

export function acceptProposedTag(
  domId: string,
  proposalId: number,
  tag: TagResponse,
): void {
  setState((prev) => {
    const proposedTags = { ...prev.proposedTags };
    proposedTags[domId] = (proposedTags[domId] || []).filter((p) => p.id !== proposalId);
    if (proposedTags[domId].length === 0) delete proposedTags[domId];

    const tags = { ...prev.tags };
    tags[domId] = [...(tags[domId] || []), tag];
    // No putTags — acceptProposal handles server-side tag creation.
    return { ...prev, proposedTags, tags };
  });
  acceptProposal(proposalId).catch((err) =>
    console.error("Accept proposal failed:", err),
  );
}

export function denyProposedTag(domId: string, proposalId: number): void {
  setState((prev) => {
    const proposedTags = { ...prev.proposedTags };
    proposedTags[domId] = (proposedTags[domId] || []).filter((p) => p.id !== proposalId);
    if (proposedTags[domId].length === 0) delete proposedTags[domId];
    return { ...prev, proposedTags };
  });
  denyProposal(proposalId).catch((err) =>
    console.error("Deny proposal failed:", err),
  );
}

// ── Toolbar actions (Step 4) ─────────────────────────────────────────

/** Set the search query. No API call — UI-only state. */
export function setSearchQuery(query: string): void {
  setState((prev) => ({ ...prev, searchQuery: query }));
}

/** Set the view mode (all / starred). No API call — UI-only state. */
export function setViewMode(mode: "all" | "starred"): void {
  setState((prev) => ({ ...prev, viewMode: mode }));
}

/** Set the tag filter state. No API call — UI-only state. */
export function setTagFilter(filter: TagFilterState): void {
  setState((prev) => ({ ...prev, tagFilter: filter }));
}

// ── React hook ───────────────────────────────────────────────────────────

/** Subscribe to the full quotes store. Re-renders on any mutation. */
export function useQuotesStore(): QuotesState {
  return useSyncExternalStore(subscribe, getSnapshot);
}

/** Derived export counts. Cached so the snapshot is referentially stable
 *  unless total/starred actually change — `useSyncExternalStore` then bails
 *  out of re-render, so subscribing this in a layout doesn't re-render the
 *  shell on every unrelated store mutation (tag add, edit, search…). */
let cachedCounts: { total: number; starred: number } = { total: 0, starred: 0 };
function getCountsSnapshot(): { total: number; starred: number } {
  // Counts mirror the export scopes: "All" = visible quotes (excludes
  // hidden/filtered), "Starred" = visible quotes that are starred.
  const visible = getVisibleQuotes(state);
  let starred = 0;
  for (const q of visible) if (state.starred[q.dom_id]) starred++;
  const total = visible.length;
  if (total !== cachedCounts.total || starred !== cachedCounts.starred) {
    cachedCounts = { total, starred };
  }
  return cachedCounts;
}

/** Reactive {total, starred} quote counts. Stable across unrelated mutations. */
export function useQuoteCounts(): { total: number; starred: number } {
  return useSyncExternalStore(subscribe, getCountsSnapshot);
}
