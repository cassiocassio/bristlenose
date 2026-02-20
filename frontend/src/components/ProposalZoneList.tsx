/**
 * ProposalZoneList — collapsible list of proposals for one zone.
 *
 * Groups proposals by session ID with session headers.
 * Each row shows timecode, speaker, quote text, tag badge (with rationale tooltip),
 * confidence score, and zone-specific action buttons.
 */

import { useState, useMemo, useCallback } from "react";
import type { ProposedTagResponse } from "../utils/types";
import { getTagBg } from "../utils/colours";

type Zone = "accepted" | "tentative" | "excluded";

interface ProposalZoneListProps {
  zone: Zone;
  proposals: ProposedTagResponse[];
  defaultExpanded?: boolean;
  onAccept?: (proposalId: number) => void;
  onDeny?: (proposalId: number) => void;
  removing: Set<number>;
}

function formatTimecode(seconds: number): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.floor(seconds % 60);
  if (h > 0) return `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
  return `${m}:${String(s).padStart(2, "0")}`;
}

const ZONE_LABELS: Record<Zone, string> = {
  accepted: "Accepted",
  tentative: "Tentative",
  excluded: "Excluded",
};

export function ProposalZoneList({
  zone,
  proposals,
  defaultExpanded = false,
  onAccept,
  onDeny,
  removing,
}: ProposalZoneListProps) {
  const [isOpen, setIsOpen] = useState(defaultExpanded);

  const visibleCount = proposals.filter((p) => !removing.has(p.id)).length;

  /** Group proposals by session, sorted by confidence desc within each session. */
  const groupedBySession = useMemo(() => {
    const sorted = [...proposals].sort((a, b) => b.confidence - a.confidence);
    const map = new Map<string, ProposedTagResponse[]>();
    for (const p of sorted) {
      if (!map.has(p.session_id)) map.set(p.session_id, []);
      map.get(p.session_id)!.push(p);
    }
    return map;
  }, [proposals]);

  const toggleOpen = useCallback(() => setIsOpen((prev) => !prev), []);

  if (visibleCount === 0 && !isOpen) return null;

  return (
    <div className="threshold-zone-list" data-testid={`bn-zone-${zone}`}>
      {/* eslint-disable-next-line jsx-a11y/click-events-have-key-events, jsx-a11y/no-static-element-interactions */}
      <div className="threshold-zone-list-header" onClick={toggleOpen}>
        <span className={`threshold-zone-list-chevron${isOpen ? " threshold-zone-list-chevron--open" : ""}`}>
          &#x25B6;
        </span>
        <span>{ZONE_LABELS[zone]}</span>
        <span className="threshold-zone-list-count">({visibleCount})</span>
      </div>

      <div className={`threshold-zone-list-body${isOpen ? " threshold-zone-list-body--open" : ""}`}>
        <table className="threshold-proposal-table">
          <tbody>
            {Array.from(groupedBySession.entries()).map(([sessionId, items]) => (
              <SessionRows
                key={sessionId}
                sessionId={sessionId}
                items={items}
                zone={zone}
                removing={removing}
                onAccept={onAccept}
                onDeny={onDeny}
              />
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ── Session row group ─────────────────────────────────────────────────

interface SessionRowsProps {
  sessionId: string;
  items: ProposedTagResponse[];
  zone: Zone;
  removing: Set<number>;
  onAccept?: (proposalId: number) => void;
  onDeny?: (proposalId: number) => void;
}

function SessionRows({ sessionId, items, zone, removing, onAccept, onDeny }: SessionRowsProps) {
  // Filter out removed items for display but keep them in DOM briefly for animation
  const visibleItems = items.filter((p) => !removing.has(p.id));
  if (visibleItems.length === 0) return null;

  return (
    <>
      <tr>
        <td colSpan={6} className="report-session-header">
          {sessionId}
        </td>
      </tr>
      {visibleItems.map((p) => (
        <tr
          key={p.id}
          className={`report-row${removing.has(p.id) ? " removing" : ""}`}
          data-testid={`bn-proposal-row-${p.id}`}
        >
          <td className="report-timecode">
            <a
              href={`sessions/transcript_${p.session_id}.html#t-${Math.floor(p.start_timecode)}`}
              target="_blank"
              rel="noreferrer"
            >
              {formatTimecode(p.start_timecode)}
            </a>
          </td>
          <td className="report-speaker">
            <span className="badge">{p.speaker_code}</span>
          </td>
          <td className="report-quote" title={p.quote_text}>
            {p.quote_text}
          </td>
          <td className="report-tag">
            <span
              className="badge has-tooltip"
              style={{ backgroundColor: getTagBg(p.colour_set, p.colour_index) }}
            >
              {p.tag_name}
              <span className="tooltip">{p.rationale}</span>
            </span>
          </td>
          <td className="threshold-confidence">
            {p.confidence.toFixed(2)}
          </td>
          <td className="threshold-actions">
            {/* Accepted zone: only deny (override) */}
            {zone === "accepted" && onDeny && (
              <button
                className="threshold-action-btn threshold-action-deny"
                onClick={() => onDeny(p.id)}
                title="Deny"
              >
                &#x2717;
              </button>
            )}
            {/* Tentative zone: accept + deny */}
            {zone === "tentative" && (
              <>
                {onAccept && (
                  <button
                    className="threshold-action-btn threshold-action-accept"
                    onClick={() => onAccept(p.id)}
                    title="Accept"
                  >
                    &#x2713;
                  </button>
                )}
                {onDeny && (
                  <button
                    className="threshold-action-btn threshold-action-deny"
                    onClick={() => onDeny(p.id)}
                    title="Deny"
                  >
                    &#x2717;
                  </button>
                )}
              </>
            )}
            {/* Excluded zone: only accept (rescue) */}
            {zone === "excluded" && onAccept && (
              <button
                className="threshold-action-btn threshold-action-accept"
                onClick={() => onAccept(p.id)}
                title="Accept"
              >
                &#x2713;
              </button>
            )}
          </td>
        </tr>
      ))}
    </>
  );
}
