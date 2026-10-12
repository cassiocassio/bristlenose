/**
 * ContextSegment — a muted transcript segment shown above or below
 * a quote card to provide surrounding context.
 *
 * Uses the same .quote-row flex layout as QuoteCard for horizontal
 * grid alignment (timecode column + text column).
 */

import { useTranslation } from "react-i18next";
import { PersonBadge } from "./PersonBadge";
import { formatTimecode } from "../utils/format";

interface ContextSegmentProps {
  speakerCode: string;
  isModerator: boolean;
  startTime: number;
  text: string;
  /** Nothing usable was heard here: drawn as an annotation, never as words. */
  inaudible?: boolean;
  /** The quote's participant ID — badge is hidden when speaker matches. */
  quoteParticipantId?: string;
  "data-testid"?: string;
}

export function ContextSegment({
  speakerCode,
  isModerator,
  startTime,
  text,
  inaudible = false,
  quoteParticipantId,
  "data-testid": testId,
}: ContextSegmentProps) {
  const { t } = useTranslation();
  const showBadge = !quoteParticipantId || speakerCode !== quoteParticipantId;

  return (
    <div className="context-segment" data-testid={testId}>
      <div className="quote-row">
        <span className="timecode"><span className="timecode-bracket">[</span>{formatTimecode(startTime)}<span className="timecode-bracket">]</span></span>
        <span className="context-text">
          {showBadge && (
            <span className="context-speaker">
              <PersonBadge
                code={speakerCode}
                role={isModerator ? "moderator" : "participant"}
              />
            </span>
          )}
          {inaudible ? (
            <span className="segment-inaudible">{t("transcript.inaudible")}</span>
          ) : text}
        </span>
      </div>
    </div>
  );
}
