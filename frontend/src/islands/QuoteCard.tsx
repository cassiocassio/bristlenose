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
  EditableText,
  PersonBadge,
  TagInput,
  TimecodeLink,
  Toggle,
} from "../components";
import type { ProposedTagBrief, QuoteResponse } from "../utils/types";
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

  onToggleStar: (domId: string, newState: boolean) => void;
  onToggleHide: (domId: string, newState: boolean) => void;
  onEditCommit: (domId: string, newText: string) => void;
  onTagAdd: (domId: string, tagName: string) => void;
  onTagRemove: (domId: string, tagName: string) => void;
  onBadgeDelete: (domId: string, sentiment: string) => void;
  onBadgeRestore: (domId: string) => void;
  onProposedAccept: (proposalId: number, tagName: string) => void;
  onProposedDeny: (proposalId: number) => void;
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
}: QuoteCardProps) {
  const [isEditingText, setIsEditingText] = useState(false);
  const [isTagInputOpen, setIsTagInputOpen] = useState(false);

  const domId = quote.dom_id;

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
      {quote.researcher_context && (
        <span className="context">[{quote.researcher_context}]</span>
      )}
      <div className="quote-row">
        {hasMedia ? (
          <TimecodeLink
            seconds={quote.start_timecode}
            endSeconds={quote.end_timecode}
            participantId={quote.participant_id}
            data-testid={`bn-quote-${domId}-timecode`}
          />
        ) : (
          <span className="timecode">[{timecodeStr}]</span>
        )}
        <div className="quote-body">
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
