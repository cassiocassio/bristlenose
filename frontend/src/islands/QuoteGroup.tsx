/**
 * QuoteGroup — a group of quote cards with editable heading,
 * optional description, and hidden-quotes counter.
 *
 * Owns local state for all quotes in the group (star, hidden,
 * edited text, tags, deleted badges). Mutations are optimistic:
 * React state updates immediately, then fire-and-forget PUT
 * calls sync to the server.
 */

import { useState, useCallback, useRef, useMemo, useLayoutEffect, useEffect } from "react";
import { Counter, EditableText } from "../components";
import type { CounterItem } from "../components/Counter";
import type {
  ModeratorQuestionResponse,
  ProposedTagBrief,
  QuoteResponse,
  TagResponse,
} from "../utils/types";
import {
  acceptProposal,
  denyProposal,
  getModeratorQuestion,
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

  // Ref mirrors stateMap so handlers (including setTimeout closures)
  // always see the latest state without stale-closure issues.
  const stateRef = useRef(stateMap);
  stateRef.current = stateMap;

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

  // Track recently-accepted tags for the accept flash animation.
  // Key: `${domId}:${tagName}`, auto-clears after 500ms.
  const [flashingTags, setFlashingTags] = useState<Set<string>>(new Set());

  // DOM refs for fly-up/fly-down animation.
  const headerRef = useRef<HTMLDivElement>(null);
  const groupRef = useRef<HTMLDivElement>(null);

  // Unhide fly-down animation: ref holds domIds awaiting animation,
  // version counter triggers the useLayoutEffect.
  const pendingUnhides = useRef<Set<string>>(new Set());
  const [unhideVersion, setUnhideVersion] = useState(0);

  // ── Moderator question state ───────────────────────────────────────────

  const LS_KEY = "bristlenose-mod-questions";

  // Which quotes have the moderator question pinned open.
  const [openQuestions, setOpenQuestions] = useState<Set<string>>(() => {
    try {
      const raw = localStorage.getItem(LS_KEY);
      return raw ? new Set(JSON.parse(raw) as string[]) : new Set();
    } catch {
      return new Set();
    }
  });

  // Cache of fetched moderator question data per quote dom_id.
  // undefined = not yet fetched, null = fetched but none found.
  const [modQuestionCache, setModQuestionCache] = useState<
    Record<string, ModeratorQuestionResponse | null>
  >({});

  // Which quote is currently showing the hover pill (only one at a time).
  const [pillVisibleFor, setPillVisibleFor] = useState<string | null>(null);

  // Timer for the 400ms hover delay.
  const hoverTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Ref mirrors openQuestions so hover-leave handler can read latest state.
  const openQuestionsRef = useRef(openQuestions);
  openQuestionsRef.current = openQuestions;

  // On mount, batch-fetch moderator questions for previously-open quotes.
  useEffect(() => {
    const domIds = quotes
      .filter((q) => openQuestions.has(q.dom_id) && q.segment_index > 0)
      .map((q) => q.dom_id);
    for (const domId of domIds) {
      if (modQuestionCache[domId] !== undefined) continue;
      getModeratorQuestion(domId)
        .then((data) => {
          setModQuestionCache((prev) => ({ ...prev, [domId]: data }));
        })
        .catch(() => {
          setModQuestionCache((prev) => ({ ...prev, [domId]: null }));
        });
    }
    // Only run on mount.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

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

  // ── Mutation helpers ──────────────────────────────────────────────────

  /** Update one quote's local state (no API call). */
  const updateQuote = useCallback(
    (
      domId: string,
      updater: (prev: QuoteLocalState) => QuoteLocalState,
    ) => {
      setStateMap((prev) => ({ ...prev, [domId]: updater(prev[domId]) }));
    },
    [],
  );

  const handleToggleStar = useCallback(
    (domId: string, newState: boolean) => {
      updateQuote(domId, (s) => ({ ...s, isStarred: newState }));
      const starred: Record<string, boolean> = {};
      for (const [id, s] of Object.entries(stateRef.current)) {
        const val = id === domId ? newState : s.isStarred;
        if (val) starred[id] = true;
      }
      putStarred(starred);
    },
    [updateQuote],
  );

  const handleToggleHide = useCallback(
    (domId: string, newState: boolean) => {
      if (newState) {
        // ── Hide: fly-up ghost + CSS collapse ───────────────────────────
        // Capture rects before any state changes.
        const quoteEl = groupRef.current?.querySelector(`#${CSS.escape(domId)}`);
        const quoteRect = quoteEl?.getBoundingClientRect() ?? null;
        const badgeEl = headerRef.current?.querySelector(".bn-hidden-badge");
        let badgeRect = badgeEl?.getBoundingClientRect() ?? null;
        // First hide in group: badge doesn't exist yet (Counter returns null).
        // Use the header's top-right corner as the fly target — that's where
        // the badge will materialise once the hide completes.
        if (!badgeRect && headerRef.current) {
          const hr = headerRef.current.getBoundingClientRect();
          badgeRect = { left: hr.right - 60, top: hr.top, width: 60, height: hr.height } as DOMRect;
        }

        // Start CSS collapse (existing .bn-hiding for sibling slide-up).
        setHidingIds((prev) => new Set(prev).add(domId));

        // Clone the quote card as a ghost overlay (before React re-renders).
        if (quoteRect && quoteEl) {
          const ghost = quoteEl.cloneNode(true) as HTMLElement;
          ghost.className = "bn-hide-ghost";
          ghost.removeAttribute("id");
          ghost.style.cssText = [
            "position: fixed",
            `left: ${quoteRect.left}px`,
            `top: ${quoteRect.top}px`,
            `width: ${quoteRect.width}px`,
            `height: ${quoteRect.height}px`,
            "margin: 0",
            "z-index: 500",
            "pointer-events: none",
            "opacity: 1",
            "overflow: hidden",
          ].join("; ");
          document.body.appendChild(ghost);

          requestAnimationFrame(() => {
            if (badgeRect) {
              ghost.style.transition = `all ${HIDE_DURATION}ms ease`;
              ghost.style.left = `${badgeRect.left}px`;
              ghost.style.top = `${badgeRect.top}px`;
              ghost.style.width = `${badgeRect.width}px`;
              ghost.style.height = "0px";
              ghost.style.opacity = "0";
            } else {
              // No badge yet (first hide) — simple fade.
              ghost.style.transition = `opacity ${HIDE_DURATION}ms ease`;
              ghost.style.opacity = "0";
            }
          });

          setTimeout(() => ghost.remove(), HIDE_DURATION + 50);
        }

        // After animation, finalise hidden state.
        const timer = setTimeout(() => {
          setHidingIds((prev) => {
            const next = new Set(prev);
            next.delete(domId);
            return next;
          });
          updateQuote(domId, (s) => ({ ...s, isHidden: true }));
          const hidden: Record<string, boolean> = {};
          for (const [id, s] of Object.entries(stateRef.current)) {
            const val = id === domId ? true : s.isHidden;
            if (val) hidden[id] = true;
          }
          putHidden(hidden);
          hideTimers.current.delete(domId);
        }, HIDE_DURATION);
        hideTimers.current.set(domId, timer);
      } else {
        // ── Unhide: fly-down from badge ─────────────────────────────────
        pendingUnhides.current.add(domId);
        updateQuote(domId, (s) => ({ ...s, isHidden: false }));
        setUnhideVersion((v) => v + 1);
        const hidden: Record<string, boolean> = {};
        for (const [id, s] of Object.entries(stateRef.current)) {
          const val = id === domId ? false : s.isHidden;
          if (val) hidden[id] = true;
        }
        putHidden(hidden);
      }
    },
    [updateQuote],
  );

  // Fly-down animation: runs after unhidden quotes enter the DOM.
  // useLayoutEffect fires before paint, so the user never sees a flash.
  useLayoutEffect(() => {
    if (pendingUnhides.current.size === 0) return;
    const ids = new Set(pendingUnhides.current);
    pendingUnhides.current.clear();

    const badgeEl = headerRef.current?.querySelector(".bn-hidden-badge");
    let badgeRect = badgeEl?.getBoundingClientRect() ?? null;
    // Unhide-all: badge vanishes (count → 0) before this effect runs.
    // Fall back to the header's right edge — same pattern as hide path.
    if (!badgeRect && headerRef.current) {
      const hr = headerRef.current.getBoundingClientRect();
      badgeRect = { left: hr.right - 60, top: hr.top, width: 60, height: hr.height } as DOMRect;
    }

    // Stagger: 150ms between each quote for unhide-all cascade.
    // Single unhide: stagger = 0, no delay.
    let index = 0;
    ids.forEach((domId) => {
      const quoteEl = groupRef.current?.querySelector(
        `#${CSS.escape(domId)}`,
      ) as HTMLElement | null;
      if (!quoteEl) return;

      const quoteRect = quoteEl.getBoundingClientRect();

      if (badgeRect) {
        const dy = badgeRect.top - quoteRect.top;
        const stagger = index * 150;

        quoteEl.style.transform = `translateY(${dy}px) scaleY(0.01)`;
        quoteEl.style.transformOrigin = "top right";
        quoteEl.style.opacity = "0";
        quoteEl.style.transition = "none";

        setTimeout(() => {
          requestAnimationFrame(() => {
            quoteEl.style.transition = `all ${HIDE_DURATION}ms ease`;
            quoteEl.style.transform = "";
            quoteEl.style.opacity = "1";
          });
        }, stagger);

        setTimeout(() => {
          quoteEl.style.transition = "";
          quoteEl.style.transform = "";
          quoteEl.style.transformOrigin = "";
          quoteEl.style.opacity = "";
        }, stagger + HIDE_DURATION + 50);
      }
      index++;
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [unhideVersion]);

  // Cleanup: remove orphaned ghost divs on unmount.
  useEffect(() => {
    return () => {
      document.querySelectorAll(".bn-hide-ghost").forEach((el) => el.remove());
    };
  }, []);

  const handleEditCommit = useCallback(
    (domId: string, newText: string) => {
      updateQuote(domId, (s) => ({ ...s, editedText: newText }));
      const edits: Record<string, string> = {};
      for (const [id, s] of Object.entries(stateRef.current)) {
        const text = id === domId ? newText : s.editedText;
        if (text) edits[id] = text;
      }
      putEdits(edits);
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
      const tags: Record<string, string[]> = {};
      for (const [id, s] of Object.entries(stateRef.current)) {
        const names =
          id === domId
            ? [...s.tags.map((t) => t.name), tagName]
            : s.tags.map((t) => t.name);
        if (names.length > 0) tags[id] = names;
      }
      putTags(tags);
    },
    [updateQuote, tagColourMap],
  );

  const handleTagRemove = useCallback(
    (domId: string, tagName: string) => {
      updateQuote(domId, (s) => ({
        ...s,
        tags: s.tags.filter((t) => t.name !== tagName),
      }));
      const tags: Record<string, string[]> = {};
      for (const [id, s] of Object.entries(stateRef.current)) {
        const names =
          id === domId
            ? s.tags.filter((t) => t.name !== tagName).map((t) => t.name)
            : s.tags.map((t) => t.name);
        if (names.length > 0) tags[id] = names;
      }
      putTags(tags);
    },
    [updateQuote],
  );

  const handleBadgeDelete = useCallback(
    (domId: string, sentiment: string) => {
      updateQuote(domId, (s) => ({
        ...s,
        deletedBadges: [...s.deletedBadges, sentiment],
      }));
      const badges: Record<string, string[]> = {};
      for (const [id, s] of Object.entries(stateRef.current)) {
        const db =
          id === domId ? [...s.deletedBadges, sentiment] : s.deletedBadges;
        if (db.length > 0) badges[id] = db;
      }
      putDeletedBadges(badges);
    },
    [updateQuote],
  );

  const handleBadgeRestore = useCallback(
    (domId: string) => {
      updateQuote(domId, (s) => ({ ...s, deletedBadges: [] }));
      const badges: Record<string, string[]> = {};
      for (const [id, s] of Object.entries(stateRef.current)) {
        const db = id === domId ? [] : s.deletedBadges;
        if (db.length > 0) badges[id] = db;
      }
      putDeletedBadges(badges);
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
      // Trigger accept flash animation on the new badge.
      const flashKey = `${domId}:${tagName}`;
      setFlashingTags((prev) => new Set(prev).add(flashKey));
      setTimeout(() => {
        setFlashingTags((prev) => {
          const next = new Set(prev);
          next.delete(flashKey);
          return next;
        });
      }, 500);
      // acceptProposal handles server-side tag creation — no putTags needed.
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

  // ── Moderator question handlers ──────────────────────────────────────

  const handleQuoteHoverEnter = useCallback((domId: string) => {
    if (hoverTimerRef.current) clearTimeout(hoverTimerRef.current);
    hoverTimerRef.current = setTimeout(() => {
      setPillVisibleFor(domId);
      hoverTimerRef.current = null;
    }, 400);
  }, []);

  const handleQuoteHoverLeave = useCallback((domId: string) => {
    if (hoverTimerRef.current) {
      clearTimeout(hoverTimerRef.current);
      hoverTimerRef.current = null;
    }
    // Don't hide pill if the question is pinned open.
    if (!openQuestionsRef.current.has(domId)) {
      setPillVisibleFor((prev) => (prev === domId ? null : prev));
    }
  }, []);

  const handleToggleQuestion = useCallback((domId: string) => {
    setOpenQuestions((prev) => {
      const next = new Set(prev);
      if (next.has(domId)) {
        next.delete(domId);
      } else {
        next.add(domId);
        // Fetch if not cached.
        if (modQuestionCache[domId] === undefined) {
          getModeratorQuestion(domId)
            .then((data) => {
              setModQuestionCache((c) => ({ ...c, [domId]: data }));
            })
            .catch(() => {
              setModQuestionCache((c) => ({ ...c, [domId]: null }));
            });
        }
      }
      // Persist to localStorage.
      try {
        localStorage.setItem(LS_KEY, JSON.stringify([...next]));
      } catch { /* quota exceeded — ignore */ }
      return next;
    });
  }, [modQuestionCache]);

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
      <div className="bn-group-header" ref={headerRef}>
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
        <Counter
          count={hiddenQuotes.length}
          items={counterItems}
          isOpen={isCounterOpen}
          onToggle={handleCounterToggle}
          onUnhide={handleUnhide}
          onUnhideAll={handleUnhideAll}
          data-testid={`bn-counter-${anchor}`}
        />
      </div>
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
      <div className="quote-group" ref={groupRef}>
        {quotes.map((q) => {
          const state = stateMap[q.dom_id];
          if (!state) return null;

          // Quote in hide animation — render with .bn-hiding class.
          if (hidingIds.has(q.dom_id)) {
            return (
              <blockquote
                key={q.dom_id}
                id={q.dom_id}
                className="quote-card bn-hiding"
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
              flashingTags={flashingTags}
              moderatorQuestion={modQuestionCache[q.dom_id] ?? null}
              isQuestionOpen={openQuestions.has(q.dom_id)}
              isPillVisible={pillVisibleFor === q.dom_id}
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
              onToggleQuestion={handleToggleQuestion}
              onQuoteHoverEnter={handleQuoteHoverEnter}
              onQuoteHoverLeave={handleQuoteHoverLeave}
            />
          );
        })}
      </div>
    </>
  );
}
