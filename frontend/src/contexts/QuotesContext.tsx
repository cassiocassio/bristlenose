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
import type { TagFilterState } from "../utils/filter";
import { EMPTY_TAG_FILTER } from "../utils/filter";
import {
  putHidden,
  putStarred,
  putEdits,
  putTags,
  putDeletedBadges,
  acceptProposal,
  denyProposal,
} from "../utils/api";

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

function getSnapshot(): QuotesState {
  return state;
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
 * On initial mount both islands call this independently (quotes are
 * exclusive — a dom_id appears in sections OR themes, never both).
 * Default behaviour merges into existing state.
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

    // Merge quotes arrays (or replace)
    const mergedQuotes = replace ? [...quotes] : [...base.quotes, ...quotes];

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
}

export function toggleHide(domId: string, newState: boolean): void {
  setState((prev) => {
    const hidden = { ...prev.hidden };
    if (newState) hidden[domId] = true;
    else delete hidden[domId];
    putHidden(hidden);
    return { ...prev, hidden };
  });
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
    const tags = { ...prev.tags };
    tags[domId] = [...(tags[domId] || []), tag];
    putTags(tagNamesMap(tags));
    return { ...prev, tags };
  });
}

export function removeTag(domId: string, tagName: string): void {
  setState((prev) => {
    const tags = { ...prev.tags };
    tags[domId] = (tags[domId] || []).filter((t) => t.name !== tagName);
    if (tags[domId].length === 0) delete tags[domId];
    putTags(tagNamesMap(tags));
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
