/**
 * QuoteCard — single quote card composition.
 *
 * Renders one blockquote with the same DOM structure as
 * `quote_card.html`, using the existing React primitives (Badge,
 * PersonBadge, TimecodeLink, EditableText, Toggle, TagInput).
 *
 * Quote text editing uses a unified click-to-edit interaction:
 * click → yellow bg + gold bracket handles → type to edit AND/OR
 * drag brackets to crop → Enter to commit. A long quote keeps its paragraphs
 * while it is edited; Shift-Return starts one, Backspace at a paragraph's
 * start joins it. See useCropEdit, utils/quoteEditSurface.ts and
 * docs/design-quote-editing.md for full behaviour spec.
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
} from "../components";
import type { TagVocabularyGroup, TagPick } from "../components";
import type { ModeratorQuestionResponse, ProposedTagBrief, QuoteResponse, TranscriptSegmentResponse } from "../utils/types";
import { formatTimecode } from "../utils/format";
import { getTagBg } from "../utils/colours";
import { isExportMode } from "../utils/exportData";
import { reportHref } from "../utils/reportHref";
import { featureFlags } from "../utils/featureFlags";
import { isMac } from "../utils/platform";
import { highlightTerms } from "../utils/highlight";
import {
  autoBreaks,
  blockRanges,
  caretAtPoint,
  clampCaret,
  judgeInput,
  rangeKeepsSurface,
  setBracketsVisible as showBrackets,
} from "../utils/quoteEditSurface";
import { useDisplayBreaks } from "../contexts/DisplayPrefsStore";
import type { SearchTerm } from "../utils/searchMatch";
import { useCropEdit, type BreaksChange } from "../hooks/useCropEdit";
import { useFocus, useQuoteFocusState } from "../contexts/FocusContext";
import { Icon } from "../components/Icon";
import { momentPlace } from "../utils/contextPlace";

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
  /**
   * A committed edit: the new words (null when only the paragraphs changed),
   * and, when the researcher's own paragraphs changed, `breaks`.
   */
  onEditCommit: (domId: string, newText: string | null, breaks?: BreaksChange) => void;
  /** The researcher's own paragraph breaks (word positions), or null: placed automatically. */
  researcherBreaks?: number[] | null;
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

/**
 * ⌘A on the Mac, Ctrl-A elsewhere: on the Mac, Ctrl-A is the text system's
 * "start of paragraph" and stays native (review 25 Nov, finding 35). The A is
 * the letter on Latin layouts (AZERTY's sits on KeyQ) and the key's place on
 * others, where `key` is a Cyrillic or Greek letter.
 */
function isSelectAll(e: React.KeyboardEvent): boolean {
  const a = e.key.toLowerCase() === "a" || (e.code === "KeyA" && !/^[a-z]$/i.test(e.key));
  const mod = isMac() ? e.metaKey && !e.ctrlKey : e.ctrlKey && !e.metaKey;
  return a && mod && !e.altKey && !e.shiftKey;
}

export function QuoteCard({
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
  researcherBreaks = null,
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

  // The edit surface: React renders it empty and utils/quoteEditSurface.ts
  // draws into it, so a re-render never reconciles over what was typed.
  const editHostRef = useRef<HTMLSpanElement>(null);
  // Where the click that opened the edit landed: the layout does not move, so
  // the caret goes to the same word.
  const clickPoint = useRef<{ x: number; y: number } | null>(null);

  // ── Crop edit hook ──────────────────────────────────────────────────

  const handleCropCommit = useCallback(
    (newText: string | null, breaks?: BreaksChange) => {
      if (breaks) onEditCommit(domId, newText, breaks);
      else if (newText !== null) onEditCommit(domId, newText);
    },
    [domId, onEditCommit],
  );

  const handleCropCancel = useCallback(() => {
    // No-op — just exit edit mode.
  }, []);

  // ── Paragraphs (Break long paragraphs, and the researcher's own) ────
  // Shown at rest: the researcher's own breaks if there are any (whatever the
  // Display setting: owner, 21 Nov 2026), else the automatic ones when Break
  // long paragraphs is on. The edit modes freeze exactly these; nothing is
  // re-placed until commit. The automatic ones are computed from the text each
  // time, never stored.
  const breaksOn = useDisplayBreaks() === "on";
  const shownBreaks = useMemo(
    () => researcherBreaks ?? (breaksOn ? autoBreaks(displayText) : []),
    [researcherBreaks, breaksOn, displayText],
  );
  const blocks = useMemo(() => {
    if (shownBreaks.length === 0) return [displayText];
    const words = displayText.split(/\s+/).filter(Boolean);
    return blockRanges(words.length, shownBreaks).map(([s, e]) => words.slice(s, e).join(" "));
  }, [shownBreaks, displayText]);
  const broken = blocks.length > 1;

  const crop = useCropEdit({
    currentText: displayText,
    originalText: quote.text,
    researcherBreaks,
    shownBreaks,
    autoBreaksOn: breaksOn,
    onCommit: handleCropCommit,
    onCancel: handleCropCancel,
  });

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

  // ── Draw the edit surface: text mode once on entry, trim on each move ──

  const { drawSurface } = crop;
  useLayoutEffect(() => {
    const host = editHostRef.current;
    if (!host || crop.mode === "idle") return;
    drawSurface(host, crop.mode === "crop");
    if (crop.mode !== "hybrid") return;
    if (document.activeElement !== host) host.focus();
    const pt = clickPoint.current;
    clickPoint.current = null;
    if (!pt || !caretAtPoint(host, pt.x, pt.y)) {
      const r = document.createRange();
      r.selectNodeContents(host.querySelector(".crop-editable") ?? host);
      r.collapse(false);
      window.getSelection()?.removeAllRanges();
      window.getSelection()?.addRange(r);
    }
    // Drawn again only when the mode or the trim changes: a re-render for any
    // other reason must not redraw over what was typed.
  }, [crop.mode, crop.cropStart, crop.cropEnd, drawSurface]);

  // The brackets' fade-in touches only the brackets, never the typed text.
  useEffect(() => {
    const host = editHostRef.current;
    if (host && crop.mode !== "idle") showBrackets(host, bracketsVisible || crop.mode === "crop");
  }, [bracketsVisible, crop.mode]);

  // ── Bracket drag: the brackets are drawn by the surface, so are their listeners ──

  const { handleBracketPointerDown } = crop;
  useEffect(() => {
    const host = editHostRef.current;
    if (crop.mode === "idle" || !host) return;
    const listener = (e: PointerEvent) => {
      const handle = (e.target as HTMLElement).closest<HTMLElement>(".crop-handle");
      if (!handle || !host.contains(handle)) return;
      handleBracketPointerDown(handle.dataset.handle as "start" | "end", e, host);
    };
    host.addEventListener("pointerdown", listener);
    return () => host.removeEventListener("pointerdown", listener);
  }, [crop.mode, handleBracketPointerDown]);

  // ── Text mode: the surface stays whole (review 21 Nov, findings 1 and 3) ──
  // Native listeners: React's onBeforeInput misses deletes and line breaks.
  // The caret is kept inside the typed text, and an input that would delete a
  // quote mark or a trimmed word, or run two paragraphs together, is refused.

  useEffect(() => {
    const host = editHostRef.current;
    if (crop.mode !== "hybrid" || !host) return;
    const onBeforeInput = (e: InputEvent) => {
      const verdict = judgeInput(host, e);
      if (verdict === "allow") return;
      e.preventDefault();
      if (verdict === "retype" && e.data && typeof document.execCommand === "function") {
        clampCaret(host);
        document.execCommand("insertText", false, e.data);
      }
    };
    const onSelectionChange = () => {
      if (document.activeElement === host) clampCaret(host);
    };
    host.addEventListener("beforeinput", onBeforeInput);
    document.addEventListener("selectionchange", onSelectionChange);
    return () => {
      host.removeEventListener("beforeinput", onBeforeInput);
      document.removeEventListener("selectionchange", onSelectionChange);
    };
  }, [crop.mode]);

  // ── Click-outside → commit ──────────────────────────────────────────

  useEffect(() => {
    if (crop.mode === "idle") return;
    const onPointerDown = (e: PointerEvent) => {
      const card = editHostRef.current?.closest("blockquote");
      if (card && !card.contains(e.target as Node)) {
        crop.commitEdit(editHostRef.current);
      }
    };
    document.addEventListener("pointerdown", onPointerDown);
    return () => document.removeEventListener("pointerdown", onPointerDown);
  }, [crop]);

  // ── Leaving mid-edit → commit ───────────────────────────────────────
  // A lens switch (⌘1–5, the native sidebar) unmounts the card mid-edit.
  // WebKit fires no blur for a removed editor, and a blur that did fire
  // committed 150 ms later, after the editor was gone, writing the old text
  // back. So as the card goes, drop any pending blur and commit what is on
  // screen, the way blur does (R88). An unchanged edit writes nothing and adds
  // no Undo, by commitEdit's own test (useCropEdit).
  // Layout effects: their cleanup runs while the editor is still in the DOM,
  // and the ref is written outside render.

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

  // ── Tab: commit, and stay on the card (owner, 21 Nov 2026) ──────────
  // In both modes. Until then Tab blurred the text, which committed 150 ms
  // later and moved focus to the speaker's name; in trim mode nothing listened
  // for it, so focus left and the card stayed mid-edit.

  // Return and Escape keep the researcher on the card too: the edit surface is
  // replaced as the card goes back to rest, and focus would fall to the top of
  // the page (review 21 Nov, finding 8). Called after the commit or cancel,
  // which clears the hold: moving focus to the card blurs the text, and that
  // blur must not commit again. In trimming the card has focus already, and a
  // hold no blur comes for would swallow the next edit's (finding 10).
  const stayOnCard = useCallback(
    (card: Element | null | undefined) => {
      if (editHostRef.current?.contains(document.activeElement)) crop.holdBlur();
      if (card instanceof HTMLElement) {
        card.setAttribute("tabindex", "-1");
        card.focus({ preventScroll: true });
      }
      setFocus(domId, { scroll: false });
    },
    [crop, domId, setFocus],
  );

  const commitAndStay = useCallback(
    (e: React.KeyboardEvent) => {
      e.preventDefault();
      e.stopPropagation();
      const card = editHostRef.current?.closest("blockquote");
      crop.commitEdit(editHostRef.current);
      stayOnCard(card);
    },
    [crop, stayOnCard],
  );

  // ── Card-level keydown for crop mode ────────────────────────────────

  const handleCardKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (crop.mode !== "crop") return;
      if (e.key === "Enter") {
        e.preventDefault();
        e.stopPropagation();
        crop.commitEdit();
      } else if (e.key === "Escape") {
        e.preventDefault();
        e.stopPropagation();
        crop.cancelEdit();
      } else if (e.key === "Tab") {
        commitAndStay(e);
      }
    },
    [crop, commitAndStay],
  );

  // ── Edit mode entry (click on quote text in idle) ───────────────────

  const handleQuoteTextClick = useCallback(
    (e: React.MouseEvent) => {
      // Read-only in an exported report: clicking the quote text must NOT enter
      // crop/trim edit mode (the edit can't persist and vanishes on reload).
      if (isExportMode()) return;
      // Don't enter edit mode when modifier keys are held (focus/selection)
      if (e.metaKey || e.ctrlKey || e.shiftKey) return;
      if (crop.mode === "idle") {
        clickPoint.current = { x: e.clientX, y: e.clientY };
        crop.enterEditMode();
      } else if (crop.mode === "crop") {
        // Click on included word → back to hybrid (text editing)
        const target = e.target as HTMLElement;
        const isIncluded =
          (target.classList.contains("crop-word") && target.classList.contains("included")) ||
          !!target.closest(".crop-included-region");
        if (isIncluded) {
          clickPoint.current = { x: e.clientX, y: e.clientY };
          crop.reenterTextEdit();
        }
      }
    },
    [crop],
  );

  // ── Hybrid mode: keyboard, paste and blur on the edit surface ───────

  const handleEditKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      const host = editHostRef.current;
      // An IME's Enter confirms its composition. WebKit (Safari, the Mac app)
      // sends that Enter after compositionend with isComposing false and
      // keyCode 229, so both are checked (review 21 Nov, finding 7).
      if (!host || e.nativeEvent.isComposing || e.keyCode === 229) return;
      if (e.key === "Enter" && e.shiftKey) {
        // A new paragraph at the caret (the transcript's Return; here Return commits).
        e.preventDefault();
        e.stopPropagation();
        crop.splitAtCaret(host, bracketsVisible);
      } else if (e.key === "Enter") {
        e.preventDefault();
        e.stopPropagation();
        const card = host.closest("blockquote");
        crop.commitEdit(host);
        stayOnCard(card);
      } else if (e.key === "Escape") {
        e.preventDefault();
        e.stopPropagation();
        const card = host.closest("blockquote");
        crop.cancelEdit();
        stayOnCard(card);
      } else if (e.key === "Tab") {
        commitAndStay(e);
      } else if (isSelectAll(e)) {
        // Select All takes the paragraph's typed text: a selection across the
        // quote marks, trimmed words or paragraphs cannot be typed over.
        const sel = window.getSelection();
        const node = sel && sel.rangeCount > 0 ? sel.getRangeAt(0).startContainer : null;
        const el = node instanceof Element ? node : node?.parentElement;
        const run = el?.closest(".bn-block")?.querySelector(".crop-editable");
        if (run) {
          e.preventDefault();
          e.stopPropagation();
          const r = document.createRange();
          r.selectNodeContents(run);
          sel?.removeAllRanges();
          sel?.addRange(r);
        }
      } else if ((e.key === "Backspace" || e.key === "Delete") && !e.metaKey && !e.altKey && !e.ctrlKey) {
        // At a paragraph's start (Backspace) or end (Delete): join. At the
        // quote's own start or end: nothing, rather than delete a quote mark.
        if (crop.joinAtCaret(host, e.key === "Backspace" ? -1 : 1, bracketsVisible) !== null) {
          e.preventDefault();
          e.stopPropagation();
        }
      }
    },
    [crop, bracketsVisible, commitAndStay, stayOnCard],
  );

  // A paste is plain text, on one line: pasted markup would bring another
  // page's paragraphs and styling into the quote.
  // It replaces only what typing could: a selection across paragraphs, quote
  // marks or trimmed words is refused, as typing over it is (finding 33).
  const handleEditPaste = useCallback((e: React.ClipboardEvent) => {
    e.preventDefault();
    const host = editHostRef.current;
    const sel = window.getSelection();
    if (!host || !sel || sel.rangeCount === 0 || !rangeKeepsSurface(host, sel.getRangeAt(0))) return;
    clampCaret(host);
    const text = e.clipboardData.getData("text/plain").replace(/\s+/g, " ");
    if (text && typeof document.execCommand === "function") document.execCommand("insertText", false, text);
  }, []);

  const handleEditBlur = useCallback(() => {
    crop.blurTimeoutRef.current = setTimeout(() => {
      if (crop.suppressBlurRef.current) {
        crop.suppressBlurRef.current = false;
        return;
      }
      if (crop.mode === "hybrid") {
        crop.commitEdit(editHostRef.current);
      }
    }, 150);
  }, [crop]);

  // ── Undo handler ────────────────────────────────────────────────────

  const handleUndo = useCallback(
    (e: React.MouseEvent) => {
      e.stopPropagation();
      // Back to the pipeline's words, and to automatic paragraphs.
      if (researcherBreaks !== null) onEditCommit(domId, quote.text, { value: null });
      else onEditCommit(domId, quote.text);
    },
    [domId, quote.text, researcherBreaks, onEditCommit],
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
      // Both edit modes draw into one surface, as the same paragraphs as at
      // rest, with the quote marks kept in place and the brackets laid over
      // them (utils/quoteEditSurface.ts). React gives it no children and its
      // own key, so it never reconciles over what was typed.
      return (
        // Card-level keyboard handling for trim mode lives on the <blockquote>.
        <span
          key="edit-surface"
          className="quote-text"
          ref={editHostRef}
          data-testid={`bn-quote-${domId}-text`}
          data-edit-key={`${domId}:text`}
          role={crop.mode === "hybrid" ? "textbox" : undefined}
          aria-multiline={crop.mode === "hybrid" ? true : undefined}
          tabIndex={crop.mode === "hybrid" ? 0 : undefined}
          contentEditable={crop.mode === "hybrid"}
          suppressContentEditableWarning
          onKeyDown={crop.mode === "hybrid" ? handleEditKeyDown : undefined}
          onPaste={crop.mode === "hybrid" ? handleEditPaste : undefined}
          onBlur={crop.mode === "hybrid" ? handleEditBlur : undefined}
          onClick={handleQuoteTextClick}
        />
      );
    }

    // Idle mode — plain text with optional ellipsis and search highlighting
    if (broken) {
      // Broken into blocks: the opening quote sits inside the first block and the
      // closing one inside the last, so neither stands alone on a line, and the
      // crop ellipses ride the first and last. The last block is drawn inline
      // (display-prefs.css) so the speaker chip follows on its last line.
      const last = blocks.length - 1;
      return (
        // eslint-disable-next-line jsx-a11y/click-events-have-key-events, jsx-a11y/no-static-element-interactions
        <span
          className="quote-text"
          ref={textSpanRef}
          style={{ cursor: "text" }}
          onClick={handleQuoteTextClick}
          data-testid={`bn-quote-${domId}-text`}
          data-edit-key={`${domId}:text`}
        >
          {blocks.map((block, i) => (
            <span key={i} className="bn-block">
              {i === 0 && <span className="smart-quote">{"\u201c"}</span>}
              {i === 0 && crop.hasLeftCrop && <span className="crop-ellipsis">{"\u2026"}</span>}
              {highlight ? highlightTerms(block, highlight) : block}
              {i === last && crop.hasRightCrop && <span className="crop-ellipsis">{"\u2026"}</span>}
              {i === last && <span className="smart-quote">{"\u201d"}</span>}
            </span>
          ))}
        </span>
      );
    }

    return (
      // Click-to-edit quote text; card-level keyboard activation lives on
      // the parent <blockquote> (handleCardKeyDown).
      // eslint-disable-next-line jsx-a11y/click-events-have-key-events, jsx-a11y/no-static-element-interactions
      <span
        className="quote-text"
        ref={textSpanRef}
        style={{ cursor: "text" }}
        onClick={handleQuoteTextClick}
        data-testid={`bn-quote-${domId}-text`}
        data-edit-key={`${domId}:text`}
      >
        {crop.hasLeftCrop && <span className="crop-ellipsis">{"\u2026"}</span>}
        {highlight ? highlightTerms(displayText, highlight) : displayText}
        {crop.hasRightCrop && <span className="crop-ellipsis">{"\u2026"}</span>}
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
            {!broken && !isActive && <span className="smart-quote">{"\u201c"}</span>}
            {renderQuoteText()}
            {!broken && !isActive && <span className="smart-quote">{"\u201d"}</span>}
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
