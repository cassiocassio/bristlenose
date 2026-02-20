/**
 * ThresholdReviewModal — confidence-aware review dialog for AutoCode proposals.
 *
 * Replaces AutoCodeReportModal with:
 * - Confidence histogram (unit-square or continuous bars)
 * - Dual threshold slider (lower/upper)
 * - Three zone lists (accepted / tentative / excluded)
 * - Bulk apply: accept above upper, deny below lower, leave middle as pending
 */

import { useState, useEffect, useCallback, useMemo } from "react";
import { createPortal } from "react-dom";
import {
  getAutoCodeProposals,
  acceptAllProposals,
  acceptProposal,
  denyAllProposals,
  denyProposal,
} from "../utils/api";
import type { ProposedTagResponse } from "../utils/types";
import { ConfidenceHistogram } from "./ConfidenceHistogram";
import { DualThresholdSlider } from "./DualThresholdSlider";
import { ProposalZoneList } from "./ProposalZoneList";

const DEFAULT_LOWER = 0.30;
const DEFAULT_UPPER = 0.70;

interface ThresholdReviewModalProps {
  frameworkId: string;
  frameworkTitle: string;
  onClose: () => void;
  onApply: () => void;
}

export function ThresholdReviewModal({
  frameworkId,
  frameworkTitle,
  onClose,
  onApply,
}: ThresholdReviewModalProps) {
  const [allProposals, setAllProposals] = useState<ProposedTagResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [applying, setApplying] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Proposals that have been individually acted on (removed from zone lists)
  const [removed, setRemoved] = useState<Set<number>>(new Set());
  const [removing, setRemoving] = useState<Set<number>>(new Set());

  // Slider state
  const [lower, setLower] = useState(DEFAULT_LOWER);
  const [upper, setUpper] = useState(DEFAULT_UPPER);

  // Track total counts for subtitle
  const [totalCount, setTotalCount] = useState(0);
  const [acceptedCount, setAcceptedCount] = useState(0);
  const [deniedCount, setDeniedCount] = useState(0);

  // Fetch all proposals on mount (min_confidence=0 to get everything)
  useEffect(() => {
    getAutoCodeProposals(frameworkId, 0)
      .then((resp) => {
        const pending = resp.proposals.filter((p) => p.status === "pending");
        const accepted = resp.proposals.filter((p) => p.status === "accepted").length;
        const denied = resp.proposals.filter((p) => p.status === "denied").length;
        setAllProposals(pending);
        setTotalCount(resp.total);
        setAcceptedCount(accepted);
        setDeniedCount(denied);
        setLoading(false);
      })
      .catch((err) => {
        console.error("Fetch proposals failed:", err);
        setError("Failed to load proposals");
        setLoading(false);
      });
  }, [frameworkId]);

  // Proposals that are still pending (not individually removed)
  const pendingProposals = useMemo(
    () => allProposals.filter((p) => !removed.has(p.id)),
    [allProposals, removed],
  );

  // The histogram always shows the initial pending set (fixed reference)
  const histogramProposals = allProposals;

  // Zone assignments based on current thresholds
  const { accepted, tentative, excluded } = useMemo(() => {
    const acc: ProposedTagResponse[] = [];
    const tent: ProposedTagResponse[] = [];
    const excl: ProposedTagResponse[] = [];
    for (const p of pendingProposals) {
      if (p.confidence >= upper) acc.push(p);
      else if (p.confidence < lower) excl.push(p);
      else tent.push(p);
    }
    return { accepted: acc, tentative: tent, excluded: excl };
  }, [pendingProposals, lower, upper]);

  // Per-row accept — calls API immediately
  const handleAccept = useCallback((proposalId: number) => {
    setRemoving((prev) => new Set(prev).add(proposalId));
    acceptProposal(proposalId).catch((err) =>
      console.error("Accept proposal failed:", err),
    );
    setTimeout(() => {
      setRemoved((prev) => new Set(prev).add(proposalId));
      setRemoving((prev) => {
        const next = new Set(prev);
        next.delete(proposalId);
        return next;
      });
      setAcceptedCount((prev) => prev + 1);
    }, 200);
  }, []);

  // Per-row deny — calls API immediately
  const handleDeny = useCallback((proposalId: number) => {
    setRemoving((prev) => new Set(prev).add(proposalId));
    denyProposal(proposalId).catch((err) =>
      console.error("Deny proposal failed:", err),
    );
    setTimeout(() => {
      setRemoved((prev) => new Set(prev).add(proposalId));
      setRemoving((prev) => {
        const next = new Set(prev);
        next.delete(proposalId);
        return next;
      });
      setDeniedCount((prev) => prev + 1);
    }, 200);
  }, []);

  // Bulk apply: accept above upper, deny below lower
  const handleApply = useCallback(async () => {
    setApplying(true);
    setError(null);
    try {
      await acceptAllProposals(frameworkId, upper);
      await denyAllProposals(frameworkId, lower);
      onApply();
    } catch (err) {
      console.error("Apply thresholds failed:", err);
      setError("Apply failed — your per-row decisions are saved. Try again.");
      setApplying(false);
    }
  }, [frameworkId, lower, upper, onApply]);

  const pendingCount = pendingProposals.length;
  const hasProposals = pendingCount > 0 || acceptedCount > 0 || deniedCount > 0;

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
              &#x2726; AutoCode Review &mdash; {frameworkTitle}
            </div>
            <div className="codebook-modal-subtitle" data-testid="bn-threshold-subtitle">
              {pendingCount} of {totalCount} proposals remaining
              {(acceptedCount > 0 || deniedCount > 0) && (
                <> ({acceptedCount > 0 ? `${acceptedCount} accepted` : ""}
                {acceptedCount > 0 && deniedCount > 0 ? ", " : ""}
                {deniedCount > 0 ? `${deniedCount} excluded` : ""})</>
              )}
            </div>
            <p className="threshold-instruction">
              Drag the thresholds to control how many auto-tags are applied as tentative or accepted.
            </p>
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
          ) : !hasProposals ? (
            <p style={{ color: "var(--bn-colour-muted)" }}>No proposals to review.</p>
          ) : (
            <>
              {/* Histogram */}
              <ConfidenceHistogram
                proposals={histogramProposals}
                lower={lower}
                upper={upper}
              />

              {/* Dual slider */}
              <DualThresholdSlider
                lower={lower}
                upper={upper}
                onLowerChange={setLower}
                onUpperChange={setUpper}
              />

              {/* Zone counters */}
              <div className="threshold-zone-counters">
                <span className="threshold-zone-counter threshold-zone-counter--exclude">
                  Exclude{" "}
                  <span className="threshold-zone-counter-count">
                    {excluded.filter((p) => !removing.has(p.id)).length}
                  </span>
                </span>
                <span className="threshold-zone-counter threshold-zone-counter--tentative">
                  Tentative{" "}
                  <span className="threshold-zone-counter-count">
                    {tentative.filter((p) => !removing.has(p.id)).length}
                  </span>
                </span>
                <span className="threshold-zone-counter threshold-zone-counter--accept">
                  Accept{" "}
                  <span className="threshold-zone-counter-count">
                    {accepted.filter((p) => !removing.has(p.id)).length}
                  </span>
                </span>
              </div>

              {/* Zone lists */}
              <ProposalZoneList
                zone="accepted"
                proposals={accepted}
                removing={removing}
                onDeny={handleDeny}
              />
              <ProposalZoneList
                zone="tentative"
                proposals={tentative}
                defaultExpanded={true}
                removing={removing}
                onAccept={handleAccept}
                onDeny={handleDeny}
              />
              <ProposalZoneList
                zone="excluded"
                proposals={excluded}
                removing={removing}
                onAccept={handleAccept}
              />
            </>
          )}

          {error && (
            <p style={{ color: "var(--bn-colour-danger)", marginTop: "0.5rem" }}>
              {error}
            </p>
          )}
        </div>

        {/* Footer */}
        <div className="threshold-footer">
          <button
            className="bn-btn"
            onClick={onClose}
            data-testid="bn-threshold-close"
          >
            Close
          </button>
          <button
            className="bn-btn bn-btn-primary"
            onClick={handleApply}
            disabled={applying || pendingCount === 0}
            data-testid="bn-threshold-apply"
          >
            {applying ? "Applying…" : "Apply thresholds"}
          </button>
        </div>
      </div>
    </div>
  );

  return createPortal(modal, document.body);
}
