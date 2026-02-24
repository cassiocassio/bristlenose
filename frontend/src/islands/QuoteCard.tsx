/**
 * QuoteCard — single quote card composition.
 *
 * Renders one blockquote with the same DOM structure as
 * `quote_card.html`, using the existing React primitives (Badge,
 * PersonBadge, TimecodeLink, EditableText, Toggle, TagInput).
 *
 * All state mutations are delegated to the parent (QuoteGroup)
 * via callbacks.
 */

import { useState, useCallback } from "react";
import {
  Badge,
  ContextSegment,
  EditableText,
  ExpandableTimecode,
  PersonBadge,
  TagInput,
  TimecodeLink,
  Toggle,
} from "../components";
import type { ModeratorQuestionResponse, ProposedTagBrief, QuoteResponse, TranscriptSegmentResponse } from "../utils/types";
import { formatTimecode, stripSmartQuotes } from "../utils/format";
import { getTagBg } from "../utils/colours";

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

// ── Smart-quote helper ──────────────────────────────────────────────────

function addSmartQuotes(text: string): string {
  return `\u201c${text}\u201d`;
}

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
  const [isEditingText, setIsEditingText] = useState(false);
  const [isTagInputOpen, setIsTagInputOpen] = useState(false);
  const [showFullModQ, setShowFullModQ] = useState(false);

  const domId = quote.dom_id;
  const hasModeratorContext = quote.segment_index > 0;

  // ── Edit handlers ───────────────────────────────────────────────────

  const handleEditCommit = useCallback(
    (newText: string) => {
      setIsEditingText(false);
      // Strip smart quotes — they're decorative, not part of the stored text.
      onEditCommit(domId, stripSmartQuotes(newText));
    },
    [domId, onEditCommit],
  );

  const handleEditCancel = useCallback(() => {
    setIsEditingText(false);
  }, []);

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
      // Keep input open for rapid entry.
      onTagAdd(domId, tagName);
      // Force remount by toggling — TagInput re-mounts and auto-focuses.
      setIsTagInputOpen(false);
      requestAnimationFrame(() => setIsTagInputOpen(true));
    },
    [domId, onTagAdd],
  );

  const handleTagCancel = useCallback(() => {
    setIsTagInputOpen(false);
  }, []);

  // ── Visibility ──────────────────────────────────────────────────────

  // Hidden quotes are not rendered (the parent handles the hide animation).
  if (isHidden) return null;

  // ── Derived state ───────────────────────────────────────────────────

  const transcriptHref = `sessions/transcript_${sessionId}.html#t-${Math.floor(quote.start_timecode)}`;

  // AI sentiment badges: show only if not deleted.
  const visibleSentiment =
    quote.sentiment && !deletedBadges.includes(quote.sentiment)
      ? quote.sentiment
      : null;

  const hasDeletedBadges = deletedBadges.length > 0;

  // Existing tag names for exclusion in TagInput.
  const existingTagNames = userTags.map((t) => t.name);

  const timecodeStr = formatTimecode(quote.start_timecode);

  return (
    <blockquote
      id={domId}
      data-timecode={timecodeStr}
      data-participant={quote.participant_id}
      className={`quote-card${isStarred ? " starred" : ""}`}
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
          {hasModeratorContext && !isQuestionOpen && (
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
          {hasModeratorContext && !isQuestionOpen && (
            <span
              className="quote-hover-zone"
              onMouseEnter={() => onQuoteHoverEnter(domId)}
              onMouseLeave={() => onQuoteHoverLeave(domId)}
              aria-hidden="true"
            />
          )}
          <EditableText
            value={addSmartQuotes(displayText)}
            originalValue={addSmartQuotes(quote.text)}
            isEditing={isEditingText}
            committed={isEdited}
            onCommit={handleEditCommit}
            onCancel={handleEditCancel}
            trigger="external"
            className="quote-text"
            committedClassName="edited"
            data-testid={`bn-quote-${domId}-text`}
            data-edit-key={`${domId}:text`}
          />
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
        className="edit-pencil"
        aria-label="Edit this quote"
        onClick={() => setIsEditingText(!isEditingText)}
        data-testid={`bn-quote-${domId}-edit`}
      >
        &#9998;
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
