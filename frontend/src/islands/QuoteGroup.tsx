/**
 * QuoteGroup — a group of quote cards with editable heading,
 * optional description, and hidden-quotes counter.
 *
 * Owns local state for all quotes in the group (star, hidden,
 * edited text, tags, deleted badges). Mutations are optimistic:
 * React state updates immediately, then fire-and-forget PUT
 * calls sync to the server.
 */

import { useState, useCallback, useRef, useMemo } from "react";
import { Counter, EditableText } from "../components";
import type { CounterItem } from "../components/Counter";
import type { ProposedTagBrief, QuoteResponse, TagResponse } from "../utils/types";
import {
  acceptProposal,
  denyProposal,
  putHidden,
  putStarred,
  putEdits,
  putTags,
  putDeletedBadges,
} from "../utils/api";
import { formatTimecode, stripSmartQuotes } from "../utils/format";
import { QuoteCard } from "./QuoteCard";

// ── Animation constants ─────────────────────────────────────────────────

const HIDE_DURATION = 300; // ms — matches vanilla JS _HIDE_DURATION

// ── Per-quote local state ───────────────────────────────────────────────

interface QuoteLocalState {
  isStarred: boolean;
  isHidden: boolean;
  editedText: string | null;
  tags: TagResponse[];
  deletedBadges: string[];
  proposedTags: ProposedTagBrief[];
}

function initialState(q: QuoteResponse): QuoteLocalState {
  return {
    isStarred: q.is_starred,
    isHidden: q.is_hidden,
    editedText: q.edited_text,
    tags: [...q.tags],
    deletedBadges: [...q.deleted_badges],
    proposedTags: [...q.proposed_tags],
  };
}

// ── Props ───────────────────────────────────────────────────────────────

interface QuoteGroupProps {
  /** Anchor ID for deep-linking (e.g. "section-login" or "theme-trust"). */
  anchor: string;
  /** Display label (e.g. "Login flow" or "Trust & credibility"). */
  label: string;
  /** Optional description below the heading. */
  description: string;
  /** Heading edit key prefix ("section" or "theme"). */
  itemType: string;
  /** All quotes in this group. */
  quotes: QuoteResponse[];
  /** Full tag vocabulary for auto-suggest across all groups. */
  tagVocabulary: string[];
  /** Whether video/audio is available (for timecode links). */
  hasMedia: boolean;
  /** Called after any state mutation with the full state maps (for parent sync). */
  onStateChange?: (stateMaps: {
    hidden: Record<string, boolean>;
    starred: Record<string, boolean>;
    edits: Record<string, string>;
    tags: Record<string, string[]>;
    deletedBadges: Record<string, string[]>;
  }) => void;
}

export function QuoteGroup({
  anchor,
  label,
  description,
  itemType,
  quotes,
  tagVocabulary,
  hasMedia,
  onStateChange,
}: QuoteGroupProps) {
  // ── State ─────────────────────────────────────────────────────────────

  const [stateMap, setStateMap] = useState<Record<string, QuoteLocalState>>(
    () => {
      const map: Record<string, QuoteLocalState> = {};
      for (const q of quotes) {
        map[q.dom_id] = initialState(q);
      }
      return map;
    },
  );

  // Heading/description edit state.
  const [headingText, setHeadingText] = useState(label);
  const [headingEdited, setHeadingEdited] = useState(false);
  const [isEditingHeading, setIsEditingHeading] = useState(false);
  const [descText, setDescText] = useState(description);
  const [descEdited, setDescEdited] = useState(false);
  const [isEditingDesc, setIsEditingDesc] = useState(false);

  // Counter dropdown state.
  const [isCounterOpen, setIsCounterOpen] = useState(false);

  // Track quotes in hide animation (shown with .bn-hiding class).
  const [hidingIds, setHidingIds] = useState<Set<string>>(new Set());
  const hideTimers = useRef<Map<string, ReturnType<typeof setTimeout>>>(new Map());

  // ── Derived ───────────────────────────────────────────────────────────

  const hiddenQuotes = useMemo(
    () => quotes.filter((q) => stateMap[q.dom_id]?.isHidden),
    [quotes, stateMap],
  );

  const counterItems: CounterItem[] = useMemo(
    () =>
      hiddenQuotes.map((q) => ({
        domId: q.dom_id,
        timecode: formatTimecode(q.start_timecode),
        seconds: q.start_timecode,
        endSeconds: q.end_timecode,
        participantId: q.participant_id,
        previewText: stripSmartQuotes(
          stateMap[q.dom_id]?.editedText || q.text,
        ),
        hasMedia,
      })),
    [hiddenQuotes, stateMap, hasMedia],
  );

  // Tag name → colour lookup from existing quote data (for manual tag add).
  const tagColourMap = useMemo(() => {
    const map: Record<string, { colour_set: string; colour_index: number }> = {};
    for (const q of quotes) {
      for (const t of q.tags) {
        if (t.colour_set && !map[t.name]) {
          map[t.name] = { colour_set: t.colour_set, colour_index: t.colour_index };
        }
      }
      for (const pt of q.proposed_tags) {
        if (pt.colour_set && !map[pt.tag_name]) {
          map[pt.tag_name] = { colour_set: pt.colour_set, colour_index: pt.colour_index };
        }
      }
    }
    return map;
  }, [quotes]);

  // ── State sync helper ─────────────────────────────────────────────────

  const syncToServer = useCallback(
    (newMap: Record<string, QuoteLocalState>) => {
      // Build full state maps for the server.
      const hidden: Record<string, boolean> = {};
      const starred: Record<string, boolean> = {};
      const edits: Record<string, string> = {};
      const tags: Record<string, string[]> = {};
      const badges: Record<string, string[]> = {};

      for (const [domId, state] of Object.entries(newMap)) {
        if (state.isHidden) hidden[domId] = true;
        if (state.isStarred) starred[domId] = true;
        if (state.editedText) edits[domId] = state.editedText;
        if (state.tags.length > 0) tags[domId] = state.tags.map((t) => t.name);
        if (state.deletedBadges.length > 0)
          badges[domId] = state.deletedBadges;
      }

      // Fire-and-forget PUT calls.
      putHidden(hidden);
      putStarred(starred);
      putEdits(edits);
      putTags(tags);
      putDeletedBadges(badges);

      onStateChange?.({ hidden, starred, edits, tags, deletedBadges: badges });
    },
    [onStateChange],
  );

  // ── Mutation handlers ─────────────────────────────────────────────────

  const updateQuote = useCallback(
    (
      domId: string,
      updater: (prev: QuoteLocalState) => QuoteLocalState,
    ) => {
      setStateMap((prev) => {
        const updated = { ...prev, [domId]: updater(prev[domId]) };
        syncToServer(updated);
        return updated;
      });
    },
    [syncToServer],
  );

  const handleToggleStar = useCallback(
    (domId: string, newState: boolean) => {
      updateQuote(domId, (s) => ({ ...s, isStarred: newState }));
    },
    [updateQuote],
  );

  const handleToggleHide = useCallback(
    (domId: string, newState: boolean) => {
      if (newState) {
        // Start hide animation.
        setHidingIds((prev) => new Set(prev).add(domId));
        const timer = setTimeout(() => {
          setHidingIds((prev) => {
            const next = new Set(prev);
            next.delete(domId);
            return next;
          });
          updateQuote(domId, (s) => ({ ...s, isHidden: true }));
          hideTimers.current.delete(domId);
        }, HIDE_DURATION);
        hideTimers.current.set(domId, timer);
      } else {
        // Unhide immediately.
        updateQuote(domId, (s) => ({ ...s, isHidden: false }));
      }
    },
    [updateQuote],
  );

  const handleEditCommit = useCallback(
    (domId: string, newText: string) => {
      updateQuote(domId, (s) => ({ ...s, editedText: newText }));
    },
    [updateQuote],
  );

  const handleTagAdd = useCallback(
    (domId: string, tagName: string) => {
      const ci = tagColourMap[tagName];
      updateQuote(domId, (s) => ({
        ...s,
        tags: [
          ...s.tags,
          {
            name: tagName,
            codebook_group: "Uncategorised",
            colour_set: ci?.colour_set ?? "",
            colour_index: ci?.colour_index ?? 0,
          },
        ],
      }));
    },
    [updateQuote, tagColourMap],
  );

  const handleTagRemove = useCallback(
    (domId: string, tagName: string) => {
      updateQuote(domId, (s) => ({
        ...s,
        tags: s.tags.filter((t) => t.name !== tagName),
      }));
    },
    [updateQuote],
  );

  const handleBadgeDelete = useCallback(
    (domId: string, sentiment: string) => {
      updateQuote(domId, (s) => ({
        ...s,
        deletedBadges: [...s.deletedBadges, sentiment],
      }));
    },
    [updateQuote],
  );

  const handleBadgeRestore = useCallback(
    (domId: string) => {
      updateQuote(domId, (s) => ({ ...s, deletedBadges: [] }));
    },
    [updateQuote],
  );

  // ── Proposed tag handlers ─────────────────────────────────────────────

  const handleProposedAccept = useCallback(
    (domId: string, proposalId: number, tagName: string) => {
      // Optimistically: remove proposed badge, add regular user tag.
      // Carry colour from the proposal so the accepted tag keeps its colour.
      updateQuote(domId, (s) => {
        const pt = s.proposedTags.find((p) => p.id === proposalId);
        return {
          ...s,
          proposedTags: s.proposedTags.filter((p) => p.id !== proposalId),
          tags: [
            ...s.tags,
            {
              name: tagName,
              codebook_group: pt?.group_name ?? "Uncategorised",
              colour_set: pt?.colour_set ?? "",
              colour_index: pt?.colour_index ?? 0,
            },
          ],
        };
      });
      acceptProposal(proposalId).catch((err) =>
        console.error("Accept proposal failed:", err),
      );
    },
    [updateQuote],
  );

  const handleProposedDeny = useCallback(
    (domId: string, proposalId: number) => {
      updateQuote(domId, (s) => ({
        ...s,
        proposedTags: s.proposedTags.filter((pt) => pt.id !== proposalId),
      }));
      denyProposal(proposalId).catch((err) =>
        console.error("Deny proposal failed:", err),
      );
    },
    [updateQuote],
  );

  // ── Counter handlers ──────────────────────────────────────────────────

  const handleCounterToggle = useCallback(() => {
    setIsCounterOpen((prev) => !prev);
  }, []);

  const handleUnhide = useCallback(
    (domId: string) => {
      handleToggleHide(domId, false);
      setIsCounterOpen(false);
    },
    [handleToggleHide],
  );

  const handleUnhideAll = useCallback(() => {
    for (const q of hiddenQuotes) {
      handleToggleHide(q.dom_id, false);
    }
    setIsCounterOpen(false);
  }, [hiddenQuotes, handleToggleHide]);

  // ── Heading/description handlers ──────────────────────────────────────

  const handleHeadingCommit = useCallback(
    (newText: string) => {
      setHeadingText(newText);
      setHeadingEdited(newText !== label);
      setIsEditingHeading(false);
      // Heading edits use the same edits API with a special key.
      putEdits({ [`${anchor}:title`]: newText });
    },
    [label, anchor],
  );

  const handleDescCommit = useCallback(
    (newText: string) => {
      setDescText(newText);
      setDescEdited(newText !== description);
      setIsEditingDesc(false);
      putEdits({ [`${anchor}:desc`]: newText });
    },
    [description, anchor],
  );

  // ── Render ────────────────────────────────────────────────────────────

  return (
    <>
      <h3 id={anchor}>
        <EditableText
          value={headingText}
          originalValue={label}
          isEditing={isEditingHeading}
          committed={headingEdited}
          onCommit={handleHeadingCommit}
          onCancel={() => setIsEditingHeading(false)}
          trigger="external"
          className="editable-text"
          data-testid={`bn-group-${anchor}-title`}
          data-edit-key={`${anchor}:title`}
        />
        {" "}
        <button
          className="edit-pencil edit-pencil-inline"
          aria-label={`Edit ${itemType} title`}
          onClick={() => setIsEditingHeading(!isEditingHeading)}
        >
          &#9998;
        </button>
      </h3>
      {description && (
        <p className="description">
          <EditableText
            value={descText}
            originalValue={description}
            isEditing={isEditingDesc}
            committed={descEdited}
            onCommit={handleDescCommit}
            onCancel={() => setIsEditingDesc(false)}
            trigger="external"
            className="editable-text"
            data-testid={`bn-group-${anchor}-desc`}
            data-edit-key={`${anchor}:desc`}
          />
          {" "}
          <button
            className="edit-pencil edit-pencil-inline"
            aria-label={`Edit ${itemType} description`}
            onClick={() => setIsEditingDesc(!isEditingDesc)}
          >
            &#9998;
          </button>
        </p>
      )}
      <div className="quote-group">
        <Counter
          count={hiddenQuotes.length}
          items={counterItems}
          isOpen={isCounterOpen}
          onToggle={handleCounterToggle}
          onUnhide={handleUnhide}
          onUnhideAll={handleUnhideAll}
          data-testid={`bn-counter-${anchor}`}
        />
        {quotes.map((q) => {
          const state = stateMap[q.dom_id];
          if (!state) return null;

          // Quote in hide animation — render with .bn-hiding class.
          if (hidingIds.has(q.dom_id)) {
            return (
              <blockquote
                key={q.dom_id}
                id={q.dom_id}
                className="bn-hiding"
              />
            );
          }

          return (
            <QuoteCard
              key={q.dom_id}
              quote={q}
              displayText={state.editedText || q.text}
              isStarred={state.isStarred}
              isHidden={state.isHidden}
              userTags={state.tags}
              deletedBadges={state.deletedBadges}
              isEdited={state.editedText != null && state.editedText !== q.text}
              tagVocabulary={tagVocabulary}
              sessionId={q.session_id}
              hasMedia={hasMedia}
              proposedTags={state.proposedTags}
              onToggleStar={handleToggleStar}
              onToggleHide={handleToggleHide}
              onEditCommit={handleEditCommit}
              onTagAdd={handleTagAdd}
              onTagRemove={handleTagRemove}
              onBadgeDelete={handleBadgeDelete}
              onBadgeRestore={handleBadgeRestore}
              onProposedAccept={(proposalId, tagName) =>
                handleProposedAccept(q.dom_id, proposalId, tagName)
              }
              onProposedDeny={(proposalId) =>
                handleProposedDeny(q.dom_id, proposalId)
              }
            />
          );
        })}
      </div>
    </>
  );
}
