/**
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

import { useState, useCallback, useRef, useEffect } from "react";
import {
  Badge,
  ContextSegment,
  ExpandableTimecode,
  PersonBadge,
  TagInput,
  TimecodeLink,
  Toggle,
} from "../components";
import type { ModeratorQuestionResponse, ProposedTagBrief, QuoteResponse, TranscriptSegmentResponse } from "../utils/types";
import { formatTimecode } from "../utils/format";
import { getTagBg } from "../utils/colours";
import { useCropEdit } from "../hooks/useCropEdit";

// ── SVG icon for the hide button (eye-slash) ────────────────────────────

const HideIcon = (
  <svg
    width="14"
    height="14"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    strokeLinecap="round"
  >
    <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94" />
    <path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19" />
    <line x1="1" y1="1" x2="23" y2="23" />
  </svg>
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
  /** Tags currently on this quote (user-added). */
  userTags: { name: string; codebook_group: string; colour_set: string; colour_index: number }[];
  /** AI sentiment badges that have been deleted. */
  deletedBadges: string[];
  /** Whether the quote text has been edited. */
  isEdited: boolean;
  /** Full tag vocabulary for auto-suggest. */
  tagVocabulary: string[];
  /** Session ID for transcript link. */
  sessionId: string;
  /** Whether video is available for this quote. */
  hasMedia: boolean;
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
  onTagAdd: (domId: string, tagName: string) => void;
  onTagRemove: (domId: string, tagName: string) => void;
  onBadgeDelete: (domId: string, sentiment: string) => void;
  onBadgeRestore: (domId: string) => void;
  onProposedAccept: (proposalId: number, tagName: string) => void;
  onProposedDeny: (proposalId: number) => void;
  onToggleQuestion: (domId: string) => void;
  onQuoteHoverEnter: (domId: string) => void;
  onQuoteHoverLeave: (domId: string) => void;
  onPillHoverEnter: (domId: string) => void;
  onPillHoverLeave: (domId: string) => void;
}

export function QuoteCard({
  quote,
  displayText,
  isStarred,
  isHidden,
  userTags,
  deletedBadges,
  isEdited,
  tagVocabulary,
  sessionId,
  hasMedia,
  proposedTags,
  flashingTags,
  onToggleStar,
  onToggleHide,
  onEditCommit,
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
}: QuoteCardProps) {
  const [isTagInputOpen, setIsTagInputOpen] = useState(false);
  const [showFullModQ, setShowFullModQ] = useState(false);
  const [bracketsVisible, setBracketsVisible] = useState(false);

  const domId = quote.dom_id;
  const hasModeratorContext = quote.segment_index > 0;
  const textSpanRef = useRef<HTMLSpanElement>(null);

  // ── Crop edit hook ──────────────────────────────────────────────────

  const handleCropCommit = useCallback(
    (newText: string) => {
      onEditCommit(domId, newText);
    },
    [domId, onEditCommit],
  );

  const handleCropCancel = useCallback(() => {
    // No-op — just exit edit mode.
  }, []);

  const crop = useCropEdit({
    currentText: displayText,
    originalText: quote.text,
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

  // ── Attach drag handlers to crop-mode brackets ────────────────────
  // In crop mode (mode 3), brackets are rendered via dangerouslySetInnerHTML
  // so they have no React event handlers. We attach pointerdown listeners
  // imperatively after each render. This mirrors the mockup's
  // attachHandleDrag() pattern (called after every innerHTML= rebuild).

  useEffect(() => {
    if (crop.mode !== "crop" || !textSpanRef.current) return;
    const handles = textSpanRef.current.querySelectorAll(".crop-handle");
    const listeners: Array<[Element, (e: Event) => void]> = [];
    handles.forEach((handle) => {
      const side = handle.getAttribute("data-handle") as "start" | "end";
      const listener = (e: Event) => {
        crop.handleBracketPointerDown(side, e as unknown as React.PointerEvent, textSpanRef.current!);
      };
      handle.addEventListener("pointerdown", listener);
      listeners.push([handle, listener]);
    });
    return () => {
      listeners.forEach(([el, fn]) => el.removeEventListener("pointerdown", fn));
    };
  }, [crop.mode, crop.cropStart, crop.cropEnd, crop.handleBracketPointerDown]);

  // ── Click-outside → commit ──────────────────────────────────────────

  useEffect(() => {
    if (crop.mode === "idle") return;
    const onPointerDown = (e: PointerEvent) => {
      const card = textSpanRef.current?.closest("blockquote");
      if (card && !card.contains(e.target as Node)) {
        const editableEl = textSpanRef.current?.querySelector(".crop-editable") as HTMLElement | null;
        crop.commitEdit(editableEl);
      }
    };
    document.addEventListener("pointerdown", onPointerDown);
    return () => document.removeEventListener("pointerdown", onPointerDown);
  }, [crop]);

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
      }
    },
    [crop],
  );

  // ── Edit mode entry (click on quote text in idle) ───────────────────

  const handleQuoteTextClick = useCallback(
    (e: React.MouseEvent) => {
      if (crop.mode === "idle") {
        crop.enterEditMode();
      } else if (crop.mode === "crop") {
        // Click on included word → back to hybrid (text editing)
        const target = e.target as HTMLElement;
        const isIncluded =
          (target.classList.contains("crop-word") && target.classList.contains("included")) ||
          target.classList.contains("crop-included-region");
        if (isIncluded) {
          crop.reenterTextEdit();
        }
      }
    },
    [crop],
  );

  // ── Hybrid mode: keyboard + blur on contenteditable ─────────────────

  const handleEditKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        e.stopPropagation();
        const editableEl = textSpanRef.current?.querySelector(".crop-editable") as HTMLElement | null;
        crop.commitEdit(editableEl);
      } else if (e.key === "Escape") {
        e.preventDefault();
        e.stopPropagation();
        crop.cancelEdit();
      }
    },
    [crop],
  );

  const handleEditBlur = useCallback(() => {
    crop.blurTimeoutRef.current = setTimeout(() => {
      if (crop.suppressBlurRef.current) {
        crop.suppressBlurRef.current = false;
        return;
      }
      if (crop.mode === "hybrid") {
        const editableEl = textSpanRef.current?.querySelector(".crop-editable") as HTMLElement | null;
        crop.commitEdit(editableEl);
      }
    }, 150);
  }, [crop]);

  // ── Undo handler ────────────────────────────────────────────────────

  const handleUndo = useCallback(
    (e: React.MouseEvent) => {
      e.stopPropagation();
      onEditCommit(domId, quote.text);
    },
    [domId, quote.text, onEditCommit],
  );

  // ── Tag handlers ────────────────────────────────────────────────────

  const handleTagCommit = useCallback(
    (tagName: string) => {
      setIsTagInputOpen(false);
      onTagAdd(domId, tagName);
    },
    [domId, onTagAdd],
  );

  const handleTagCommitAndReopen = useCallback(
    (tagName: string) => {
      onTagAdd(domId, tagName);
      setIsTagInputOpen(false);
      requestAnimationFrame(() => setIsTagInputOpen(true));
    },
    [domId, onTagAdd],
  );

  const handleTagCancel = useCallback(() => {
    setIsTagInputOpen(false);
  }, []);

  // ── Visibility ──────────────────────────────────────────────────────

  if (isHidden) return null;

  // ── Derived state ───────────────────────────────────────────────────

  const transcriptHref = `sessions/transcript_${sessionId}.html#t-${Math.floor(quote.start_timecode)}`;
  const visibleSentiment =
    quote.sentiment && !deletedBadges.includes(quote.sentiment)
      ? quote.sentiment
      : null;
  const hasDeletedBadges = deletedBadges.length > 0;
  const existingTagNames = userTags.map((t) => t.name);
  const timecodeStr = formatTimecode(quote.start_timecode);
  const isActive = crop.mode !== "idle";
  const bracketCls = bracketsVisible ? "crop-handle bracket-visible" : "crop-handle bracket-delayed";

  // ── Render quote text area ──────────────────────────────────────────

  function renderQuoteText() {
    if (crop.mode === "hybrid") {
      // Mode 2: contenteditable with optional excluded word spans
      const includedText = crop.words.slice(crop.cropStart, crop.cropEnd).join(" ");
      return (
        <span
          className="quote-text"
          ref={textSpanRef}
          data-testid={`bn-quote-${domId}-text`}
          data-edit-key={`${domId}:text`}
        >
          {/* Leading excluded words */}
          {crop.cropStart > 0 && crop.words.slice(0, crop.cropStart).map((w, i) => (
            <span key={`ex-${i}`} className="crop-word excluded" data-i={i}>
              {w}{" "}
            </span>
          ))}
          {/* [ bracket */}
          <span
            className={bracketCls}
            data-handle="start"
            onPointerDown={(e) => crop.handleBracketPointerDown("start", e, textSpanRef.current!)}
          >
            [
          </span>
          {/* Contenteditable included text */}
          <span
            className="crop-editable"
            contentEditable
            suppressContentEditableWarning
            onKeyDown={handleEditKeyDown}
            onBlur={handleEditBlur}
            ref={(el) => {
              // Auto-focus on mount
              if (el && document.activeElement !== el) {
                el.focus();
              }
            }}
          >
            {includedText}
          </span>
          {/* ] bracket */}
          <span
            className={bracketCls}
            data-handle="end"
            onPointerDown={(e) => crop.handleBracketPointerDown("end", e, textSpanRef.current!)}
          >
            ]
          </span>
          {/* Trailing excluded words */}
          {crop.cropEnd < crop.words.length && crop.words.slice(crop.cropEnd).map((w, i) => (
            <span key={`ex-end-${i}`} className="crop-word excluded" data-i={crop.cropEnd + i}>
              {" "}{w}
            </span>
          ))}
        </span>
      );
    }

    if (crop.mode === "crop") {
      // Mode 3: word spans for drag hit detection
      const html: string[] = [];
      let inIncluded = false;
      for (let i = 0; i < crop.words.length; i++) {
        const isExcluded = i < crop.cropStart || i >= crop.cropEnd;

        if (i === crop.cropStart) {
          html.push(`<span class="crop-handle bracket-visible" data-handle="start">[</span>`);
          html.push(`<span class="crop-included-region">`);
          inIncluded = true;
        }

        const cls = `crop-word ${isExcluded ? "excluded" : "included"}`;
        html.push(
          `<span class="${cls}" data-i="${i}">${escapeHtml(crop.words[i])}</span>`,
        );

        if (i === crop.cropEnd - 1 && inIncluded) {
          html.push(`</span>`); // close .crop-included-region
          inIncluded = false;
          html.push(`<span class="crop-handle bracket-visible" data-handle="end">]</span>`);
        }

        if (i < crop.words.length - 1) html.push(" ");
      }

      return (
        <span
          className="quote-text"
          ref={textSpanRef}
          data-testid={`bn-quote-${domId}-text`}
          data-edit-key={`${domId}:text`}
          onClick={handleQuoteTextClick}
          dangerouslySetInnerHTML={{ __html: html.join("") }}
        />
      );
    }

    // Idle mode — plain text with optional ellipsis
    return (
      <span
        className="quote-text"
        ref={textSpanRef}
        style={{ cursor: "text" }}
        onClick={handleQuoteTextClick}
        data-testid={`bn-quote-${domId}-text`}
        data-edit-key={`${domId}:text`}
      >
        {crop.hasLeftCrop && <span className="crop-ellipsis">{"\u2026"}</span>}
        {displayText}
        {crop.hasRightCrop && <span className="crop-ellipsis">{"\u2026"}</span>}
      </span>
    );
  }

  return (
    <blockquote
      id={domId}
      data-timecode={timecodeStr}
      data-participant={quote.participant_id}
      className={`quote-card${isStarred ? " starred" : ""}${isActive ? " editing" : ""}`}
      onKeyDown={handleCardKeyDown}
    >
      {contextAbove && contextAbove.length > 0 && contextAbove.map((seg, i) => (
        <ContextSegment
          key={`above-${seg.segment_index}-${i}`}
          speakerCode={seg.speaker_code}
          isModerator={seg.is_moderator}
          startTime={seg.start_time}
          text={seg.text}
          quoteParticipantId={quote.participant_id}
          data-testid={`bn-quote-${domId}-ctx-above-${i}`}
        />
      ))}
      {quote.researcher_context && !hasModeratorContext && (
        <span className="context">[{quote.researcher_context}]</span>
      )}
      {isQuestionOpen && moderatorQuestion && (() => {
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
                  aria-label="Dismiss moderator question"
                  data-testid={`bn-quote-${domId}-mod-q-dismiss`}
                >
                  &times;
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
          const hasExpansion = onExpandAbove && onExpandBelow;
          const timecodeEl = hasMedia ? (
            <TimecodeLink
              seconds={quote.start_timecode}
              endSeconds={quote.end_timecode}
              participantId={quote.participant_id}
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
              aria-label="Show moderator question"
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
            <span className="smart-quote">{"\u201c"}</span>
            {renderQuoteText()}
            <span className="smart-quote">{"\u201d"}</span>
          </span>
          &nbsp;
          <span className="speaker">
            &mdash;&nbsp;
            <PersonBadge
              code={quote.participant_id}
              role="participant"
              name={
                quote.speaker_name !== quote.participant_id
                  ? quote.speaker_name
                  : undefined
              }
              href={transcriptHref}
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
                key={tag.name}
                text={tag.name}
                variant="user"
                colour={tag.colour_set ? getTagBg(tag.colour_set, tag.colour_index) : undefined}
                className={flashingTags.has(`${domId}:${tag.name}`) ? "badge-accept-flash" : undefined}
                onDelete={() => onTagRemove(domId, tag.name)}
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
                exclude={existingTagNames}
                onCommit={handleTagCommit}
                onCancel={handleTagCancel}
                onCommitAndReopen={handleTagCommitAndReopen}
                data-testid={`bn-quote-${domId}-tag-input`}
              />
            ) : (
              <span
                className="badge badge-add"
                aria-label="Add tag"
                onClick={() => setIsTagInputOpen(true)}
                data-testid={`bn-quote-${domId}-add-tag`}
              >
                +
              </span>
            )}
            {hasDeletedBadges && (
              <button
                className="badge-restore"
                aria-label="Restore tags"
                title="Restore tags"
                onClick={() => onBadgeRestore(domId)}
                data-testid={`bn-quote-${domId}-restore`}
              >
                &#x21A9;
              </button>
            )}
          </div>
        </div>
      </div>
      {contextBelow && contextBelow.length > 0 && contextBelow.map((seg, i) => (
        <ContextSegment
          key={`below-${seg.segment_index}-${i}`}
          speakerCode={seg.speaker_code}
          isModerator={seg.is_moderator}
          startTime={seg.start_time}
          text={seg.text}
          quoteParticipantId={quote.participant_id}
          data-testid={`bn-quote-${domId}-ctx-below-${i}`}
        />
      ))}
      <Toggle
        active={false}
        onToggle={() => onToggleHide(domId, true)}
        className="hide-btn"
        aria-label="Hide this quote"
        data-testid={`bn-quote-${domId}-hide`}
      >
        {HideIcon}
      </Toggle>
      <button
        className={`action-btn undo-btn${isEdited ? " visible" : ""}`}
        aria-label="Revert to original"
        title="Revert to original"
        onClick={handleUndo}
        data-testid={`bn-quote-${domId}-undo`}
      >
        &#x21A9;
      </button>
      <Toggle
        active={isStarred}
        onToggle={(newState) => onToggleStar(domId, newState)}
        className="star-btn"
        activeClassName="starred"
        aria-label="Star this quote"
        data-testid={`bn-quote-${domId}-star`}
      >
        &#9733;
      </Toggle>
    </blockquote>
  );
}
