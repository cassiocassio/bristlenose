/**
 * ThresholdReviewModal — confidence-aware review dialog for AutoCode proposals.
 *
 * - Confidence histogram (unit-square or continuous bars) over the whole run
 * - Dual threshold slider (lower/upper)
 * - Three zone lists (accepted / tentative / excluded), showing where Apply leaves
 *   each proposal
 * - Apply re-cuts the run at the two lines (landing plan Phase 2: D2, D26, D39)
 *
 * The whole run loads, decided proposals included, so a cut can be moved again and an
 * exclusion taken back (D1). A decision a person made is pinned: the lines never move
 * it, and its row carries a pin (D2). docs/mockups/autocode-review-dialog.html is the
 * approved design.
 */

import { useState, useEffect, useCallback, useMemo, useRef } from "react";
import { useTranslation } from "react-i18next";
import { Dialog } from "./Dialog";
import {
  getAutoCodeStatus,
  getAutoCodeProposals,
  acceptProposal,
  denyProposal,
  recutProposals,
  toastSaveFailed,
} from "../utils/api";
import type { ApiError } from "../utils/api";
import type { ProposedTagResponse } from "../utils/types";
import { isExportMode } from "../utils/exportData";
import { snapToStep } from "../utils/confidenceStep";
import { outcomeZone } from "../utils/recut";
import type { Lines } from "../utils/recut";
import { reviewedElsewhere } from "../contexts/QuotesContext";
import { ConfidenceHistogram } from "./ConfidenceHistogram";
import { DualThresholdSlider } from "./DualThresholdSlider";
import { ProposalZoneList } from "./ProposalZoneList";
import { Icon } from "./Icon";

const DEFAULT_LOWER = 0.30;
const DEFAULT_UPPER = 0.70;

type Decision = "accepted" | "denied";
type Outcome = "landed" | "back" | "gone" | "other";

interface ThresholdReviewModalProps {
  open: boolean;
  frameworkId: string;
  frameworkTitle: string;
  onClose: () => void;
  onApply: () => void;
}

export function ThresholdReviewModal({
  open,
  frameworkId,
  frameworkTitle,
  onClose,
  onApply,
}: ThresholdReviewModalProps) {
  const { t } = useTranslation();
  // The run as it stands on this side: every proposal, with each row's decision as
  // the per-row buttons have changed it.
  const [proposals, setProposals] = useState<ProposedTagResponse[]>([]);
  // The run as it loaded: the histogram's fixed reference for the distribution.
  const [loaded, setLoaded] = useState<ProposedTagResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [applying, setApplying] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Rows sliding out after a per-row action, before they settle where it put them.
  const [removing, setRemoving] = useState<Set<number>>(new Set());

  // Slider state, and the lines the run was last cut at (null: never cut).
  const [lower, setLower] = useState(DEFAULT_LOWER);
  const [upper, setUpper] = useState(DEFAULT_UPPER);
  const [stored, setStored] = useState<Lines | null>(null);

  const [totalCount, setTotalCount] = useState(0);

  // Moves each time the modal opens (see `review`).
  const opening = useRef(0);

  // Fetch the whole run (min_confidence=0) and the lines it was cut at, together, so
  // the counters never show a cut against the wrong lines.
  useEffect(() => {
    if (!open) return;
    opening.current += 1;
    const mine = opening.current;
    setLoading(true);
    setProposals([]);
    setLoaded([]);
    setRemoving(new Set());
    setLower(DEFAULT_LOWER);
    setUpper(DEFAULT_UPPER);
    setStored(null);
    setError(null);
    setApplying(false);
    // The lines failing to load is not a precondition for reviewing: the defaults
    // set above are a usable state, and Apply's re-cut reads the stored lines on the
    // server whatever this side drew.
    const status = getAutoCodeStatus(frameworkId).catch(() => null);
    Promise.all([getAutoCodeProposals(frameworkId, 0), status])
      .then(([resp, job]) => {
        if (opening.current !== mine) return;
        // Seed the sliders from the cutoffs actually applied, so the dialog never
        // draws lines where they weren't. Snapped: an earlier build stored drifted
        // values (0.30000000000000004) and reopening on one would keep sending it.
        // A job with one line stored is cut at it and the default for the other, as
        // the server reads it (`stored_lines`).
        const lo = job?.applied_lower_threshold;
        const hi = job?.applied_upper_threshold;
        if (lo != null || hi != null) {
          const lines = {
            lower: snapToStep(lo ?? DEFAULT_LOWER),
            upper: snapToStep(hi ?? DEFAULT_UPPER),
          };
          setStored(lines);
          setLower(lines.lower);
          setUpper(lines.upper);
        }
        setProposals(resp.proposals);
        setLoaded(resp.proposals);
        setTotalCount(resp.total);
        setLoading(false);
      })
      .catch((err) => {
        if (opening.current !== mine) return;
        console.error("Fetch proposals failed:", err);
        setError(t("autocode.review.loadFailed"));
        setLoading(false);
      });
  }, [open, frameworkId]);

  // Where Apply at the sliders' lines leaves each proposal, over the whole run (D26):
  // what the counters count and the zone lists list.
  const { accepted, tentative, excluded } = useMemo(() => {
    const lines = { lower: snapToStep(lower), upper: snapToStep(upper) };
    const acc: ProposedTagResponse[] = [];
    const tent: ProposedTagResponse[] = [];
    const excl: ProposedTagResponse[] = [];
    for (const p of proposals) {
      const zone = outcomeZone(p, stored, lines);
      if (zone === "accepted") acc.push(p);
      else if (zone === "excluded") excl.push(p);
      else tent.push(p);
    }
    return { accepted: acc, tentative: tent, excluded: excl };
  }, [proposals, stored, lower, upper]);

  // Per-row accept and deny call the API at once; the row slides out and comes back
  // where the decision put it, pinned as the researcher's. A row already decided
  // (an accepted or excluded one, D39) sends the explicit override (D34); a pending
  // one does not, so a row the server says was decided meanwhile is refused as
  // "reviewed elsewhere". One that fails says so and comes back as it was (R5); one
  // decided elsewhere the way the click asked has landed; one decided the other way
  // lands there (N33); one that is gone (404) leaves.
  //
  // `opening` moves each time the modal opens and re-reads the run, so an answer
  // from an earlier opening still says so but changes no row.
  const outcome = useRef(new Map<number, Outcome>());
  const left = useRef(new Set<number>());
  const review = useCallback((before: ProposedTagResponse, decision: Decision) => {
    if (isExportMode()) return; // no server in an exported report
    const mine = opening.current;
    const id = before.id;
    const other: Decision = decision === "accepted" ? "denied" : "accepted";
    const place = (o: Outcome) => {
      if (o === "back") {
        setProposals((prev) => prev.map((p) => (p.id === id ? before : p)));
      } else if (o === "gone") {
        setProposals((prev) => prev.filter((p) => p.id !== id));
      } else {
        // Decided elsewhere ("other") was a person too: while this dialog is open the
        // only other writer of a listed row's decision is a quote card.
        const status = o === "landed" ? decision : other;
        const decided_by = "researcher" as const;
        setProposals((prev) => prev.map((p) => (p.id === id ? { ...p, status, decided_by } : p)));
      }
    };
    outcome.current.delete(id);
    left.current.delete(id);
    setRemoving((prev) => new Set(prev).add(id));
    const settle = (o: Outcome) => {
      if (opening.current !== mine) return;
      outcome.current.set(id, o);
      if (left.current.has(id)) place(o); // else the timer applies it
    };
    const call = decision === "accepted" ? acceptProposal : denyProposal;
    call(id, before.status !== "pending").then(
      () => settle("landed"),
      (err: ApiError) => {
        console.error("Review proposal failed:", err);
        if (err?.reason === `proposal_${decision}`) return settle("landed");
        toastSaveFailed(err);
        const decidedElsewhere = !!err?.reason?.startsWith("proposal_");
        settle(decidedElsewhere ? "other" : reviewedElsewhere(err) ? "gone" : "back");
      },
    );
    setTimeout(() => {
      if (opening.current !== mine) return;
      left.current.add(id);
      setRemoving((prev) => { const n = new Set(prev); n.delete(id); return n; });
      const o = outcome.current.get(id);
      if (o !== "back") place(o ?? "landed");
    }, 200);
  }, []);

  const byId = useMemo(() => new Map(proposals.map((p) => [p.id, p])), [proposals]);

  const handleAccept = useCallback(
    (proposalId: number) => {
      const p = byId.get(proposalId);
      if (p) review(p, "accepted");
    },
    [byId, review],
  );

  const handleDeny = useCallback(
    (proposalId: number) => {
      const p = byId.get(proposalId);
      if (p) review(p, "denied");
    },
    [byId, review],
  );

  // Apply re-cuts the run at the sliders' lines, on the 0.05 grid.
  const handleApply = useCallback(async () => {
    setApplying(true);
    setError(null);
    try {
      await recutProposals(frameworkId, snapToStep(lower), snapToStep(upper));
      onApply();
    } catch (err) {
      console.error("Apply thresholds failed:", err);
      setError(t("autocode.review.applyFailed"));
      setApplying(false);
    }
  }, [frameworkId, lower, upper, onApply]);

  const pendingCount = proposals.filter((p) => p.status === "pending").length;
  const acceptedCount = proposals.filter((p) => p.status === "accepted").length;
  const deniedCount = proposals.filter((p) => p.status === "denied").length;
  const hasProposals = proposals.length > 0;
  // Apply changes nothing with the lines where the run was cut (D26), so it waits for
  // a line to move. A run never cut has no stored lines: its first Apply is a plain
  // cut, offered while anything is pending, as it always was.
  const linesMoved = stored
    ? snapToStep(lower) !== stored.lower || snapToStep(upper) !== stored.upper
    : pendingCount > 0;

  return (
    // The header draws its own × in the shell (no crash boundary here), so the
    // shared one is off.
    <Dialog
      open={open}
      onClose={onClose}
      className="codebook-modal"
      testId="bn-threshold-overlay"
      labelledBy="bn-threshold-title"
      closeButton={false}
    >
        {/* Header */}
        <div className="codebook-modal-header">
          <div>
            <div className="codebook-modal-title" id="bn-threshold-title">
              {t("autocode.review.title")} &mdash; {frameworkTitle}
            </div>
            <div className="codebook-modal-subtitle" data-testid="bn-threshold-subtitle">
              {t("autocode.review.remaining", { pending: pendingCount, total: totalCount })}
              {(acceptedCount > 0 || deniedCount > 0) && (
                <> ({acceptedCount > 0 ? t("autocode.review.accepted", { count: acceptedCount }) : ""}
                {acceptedCount > 0 && deniedCount > 0 ? ", " : ""}
                {deniedCount > 0 ? t("autocode.review.excluded", { count: deniedCount }) : ""})</>
              )}
            </div>
            <p className="threshold-instruction">
              {t("autocode.review.dragInstruction")}
            </p>
          </div>
          <button
            className="codebook-modal-close"
            onClick={onClose}
            aria-label={t("autocode.close")}
          >
            <Icon name="close" decorative />
          </button>
        </div>

        {/* Body */}
        <div className="codebook-modal-body" style={{ padding: "1.5rem" }}>
          {loading ? (
            <p style={{ color: "var(--bn-colour-muted)" }}>{t("autocode.loading")}</p>
          ) : !hasProposals ? (
            <p style={{ color: "var(--bn-colour-muted)" }}>{t("autocode.empty")}</p>
          ) : (
            <>
              {/* Histogram */}
              <ConfidenceHistogram
                proposals={loaded}
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
                  {t("autocode.review.zoneExclude")}{" "}
                  <span className="threshold-zone-counter-count">
                    {excluded.filter((p) => !removing.has(p.id)).length}
                  </span>
                </span>
                <span className="threshold-zone-counter threshold-zone-counter--tentative">
                  {t("autocode.review.zoneTentative")}{" "}
                  <span className="threshold-zone-counter-count">
                    {tentative.filter((p) => !removing.has(p.id)).length}
                  </span>
                </span>
                <span className="threshold-zone-counter threshold-zone-counter--accept">
                  {t("autocode.review.zoneAccept")}{" "}
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
            {t("autocode.close")}
          </button>
          <button
            className="bn-btn bn-btn-primary"
            onClick={handleApply}
            disabled={applying || !linesMoved}
            data-testid="bn-threshold-apply"
          >
            {applying ? t("autocode.review.applying") : t("autocode.review.apply")}
          </button>
        </div>
    </Dialog>
  );
}
