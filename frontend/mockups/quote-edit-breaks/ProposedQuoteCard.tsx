/**
 * ProposedQuoteCard — a copy of islands/QuoteCard.tsx with the proposal for
 * editing a quote that is drawn as paragraphs (docs/mockups/quote-edit-breaks.html).
 * Diff it against QuoteCard.tsx to read the proposal as code. Everything outside
 * the edit handlers and renderQuoteText is the shipped card, unchanged.
 *
 * (Shipped header follows.)
 * QuoteCard — single quote card composition.
 *
 * Renders one blockquote with the same DOM structure as
 * `quote_card.html`, using the existing React primitives (Badge,
 * PersonBadge, TimecodeLink, EditableText, Toggle, TagInput).
 *
 * Quote text editing uses a unified click-to-edit interaction:
 * click → yellow bg + gold bracket handles → type to edit AND/OR
 * drag brackets to crop → Enter to commit. See useCropEdit hook
 * and docs/design-quote-editing.md for full behaviour spec.
 *
 * All state mutations are delegated to the parent (QuoteGroup)
 * via callbacks.
 */

import { useState, useCallback, useRef, useEffect, useLayoutEffect, useMemo } from "react";
import { useTranslation } from "react-i18next";
import {
  Badge,
  ContextSegment,
  ExpandableTimecode,
  PersonBadge,
  TagInput,
  TimecodeLink,
  Toggle,
} from "../../src/components";
import type { TagVocabularyGroup, TagPick } from "../../src/components";
import type { ModeratorQuestionResponse, ProposedTagBrief, QuoteResponse, TranscriptSegmentResponse } from "../../src/utils/types";
import { formatTimecode } from "../../src/utils/format";
import { getTagBg } from "../../src/utils/colours";
import { isExportMode } from "../../src/utils/exportData";
import { reportHref } from "../../src/utils/reportHref";
import { featureFlags } from "../../src/utils/featureFlags";
import { highlightTerms } from "../../src/utils/highlight";
import { useDisplayBreaks } from "../../src/contexts/DisplayPrefsStore";
import type { SearchTerm } from "../../src/utils/searchMatch";
import { useCropEditProposed, type CommitResult } from "./useCropEditProposed";
import { autoBreaks, blockRanges, caretAtPoint, draw, setBracketsVisible as showBrackets } from "./proposedDom";
import { useFocus, useQuoteFocusState } from "../../src/contexts/FocusContext";
import { Icon } from "../../src/components/Icon";
import { momentPlace } from "../../src/utils/contextPlace";

// ── SVG icon for the hide button (eye-slash) ────────────────────────────

const HideIcon = (
  <Icon name="hide" px={14} decorative />
);

/** Split text into first sentence + remainder (if any). */
function splitFirstSentence(text: string): { first: string; rest: string } {
  const match = text.match(/^(.*?[.?!])\s+(.+)$/s);
  if (!match) return { first: text, rest: "" };
  return { first: match[1], rest: match[2] };
}

function escapeHtml(s: string): string {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

// ── Props ───────────────────────────────────────────────────────────────

interface QuoteCardProps {
  quote: QuoteResponse;
  /** Current display text (may be edited). */
  displayText: string;
  isStarred: boolean;
  isHidden: boolean;
  /** Tags currently on this quote (user-added, visible after hidden-group filter). */
  userTags: { id?: number; name: string; codebook_group: string; colour_set: string; colour_index: number }[];
  /** All tag names on this quote (including hidden groups) — used for TagInput exclude filter. */
  allTagNames: string[];
  /** Lowercased tag names whose codebook groups are currently hidden (eye-toggled off). */
  hiddenTagNames?: Set<string>;
  /** Lowercased tag names from DISABLED codebooks — suppressed from autocomplete
   *  entirely (merged into the exclude set), never merely decorated. §5. */
  disabledTagNames?: Set<string>;
  /** AI sentiment badges that have been deleted. */
  deletedBadges: string[];
  /** Whether the quote text has been edited. */
  isEdited: boolean;
  /** Full tag vocabulary for auto-suggest. */
  tagVocabulary: string[];
  /** Grouped vocabulary with codebook metadata (for structured autocomplete). */
  groupedVocabulary?: TagVocabularyGroup[];
  /** Session ID for transcript link. */
  sessionId: string;
  /** Whether video is available for this quote. */
  hasMedia: boolean;
  /** Whether any session in this project has a moderator speaker. */
  hasModerator: boolean;
  /** Pending AutoCode proposals for this quote. */
  proposedTags: ProposedTagBrief[];
  /** Tags currently playing the accept flash animation. Keys: `${domId}:${tagName}`. */
  flashingTags: Set<string>;
  /** Cached moderator question data (null = not yet fetched or none found). */
  moderatorQuestion: ModeratorQuestionResponse | null;
  /** Whether the moderator question is expanded (pinned open). */
  isQuestionOpen: boolean;
  /** Whether the "Question?" pill is visible (from hover timer). */
  isPillVisible: boolean;

  /** Context expansion — optional, only passed when transcript cache available. */
  canExpandAbove?: boolean;
  canExpandBelow?: boolean;
  onExpandAbove?: () => void;
  onExpandBelow?: () => void;
  exhaustedAbove?: boolean;
  exhaustedBelow?: boolean;
  /** Resolved context segments to render inside the blockquote. */
  contextAbove?: TranscriptSegmentResponse[];
  contextBelow?: TranscriptSegmentResponse[];

  onToggleStar: (domId: string, newState: boolean) => void;
  onToggleHide: (domId: string, newState: boolean) => void;
  onEditCommit: (domId: string, newText: string) => void;
  /** PROPOSED: the researcher's own breaks for this quote (null = automatic). */
  researcherBreaks: number[] | null;
  /** PROPOSED: a change to the researcher's breaks (the quote_breaks overlay). */
  onBreaksCommit: (domId: string, breaks: number[] | null) => void;
  /** PROPOSED (open decision): show the researcher's breaks with Break long paragraphs off. */
  researcherBreaksWhenOff: boolean;
  /** PROPOSED (open decision): Tab leaves focus on the card instead of moving on. */
  tabStaysOnCard: boolean;
  /** Mockup only: say what a key did. */
  onKeyEcho: (what: string) => void;
  /** `pick` is the tag chosen from the list, as the row it is (two tags can share a name). */
  onTagAdd: (domId: string, tagName: string, pick?: TagPick) => void;
  /** `tagId` is the tag the × points at; a removal that carries it takes only that tag. */
  onTagRemove: (domId: string, tagName: string, tagId?: number) => void;
  onBadgeDelete: (domId: string, sentiment: string) => void;
  onBadgeRestore: (domId: string) => void;
  onProposedAccept: (proposalId: number, tagName: string) => void;
  onProposedDeny: (proposalId: number) => void;
  onToggleQuestion: (domId: string) => void;
  onQuoteHoverEnter: (domId: string) => void;
  onQuoteHoverLeave: (domId: string) => void;
  onPillHoverEnter: (domId: string) => void;
  onPillHoverLeave: (domId: string) => void;
  /** What to mark in the quote text: the typed words plus what a "mentions" or
   *  "text contains" token found (`highlightTermsOf`, utils/filter.ts). */
  highlight?: SearchTerm[];
  /** Whether to show the "[When asked…]" researcher-context line. Default true. The Screens lens
   *  passes false: the owner, 15 Oct 2026, "interesting but new… hide here for the moment". */
  showResearcherContext?: boolean;
}

export function ProposedQuoteCard({
  quote,
  displayText,
  isStarred,
  isHidden,
  userTags,
  allTagNames,
  hiddenTagNames,
  disabledTagNames,
  deletedBadges,
  isEdited,
  tagVocabulary,
  groupedVocabulary,
  sessionId,
  hasMedia,
  hasModerator,
  proposedTags,
  flashingTags,
  onToggleStar,
  onToggleHide,
  onEditCommit,
  researcherBreaks,
  onBreaksCommit,
  researcherBreaksWhenOff,
  tabStaysOnCard,
  onKeyEcho,
  onTagAdd,
  onTagRemove,
  onBadgeDelete,
  onBadgeRestore,
  onProposedAccept,
  onProposedDeny,
  moderatorQuestion,
  isQuestionOpen,
  isPillVisible,
  onToggleQuestion,
  onQuoteHoverEnter,
  onQuoteHoverLeave,
  onPillHoverEnter,
  onPillHoverLeave,
  canExpandAbove,
  canExpandBelow,
  onExpandAbove,
  onExpandBelow,
  exhaustedAbove,
  exhaustedBelow,
  contextAbove,
  contextBelow,
  highlight,
  showResearcherContext = true,
}: QuoteCardProps) {
  const { t } = useTranslation();
  const [isTagInputOpen, setIsTagInputOpen] = useState(false);
  const [showFullModQ, setShowFullModQ] = useState(false);
  const [bracketsVisible, setBracketsVisible] = useState(false);

  const domId = quote.dom_id;

  // ── Focus/selection state ──────────────────────────────────────────
  const { isFocused, isSelected } = useQuoteFocusState(domId);
  const {
    setFocus,
    toggleSelection,
    selectRange,
    clearSelection,
    setAnchor,
    anchorId,
    registerTagOpener,
    unregisterTagOpener,
  } = useFocus();

  // Register tag opener so keyboard shortcut (t) can open tag input.
  useEffect(() => {
    registerTagOpener(domId, () => setIsTagInputOpen(true));
    return () => unregisterTagOpener(domId);
  }, [domId, registerTagOpener, unregisterTagOpener]);
  // Gated on `moderatorQuestionPill` (parked — see utils/featureFlags.ts).
  // Falsing this also restores `quote.researcher_context` on quotes that have
  // a verbatim moderator question: the paraphrased context was suppressed
  // *because* the pill offered the verbatim one, so with the pill withheld the
  // researcher context is the affordance again.
  const hasModeratorContext =
    featureFlags.moderatorQuestionPill && hasModerator && quote.segment_index > 0;
  const textSpanRef = useRef<HTMLSpanElement>(null);

  // Focus the editable span when it mounts. Stable, so React calls it only on
  // mount and unmount: an inline arrow is a new ref every render, re-run each
  // time, and the bracket-reveal re-render 250 ms into an edit pulled focus
  // back from anything the researcher had moved to — the tag input included.
  const focusEditableOnMount = useCallback((el: HTMLSpanElement | null) => {
    if (el && document.activeElement !== el) {
      el.focus();
    }
  }, []);

  // ── Crop edit hook ──────────────────────────────────────────────────

  // ── PROPOSED: the paragraphs at rest are the paragraphs while editing ──
  // Rest shows the researcher's own breaks if they have any, else the
  // automatic ones (when Break long paragraphs is on). Entering edit freezes
  // exactly what is shown; nothing is re-placed until commit.
  const breaksOn = useDisplayBreaks() === "on";
  const shownBreaks = useMemo(() => {
    if (researcherBreaks !== null && (breaksOn || researcherBreaksWhenOff)) return researcherBreaks;
    return breaksOn ? autoBreaks(displayText) : [];
  }, [researcherBreaks, breaksOn, researcherBreaksWhenOff, displayText]);
  const blocks = useMemo(() => {
    const words = displayText.split(/\s+/).filter(Boolean);
    return blockRanges(words.length, shownBreaks).map(([s, e]) => words.slice(s, e).join(" "));
  }, [displayText, shownBreaks]);

  const handleCropCommit = useCallback(
    (r: CommitResult) => {
      if (r.text !== null) onEditCommit(domId, r.text);
      if (r.breaks !== null) onBreaksCommit(domId, r.breaks.value);
      if (r.text === null && r.breaks === null) onKeyEcho("\u2192 nothing written (unchanged)");
    },
    [domId, onEditCommit, onBreaksCommit, onKeyEcho],
  );

  const crop = useCropEditProposed({
    currentText: displayText,
    researcherBreaks,
    shownBreaks,
    onCommit: handleCropCommit,
    onKey: onKeyEcho,
  });

  // Where the click landed, so the caret goes there (the layout does not move,
  // so the same point is the same word after the edit surface is drawn).
  const clickPoint = useRef<{ x: number; y: number } | null>(null);
  const editHostRef = useRef<HTMLSpanElement>(null);

  // ── Bracket delayed entrance ────────────────────────────────────────

  useEffect(() => {
    if (crop.mode === "hybrid") {
      setBracketsVisible(false);
      const timer = setTimeout(() => setBracketsVisible(true), 250);
      return () => clearTimeout(timer);
    }
    if (crop.mode === "crop") {
      setBracketsVisible(true);
    } else {
      setBracketsVisible(false);
    }
  }, [crop.mode]);

  // ── Draw the edit surface (text mode once on entry; trim on each move) ──

  useLayoutEffect(() => {
    const host = editHostRef.current;
    if (!host || crop.mode === "idle") return;
    const m = crop.model.current;
    draw(host, { ...m, cropStart: crop.mode === "crop" ? crop.cropStart : m.cropStart, cropEnd: crop.mode === "crop" ? crop.cropEnd : m.cropEnd }, {
      mode: crop.mode,
      leftEllipsis: crop.hasLeftCrop,
      rightEllipsis: crop.hasRightCrop,
      bracketsVisible: crop.mode === "crop",
    });
    if (crop.mode === "hybrid") {
      host.focus();
      const pt = clickPoint.current;
      clickPoint.current = null;
      if (!pt || !caretAtPoint(host, pt.x, pt.y)) {
        const sel = window.getSelection();
        const r = document.createRange();
        r.selectNodeContents(host.querySelector(".crop-editable") ?? host);
        r.collapse(false);
        sel?.removeAllRanges();
        sel?.addRange(r);
      }
    }
    }, [crop.mode, crop.cropStart, crop.cropEnd]);

  // The bracket fade-in touches only the brackets, never the typed text.
  useEffect(() => {
    const host = editHostRef.current;
    if (host && crop.mode !== "idle") showBrackets(host, bracketsVisible || crop.mode === "crop");
  }, [bracketsVisible, crop.mode]);

  // ── Bracket drag: the brackets are drawn by hand, so are their listeners ──

  useEffect(() => {
    const host = editHostRef.current;
    if (crop.mode === "idle" || !host) return;
    const listener = (e: Event) => {
      const t = (e.target as HTMLElement).closest<HTMLElement>(".crop-handle");
      if (!t || !host.contains(t)) return;
      crop.handleBracketPointerDown(t.dataset.handle as "start" | "end", e as PointerEvent, host);
    };
    host.addEventListener("pointerdown", listener);
    return () => host.removeEventListener("pointerdown", listener);
  }, [crop.mode, crop.handleBracketPointerDown]);

  // ── Click-outside → commit ──────────────────────────────────────────

  useEffect(() => {
    if (crop.mode === "idle") return;
    const onPointerDown = (e: PointerEvent) => {
      const card = editHostRef.current?.closest("blockquote");
      if (card && !card.contains(e.target as Node)) {
        onKeyEcho("click outside \u2192 commit");
        crop.commitEdit(editHostRef.current);
      }
    };
    document.addEventListener("pointerdown", onPointerDown);
    return () => document.removeEventListener("pointerdown", onPointerDown);
  }, [crop, onKeyEcho]);

  // ── Leaving mid-edit → commit (as shipped, R88) ─────────────────────

  const commitOnLeave = useRef<(() => void) | null>(null);
  useLayoutEffect(() => {
    commitOnLeave.current =
      crop.mode === "idle"
        ? null
        : () => {
            if (crop.blurTimeoutRef.current) {
              clearTimeout(crop.blurTimeoutRef.current);
              crop.blurTimeoutRef.current = null;
            }
            crop.commitEdit(editHostRef.current);
          };
  });
  useLayoutEffect(() => () => commitOnLeave.current?.(), []);

  // ── Tab: commits in BOTH modes (shipped: text mode only, by blur) ───

  const tabOut = useCallback(
    (e: React.KeyboardEvent) => {
      e.preventDefault();
      e.stopPropagation();
      const card = editHostRef.current?.closest("blockquote") as HTMLElement | null;
      if (crop.blurTimeoutRef.current) {
        clearTimeout(crop.blurTimeoutRef.current);
        crop.blurTimeoutRef.current = null;
      }
      crop.suppressBlurRef.current = true;
      // Where native Tab would have gone from the quote text: the next (or
      // previous) focusable control in document order.
      let target: HTMLElement | null = null;
      if (!tabStaysOnCard && editHostRef.current) {
        const all = Array.from(
          document.querySelectorAll<HTMLElement>('a[href], button:not([disabled]), input, select, textarea, [tabindex]:not([tabindex="-1"])'),
        ).filter((n) => !editHostRef.current!.contains(n) && n.offsetParent !== null);
        const pos = (n: HTMLElement) => editHostRef.current!.compareDocumentPosition(n);
        target = e.shiftKey
          ? all.filter((n) => pos(n) & Node.DOCUMENT_POSITION_PRECEDING).pop() ?? null
          : all.find((n) => pos(n) & Node.DOCUMENT_POSITION_FOLLOWING) ?? null;
      }
      onKeyEcho(`${e.shiftKey ? "Shift-Tab" : "Tab"} \u2192 commit, focus ${tabStaysOnCard ? "stays on the card" : target ? `to ${target.getAttribute("aria-label") ?? target.textContent?.trim() ?? target.tagName}` : "leaves the card"}`);
      crop.commitEdit(editHostRef.current);
      requestAnimationFrame(() => {
        if (tabStaysOnCard && card) {
          card.setAttribute("tabindex", "-1");
          card.focus();
        } else target?.focus();
      });
    },
    [crop, tabStaysOnCard, onKeyEcho],
  );

  // ── Card-level keydown for crop mode ────────────────────────────────

  const handleCardKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (crop.mode !== "crop") return;
      if (e.key === "Enter") {
        e.preventDefault();
        e.stopPropagation();
        onKeyEcho("Return \u2192 commit the trim");
        crop.commitEdit();
      } else if (e.key === "Escape") {
        e.preventDefault();
        e.stopPropagation();
        onKeyEcho("Escape \u2192 cancel");
        crop.cancelEdit();
      } else if (e.key === "Tab") {
        tabOut(e);
      }
    },
    [crop, onKeyEcho, tabOut],
  );

  // ── Edit mode entry (click on quote text in idle) ───────────────────

  const handleQuoteTextClick = useCallback(
    (e: React.MouseEvent) => {
      if (isExportMode()) return;
      if (e.metaKey || e.ctrlKey || e.shiftKey) return;
      if (crop.mode === "idle") {
        clickPoint.current = { x: e.clientX, y: e.clientY };
        onKeyEcho("click \u2192 edit");
        crop.enterEditMode();
      } else if (crop.mode === "crop") {
        const target = e.target as HTMLElement;
        const isIncluded =
          (target.classList.contains("crop-word") && target.classList.contains("included")) ||
          target.classList.contains("crop-included-region");
        if (isIncluded) {
          clickPoint.current = { x: e.clientX, y: e.clientY };
          onKeyEcho("click a kept word \u2192 back to text");
          crop.reenterTextEdit();
        }
      }
    },
    [crop, onKeyEcho],
  );

  // ── Text mode: keyboard + blur on the contenteditable ───────────────

  const handleEditKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      const host = editHostRef.current;
      if (!host || e.nativeEvent.isComposing) return;
      const vis = bracketsVisible;
      if (e.key === "Enter" && (e.shiftKey || e.altKey)) {
        e.preventDefault();
        e.stopPropagation();
        onKeyEcho(`${e.shiftKey ? "Shift" : "Option"}-Return \u2192 ${crop.splitAtCaret(host, vis)}`);
      } else if (e.key === "Enter") {
        e.preventDefault();
        e.stopPropagation();
        onKeyEcho("Return \u2192 commit");
        crop.commitEdit(host);
      } else if (e.key === "Escape") {
        e.preventDefault();
        e.stopPropagation();
        onKeyEcho("Escape \u2192 cancel");
        crop.cancelEdit();
      } else if (e.key === "Tab") {
        tabOut(e);
      } else if ((e.key === "Backspace" || e.key === "Delete") && !e.metaKey && !e.altKey) {
        const did = crop.joinAtCaret(host, e.key === "Backspace" ? -1 : 1, vis);
        if (did !== null) {
          e.preventDefault();
          e.stopPropagation();
          onKeyEcho(`${e.key === "Backspace" ? "Backspace" : "Delete"} at a paragraph ${e.key === "Backspace" ? "start" : "end"} \u2192 ${did}`);
        }
      }
    },
    [crop, bracketsVisible, onKeyEcho, tabOut],
  );

  // A paste is plain text: a pasted paragraph would otherwise bring the other
  // page's elements into the quote.
  const handlePaste = useCallback(
    (e: React.ClipboardEvent) => {
      e.preventDefault();
      const text = e.clipboardData.getData("text/plain").replace(/\s+/g, " ");
      document.execCommand("insertText", false, text);
      onKeyEcho("paste \u2192 as plain text");
    },
    [onKeyEcho],
  );

  const handleEditBlur = useCallback(() => {
    crop.blurTimeoutRef.current = setTimeout(() => {
      if (crop.suppressBlurRef.current) {
        crop.suppressBlurRef.current = false;
        return;
      }
      if (crop.mode === "hybrid") {
        onKeyEcho("blur \u2192 commit");
        crop.commitEdit(editHostRef.current);
      }
    }, 150);
  }, [crop, onKeyEcho]);

  // ── Undo handler ────────────────────────────────────────────────────

  const handleUndo = useCallback(
    (e: React.MouseEvent) => {
      e.stopPropagation();
      onEditCommit(domId, quote.text);
    },
    [domId, quote.text, onEditCommit],
  );

  // ── Click-to-focus handler ──────────────────────────────────────────

  const handleCardClick = useCallback(
    (e: React.MouseEvent) => {
      // Don't interfere with clicks on interactive elements
      const target = e.target as HTMLElement;
      if (target.closest("button, a, input, [contenteditable=\"true\"]")) {
        return;
      }
      // Don't interfere with tag input
      if (target.closest(".badge-add, .tag-input-wrap")) {
        return;
      }
      if (e.metaKey || e.ctrlKey) {
        // Cmd/Ctrl+Click: toggle selection
        e.preventDefault();
        e.stopPropagation();
        window.getSelection()?.removeAllRanges();
        toggleSelection(domId);
        setAnchor(domId);
        setFocus(domId, { scroll: false });
      } else if (e.shiftKey && anchorId) {
        // Shift+Click: range selection
        // Must clear browser's native text selection (Shift+click creates one).
        e.preventDefault();
        e.stopPropagation();
        window.getSelection()?.removeAllRanges();
        selectRange(anchorId, domId);
        setFocus(domId, { scroll: false });
      } else {
        // Don't interfere with text selection on plain clicks
        const sel = window.getSelection();
        if (sel && sel.toString().length > 0) {
          return;
        }
        // Plain click: focus + single-select (Finder-like)
        clearSelection();
        toggleSelection(domId);
        setFocus(domId, { scroll: false });
        setAnchor(domId);
      }
    },
    [domId, anchorId, toggleSelection, selectRange, clearSelection, setFocus, setAnchor],
  );

  // ── Tag handlers ────────────────────────────────────────────────────

  const handleTagCommit = useCallback(
    (tagName: string, pick?: TagPick) => {
      if (disabledTagNames?.has(tagName.toLowerCase())) return;
      setIsTagInputOpen(false);
      if (pick) onTagAdd(domId, tagName, pick);
      else onTagAdd(domId, tagName);
    },
    [domId, onTagAdd, disabledTagNames],
  );

  const handleTagCommitAndReopen = useCallback(
    (tagName: string, pick?: TagPick) => {
      if (disabledTagNames?.has(tagName.toLowerCase())) return;
      if (pick) onTagAdd(domId, tagName, pick);
      else onTagAdd(domId, tagName);
      setIsTagInputOpen(false);
      requestAnimationFrame(() => setIsTagInputOpen(true));
    },
    [domId, onTagAdd, disabledTagNames],
  );

  const handleTagCancel = useCallback(() => {
    setIsTagInputOpen(false);
  }, []);

  // ── Visibility ──────────────────────────────────────────────────────

  if (isHidden) return null;

  // ── Derived state ───────────────────────────────────────────────────

  // Must go through reportHref: under hash routing (export mode, file://) a
  // plain "/report/..." href navigates the browser off the file:// document to
  // a non-existent path, silently — no console error. The timecode rides as a
  // nested #t-<seconds> that TranscriptPage's tail-parse resolves.
  const transcriptHref = reportHref(
    `/report/sessions/${sessionId}#t-${Math.floor(quote.start_timecode)}`,
  );
  // Suppress the AI sentiment badge when the same sentiment exists as a
  // codebook tag (from the Sentiment framework auto-import).  This prevents
  // showing the same sentiment twice — once as AI badge, once as user tag.
  const hasSentimentTag = userTags.some(
    (t) => t.codebook_group === "Sentiment" && t.name === quote.sentiment,
  );
  const visibleSentiment =
    quote.sentiment && !hasSentimentTag && !deletedBadges.includes(quote.sentiment)
      ? quote.sentiment
      : null;
  const hasDeletedBadges = deletedBadges.length > 0;
  // TagInput exclude = tags already on this quote ∪ tags from DISABLED codebooks
  // ("off means off" — you can't add what's switched off; §5). Eye-hidden tags are
  // NOT excluded — hide keeps them suggestable (they flow via hiddenTagNames).
  const existingTagNames =
    disabledTagNames && disabledTagNames.size > 0
      ? [...allTagNames, ...disabledTagNames]
      : allTagNames;
  const timecodeStr = formatTimecode(quote.start_timecode);
  const isActive = crop.mode !== "idle";

  // ── Render quote text area ──────────────────────────────────────────

  function renderQuoteText() {
    if (crop.mode !== "idle") {
      // PROPOSED: one host for both edit modes, drawn by proposedDom.ts as the
      // same blocks as at rest. React gives it no children, and a new key, so
      // it never reconciles over what the browser typed.
      return (
        // eslint-disable-next-line jsx-a11y/click-events-have-key-events, jsx-a11y/no-static-element-interactions
        <span
          key="edit-host"
          className="quote-text"
          ref={editHostRef}
          data-testid={`bn-quote-${domId}-text`}
          data-edit-key={`${domId}:text`}
          role={crop.mode === "hybrid" ? "textbox" : undefined}
          aria-multiline={crop.mode === "hybrid" ? "true" : undefined}
          contentEditable={crop.mode === "hybrid"}
          suppressContentEditableWarning
          onKeyDown={crop.mode === "hybrid" ? handleEditKeyDown : undefined}
          onBlur={crop.mode === "hybrid" ? handleEditBlur : undefined}
          onPaste={crop.mode === "hybrid" ? handlePaste : undefined}
          onClick={handleQuoteTextClick}
        />
      );
    }

    // Idle — always drawn as blocks (one block when unbroken), so the quote
    // marks sit in the same place in every state.
    const last = blocks.length - 1;
    return (
      // eslint-disable-next-line jsx-a11y/click-events-have-key-events, jsx-a11y/no-static-element-interactions
      <span
        key="rest"
        className="quote-text"
        ref={textSpanRef}
        style={{ cursor: "text" }}
        onClick={handleQuoteTextClick}
        data-testid={`bn-quote-${domId}-text`}
        data-edit-key={`${domId}:text`}
      >
        {blocks.map((block, i) => (
          <span key={i} className="bn-block">
            {i === 0 && <span className="bn-mark"><span className="smart-quote">{"\u201c"}</span></span>}
            {i === 0 && crop.hasLeftCrop && <span className="crop-ellipsis">{"\u2026"}</span>}
            {highlight ? highlightTerms(block, highlight) : block}
            {i === last && crop.hasRightCrop && <span className="crop-ellipsis">{"\u2026"}</span>}
            {i === last && <span className="bn-mark"><span className="smart-quote">{"\u201d"}</span></span>}
          </span>
        ))}
      </span>
    );
  }

  return (
    // Quote card; <blockquote> semantics preserved. Card-level click +
    // keyboard handlers wire selection, star, hide, tag-add shortcuts.
    // eslint-disable-next-line jsx-a11y/no-noninteractive-element-interactions
    <blockquote
      id={domId}
      data-timecode={timecodeStr}
      data-participant={quote.participant_id}
      className={`quote-card${isStarred ? " starred" : ""}${isActive ? " editing" : ""}${isFocused ? " bn-focused" : ""}${isSelected ? " bn-selected" : ""}`}
      onKeyDown={handleCardKeyDown}
      onClick={handleCardClick}
    >
      {featureFlags.quoteContextExpansion && contextAbove && contextAbove.length > 0 && contextAbove.map((seg, i) => (
        <ContextSegment
          key={`above-${seg.segment_index}-${i}`}
          speakerCode={seg.speaker_code}
          isModerator={seg.is_moderator}
          startTime={seg.start_time}
          text={seg.text}
          inaudible={seg.inaudible}
          quoteParticipantId={quote.participant_id}
          data-testid={`bn-quote-${domId}-ctx-above-${i}`}
        />
      ))}
      {showResearcherContext && quote.researcher_context && !hasModeratorContext && (
        <span className="context">[{quote.researcher_context}]</span>
      )}
      {/* Gated as well as the pill: a researcher who pinned questions open
          before the flag landed still has their dom_ids in localStorage, and
          without this they'd restore on load with no way to dismiss them. */}
      {featureFlags.moderatorQuestionPill && isQuestionOpen && moderatorQuestion && (() => {
        const { first, rest } = splitFirstSentence(moderatorQuestion.text);
        return (
          <div className="quote-row moderator-question-row" data-testid={`bn-quote-${domId}-mod-q-block`}>
            <span className="timecode" aria-hidden="true" style={{ visibility: "hidden" }}>[{timecodeStr}]</span>
            <div className="moderator-question">
              <span className="moderator-question-badge">
                <PersonBadge
                  code={moderatorQuestion.speaker_code}
                  role="moderator"
                />
                <button
                  className="moderator-question-dismiss"
                  onClick={() => onToggleQuestion(domId)}
                  aria-label={t("quotes.dismissModeratorQuestion")}
                  data-testid={`bn-quote-${domId}-mod-q-dismiss`}
                >
                  <Icon name="close" decorative />
                </button>
              </span>
              <span className="moderator-question-text">
                {showFullModQ || !rest ? moderatorQuestion.text : (
                  <>
                    {first}
                    <button
                      className="moderator-question-more"
                      onClick={() => setShowFullModQ(true)}
                    >
                      more&hellip;
                    </button>
                  </>
                )}
              </span>
            </div>
          </div>
        );
      })()}
      <div className="quote-row">
        {(() => {
          const hasExpansion =
            featureFlags.quoteContextExpansion && onExpandAbove && onExpandBelow;
          const timecodeEl = hasMedia ? (
            <TimecodeLink
              seconds={quote.start_timecode}
              endSeconds={quote.end_timecode}
              participantId={quote.participant_id}
              sessionId={sessionId}
              data-testid={`bn-quote-${domId}-timecode`}
            />
          ) : (
            <span className="timecode">[{timecodeStr}]</span>
          );
          if (hasExpansion) {
            return (
              <ExpandableTimecode
                canExpandAbove={canExpandAbove ?? false}
                canExpandBelow={canExpandBelow ?? false}
                onExpandAbove={onExpandAbove}
                onExpandBelow={onExpandBelow}
                exhaustedAbove={exhaustedAbove}
                exhaustedBelow={exhaustedBelow}
                data-testid={`bn-quote-${domId}-expand`}
              >
                {timecodeEl}
              </ExpandableTimecode>
            );
          }
          return timecodeEl;
        })()}
        <div className="quote-body">
          {hasModeratorContext && !isQuestionOpen && !isActive && (
            <button
              className={`moderator-pill${isPillVisible ? " visible" : ""}`}
              onClick={() => onToggleQuestion(domId)}
              onMouseEnter={() => onPillHoverEnter(domId)}
              onMouseLeave={() => onPillHoverLeave(domId)}
              aria-label={t("quotes.showModeratorQuestion")}
              data-testid={`bn-quote-${domId}-mod-q`}
            >
              Question?
            </button>
          )}
          {hasModeratorContext && !isQuestionOpen && !isActive && (
            <span
              className="quote-hover-zone"
              onClick={handleQuoteTextClick}
              onMouseEnter={() => onQuoteHoverEnter(domId)}
              onMouseLeave={() => onQuoteHoverLeave(domId)}
              aria-hidden="true"
            />
          )}
          <span className="quote-text-wrapper">
            {renderQuoteText()}
          </span>
          {" "}
          <span className="speaker">
            <PersonBadge
              code={quote.participant_id}
              role="participant"
              name={
                quote.speaker_name !== quote.participant_id
                  ? quote.speaker_name
                  : undefined
              }
              href={transcriptHref}
              place={momentPlace("navigate", sessionId, quote.start_timecode, null)}
              data-testid={`bn-quote-${domId}-speaker`}
            />
          </span>
          <div className="badges">
            {visibleSentiment && (
              <Badge
                text={visibleSentiment}
                variant="ai"
                sentiment={visibleSentiment}
                onDelete={() => onBadgeDelete(domId, visibleSentiment)}
                data-testid={`bn-quote-${domId}-badge-ai`}
              />
            )}
            {userTags.map((tag) => (
              <Badge
                key={`${tag.id ?? ""}:${tag.name}`}
                text={tag.name}
                variant="user"
                colour={tag.colour_set ? getTagBg(tag.colour_set, tag.colour_index) : undefined}
                className={flashingTags.has(`${domId}:${tag.name}`) ? "badge-accept-flash" : undefined}
                onDelete={() => (tag.id != null ? onTagRemove(domId, tag.name, tag.id) : onTagRemove(domId, tag.name))}
                data-testid={`bn-quote-${domId}-badge-${tag.name}`}
              />
            ))}
            {proposedTags.map((pt) => (
              <Badge
                key={`proposed-${pt.id}`}
                text={pt.tag_name}
                variant="proposed"
                colour={getTagBg(pt.colour_set, pt.colour_index)}
                rationale={pt.rationale}
                onAccept={() => onProposedAccept(pt.id, pt.tag_name)}
                onDeny={() => onProposedDeny(pt.id)}
                data-testid={`bn-quote-${domId}-proposed-${pt.id}`}
              />
            ))}
            {isTagInputOpen ? (
              <TagInput
                vocabulary={tagVocabulary}
                groupedVocabulary={groupedVocabulary}
                exclude={existingTagNames}
                hiddenTags={hiddenTagNames}
                onCommit={handleTagCommit}
                onCancel={handleTagCancel}
                onCommitAndReopen={handleTagCommitAndReopen}
                data-testid={`bn-quote-${domId}-tag-input`}
              />
            ) : (
              <span
                className="badge badge-add"
                role="button"
                tabIndex={0}
                aria-label={t("quotes.addTag")}
                onClick={() => setIsTagInputOpen(true)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    setIsTagInputOpen(true);
                  }
                }}
                data-testid={`bn-quote-${domId}-add-tag`}
              >
                <Icon name="add" decorative />
              </span>
            )}
            {hasDeletedBadges && (
              <button
                className="badge-restore"
                aria-label={t("quotes.restoreTags")}
                title={t("quotes.restoreTags")}
                onClick={() => onBadgeRestore(domId)}
                data-testid={`bn-quote-${domId}-restore`}
              >
                <Icon name="revert" decorative />
              </button>
            )}
          </div>
        </div>
      </div>
      {featureFlags.quoteContextExpansion && contextBelow && contextBelow.length > 0 && contextBelow.map((seg, i) => (
        <ContextSegment
          key={`below-${seg.segment_index}-${i}`}
          speakerCode={seg.speaker_code}
          isModerator={seg.is_moderator}
          startTime={seg.start_time}
          text={seg.text}
          inaudible={seg.inaudible}
          quoteParticipantId={quote.participant_id}
          data-testid={`bn-quote-${domId}-ctx-below-${i}`}
        />
      ))}
      <Toggle
        active={false}
        onToggle={() => onToggleHide(domId, true)}
        className="hide-btn"
        aria-label={t("quotes.hideQuote")}
        data-testid={`bn-quote-${domId}-hide`}
      >
        {HideIcon}
      </Toggle>
      <button
        className={`action-btn undo-btn${isEdited ? " visible" : ""}`}
        aria-label={t("quotes.revertToOriginal")}
        title={t("quotes.revertToOriginal")}
        onClick={handleUndo}
        data-testid={`bn-quote-${domId}-undo`}
      >
        <Icon name="revert" decorative />
      </button>
      <Toggle
        active={isStarred}
        onToggle={(newState) => onToggleStar(domId, newState)}
        className="star-btn"
        activeClassName="starred"
        aria-label={t("quotes.starQuote")}
        data-testid={`bn-quote-${domId}-star`}
      >
        &#9733;
      </Toggle>
    </blockquote>
  );
}
