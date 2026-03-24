/**
 * AutoCodeReportModal — triage table for reviewing AutoCode proposals.
 *
 * Fetches proposals when opened, groups by session, allows per-row deny,
 * and offers bulk accept or "tag tentatively" (close without action).
 */

import { useState, useEffect, useCallback, useMemo } from "react";
import { createPortal } from "react-dom";
import { useTranslation } from "react-i18next";
import { useInert } from "../hooks/useInert";
import {
  getAutoCodeProposals,
  acceptAllProposals,
  denyProposal,
} from "../utils/api";
import type { ProposedTagResponse } from "../utils/types";
import { getTagBg } from "../utils/colours";

interface AutoCodeReportModalProps {
  open: boolean;
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
  open,
  frameworkId,
  frameworkTitle,
  onClose,
  onAcceptAll,
  onTagTentatively,
}: AutoCodeReportModalProps) {
  useInert(open);
  const { t } = useTranslation();
  const [proposals, setProposals] = useState<ProposedTagResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [removing, setRemoving] = useState<Set<number>>(new Set());

  // Fetch proposals when opened (or frameworkId changes while open).
  useEffect(() => {
    if (!open) return;
    setLoading(true);
    setProposals([]);
    setRemoving(new Set());
    getAutoCodeProposals(frameworkId)
      .then((resp) => {
        setProposals(resp.proposals.filter((p) => p.status === "pending"));
        setLoading(false);
      })
      .catch((err) => {
        console.error("Fetch proposals failed:", err);
        setLoading(false);
      });
  }, [open, frameworkId]);

  // Escape key closes modal.
  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        e.stopPropagation();
        onClose();
      }
    };
    document.addEventListener("keydown", handler, true);
    return () => document.removeEventListener("keydown", handler, true);
  }, [open, onClose]);

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
    <div
      className={`codebook-modal-overlay${open ? " visible" : ""}`}
      onClick={onClose}
      aria-hidden={!open}
    >
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
              &#x2726; {t("autocode.report.title")} &mdash; {frameworkTitle}
            </div>
            <div className="codebook-modal-subtitle" data-testid="bn-report-subtitle">
              {t("autocode.report.subtitle", { count: visibleCount, sessions: sessionCount })}
            </div>
          </div>
          <button
            className="codebook-modal-close"
            onClick={onClose}
            aria-label={t("autocode.close")}
          >
            &times;
          </button>
        </div>

        {/* Body */}
        <div className="codebook-modal-body" style={{ padding: "1.5rem" }}>
          {loading ? (
            <p style={{ color: "var(--bn-colour-muted)" }}>{t("autocode.loading")}</p>
          ) : visibleCount === 0 ? (
            <p style={{ color: "var(--bn-colour-muted)" }}>{t("autocode.empty")}</p>
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
            {t("autocode.report.close")}
          </button>
          <button
            className="bn-btn"
            onClick={handleAcceptAll}
            data-testid="bn-report-accept-all"
          >
            {t("autocode.report.acceptAll")}
          </button>
          <button
            className="bn-btn bn-btn-primary"
            onClick={onTagTentatively}
            data-testid="bn-report-tag-tentatively"
          >
            {t("autocode.report.tagTentatively")}
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
  const { t } = useTranslation();
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
              href={`/report/sessions/${p.session_id}#t-${Math.floor(p.start_timecode)}`}
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
              title={t("autocode.report.deny")}
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
