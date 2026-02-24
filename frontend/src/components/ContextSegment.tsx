/**
 * ContextSegment — a muted transcript segment shown above or below
 * a quote card to provide surrounding context.
 *
 * Uses the same .quote-row flex layout as QuoteCard for horizontal
 * grid alignment (timecode column + text column).
 */

import { PersonBadge } from "./PersonBadge";
import { formatTimecode } from "../utils/format";

interface ContextSegmentProps {
  speakerCode: string;
  isModerator: boolean;
  startTime: number;
  text: string;
  "data-testid"?: string;
}

export function ContextSegment({
  speakerCode,
  isModerator,
  startTime,
  text,
  "data-testid": testId,
}: ContextSegmentProps) {
  return (
    <div className="context-segment" data-testid={testId}>
      <div className="quote-row">
        <span className="timecode">[{formatTimecode(startTime)}]</span>
        <span className="context-text">
          <span className="context-speaker">
            <PersonBadge
              code={speakerCode}
              role={isModerator ? "moderator" : "participant"}
            />
          </span>
          {text}
        </span>
      </div>
    </div>
  );
}
