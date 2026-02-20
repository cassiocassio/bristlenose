/**
 * AutoCodeReportModal — triage table for reviewing AutoCode proposals.
 *
 * Fetches proposals on mount, groups by session, allows per-row deny,
 * and offers bulk accept or "tag tentatively" (close without action).
 */

import { useState, useEffect, useCallback, useMemo } from "react";
import { createPortal } from "react-dom";
import {
  getAutoCodeProposals,
  acceptAllProposals,
  denyProposal,
} from "../utils/api";
import type { ProposedTagResponse } from "../utils/types";
import { getTagBg } from "../utils/colours";

interface AutoCodeReportModalProps {
  frameworkId: string;
  frameworkTitle: string;
  onClose: () => void;
  onAcceptAll: () => void;
  onTagTentatively: () => void;
}

function formatTimecode(seconds: number): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.floor(seconds % 60);
  if (h > 0) return `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
  return `${m}:${String(s).padStart(2, "0")}`;
}

export function AutoCodeReportModal({
  frameworkId,
  frameworkTitle,
  onClose,
  onAcceptAll,
  onTagTentatively,
}: AutoCodeReportModalProps) {
  const [proposals, setProposals] = useState<ProposedTagResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [removing, setRemoving] = useState<Set<number>>(new Set());

  useEffect(() => {
    getAutoCodeProposals(frameworkId)
      .then((resp) => {
        setProposals(resp.proposals.filter((p) => p.status === "pending"));
        setLoading(false);
      })
      .catch((err) => {
        console.error("Fetch proposals failed:", err);
        setLoading(false);
      });
  }, [frameworkId]);

  // Group proposals by session. Keep removing items visible
  // so the CSS animation plays before they're removed from state.
  const groupedBySession = useMemo(() => {
    const map = new Map<string, ProposedTagResponse[]>();
    for (const p of proposals) {
      if (!map.has(p.session_id)) map.set(p.session_id, []);
      map.get(p.session_id)!.push(p);
    }
    return map;
  }, [proposals]);

  const visibleCount = proposals.filter((p) => !removing.has(p.id)).length;
  const sessionCount = groupedBySession.size;

  const handleDeny = useCallback((proposalId: number) => {
    setRemoving((prev) => new Set(prev).add(proposalId));
    denyProposal(proposalId).catch((err) =>
      console.error("Deny proposal failed:", err),
    );
    // Remove from proposals after animation.
    setTimeout(() => {
      setProposals((prev) => prev.filter((p) => p.id !== proposalId));
      setRemoving((prev) => {
        const next = new Set(prev);
        next.delete(proposalId);
        return next;
      });
    }, 200);
  }, []);

  const handleAcceptAll = useCallback(() => {
    acceptAllProposals(frameworkId)
      .then(() => onAcceptAll())
      .catch((err) => console.error("Accept all failed:", err));
  }, [frameworkId, onAcceptAll]);

  const modal = (
    // eslint-disable-next-line jsx-a11y/click-events-have-key-events, jsx-a11y/no-static-element-interactions
    <div className="codebook-modal-overlay" onClick={onClose}>
      {/* eslint-disable-next-line jsx-a11y/click-events-have-key-events, jsx-a11y/no-static-element-interactions */}
      <div
        className="codebook-modal"
        style={{ maxWidth: "56rem" }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="codebook-modal-header">
          <div>
            <div className="codebook-modal-title">
              &#x2726; AutoCode Report &mdash; {frameworkTitle}
            </div>
            <div className="codebook-modal-subtitle" data-testid="bn-report-subtitle">
              {visibleCount} tag{visibleCount !== 1 ? "s" : ""} proposed across{" "}
              {sessionCount} session{sessionCount !== 1 ? "s" : ""}
            </div>
          </div>
          <button
            className="codebook-modal-close"
            onClick={onClose}
            aria-label="Close"
          >
            &times;
          </button>
        </div>

        {/* Body */}
        <div className="codebook-modal-body" style={{ padding: "1.5rem" }}>
          {loading ? (
            <p style={{ color: "var(--bn-colour-muted)" }}>Loading proposals…</p>
          ) : visibleCount === 0 ? (
            <p style={{ color: "var(--bn-colour-muted)" }}>No proposals to review.</p>
          ) : (
            <table className="report-table" data-testid="bn-report-table">
              <tbody>
                {Array.from(groupedBySession.entries()).map(([sessionId, items]) => (
                  <SessionRows
                    key={sessionId}
                    sessionId={sessionId}
                    items={items}
                    removing={removing}
                    onDeny={handleDeny}
                  />
                ))}
              </tbody>
            </table>
          )}
        </div>

        {/* Footer */}
        <div className="codebook-modal-footer" style={{
          padding: "1rem 1.5rem",
          borderTop: "1px solid var(--bn-colour-border)",
          display: "flex",
          justifyContent: "flex-end",
          gap: "0.5rem",
        }}>
          <button className="bn-btn" onClick={onClose} data-testid="bn-report-close">
            Close
          </button>
          <button
            className="bn-btn"
            onClick={handleAcceptAll}
            data-testid="bn-report-accept-all"
          >
            Accept all
          </button>
          <button
            className="bn-btn bn-btn-primary"
            onClick={onTagTentatively}
            data-testid="bn-report-tag-tentatively"
          >
            Tag tentatively
          </button>
        </div>
      </div>
    </div>
  );

  return createPortal(modal, document.body);
}

// ── Session row group ─────────────────────────────────────────────────

interface SessionRowsProps {
  sessionId: string;
  items: ProposedTagResponse[];
  removing: Set<number>;
  onDeny: (id: number) => void;
}

function SessionRows({ sessionId, items, removing, onDeny }: SessionRowsProps) {
  return (
    <>
      <tr>
        <td colSpan={5} className="report-session-header">
          {sessionId}
        </td>
      </tr>
      {items.map((p) => (
        <tr
          key={p.id}
          className={`report-row${removing.has(p.id) ? " removing" : ""}`}
          data-testid={`bn-report-row-${p.id}`}
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
          <td className="report-deny">
            <button
              className="report-deny-btn"
              onClick={() => onDeny(p.id)}
              title="Deny"
              data-testid={`bn-report-deny-${p.id}`}
            >
              &#x2298;
            </button>
          </td>
        </tr>
      ))}
    </>
  );
}
