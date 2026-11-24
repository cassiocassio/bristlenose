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

import { useState, useEffect, useCallback, useLayoutEffect, useMemo, useRef } from "react";
import { flushSync } from "react-dom";
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
import { outcomeZone, snapLines, storedLinesOf } from "../utils/recut";
import type { Lines } from "../utils/recut";
import { reviewedElsewhere } from "../contexts/QuotesContext";
import { announce } from "../utils/announce";
import { ConfidenceHistogram } from "./ConfidenceHistogram";
import { DualThresholdSlider } from "./DualThresholdSlider";
import { ProposalZoneList } from "./ProposalZoneList";
import { Icon } from "./Icon";
import { RollingNumber } from "./RollingNumber";
import { captureLayout, playLayout } from "../utils/reviewMotion";
import type { Layout } from "../utils/reviewMotion";

const DEFAULT_LOWER = 0.30;
const DEFAULT_UPPER = 0.70;

type Decision = "accepted" | "denied";

/**
 * Where keyboard focus goes when a decided row leaves its zone: the same button on the
 * next row of the zone the researcher was working down (or the row before, or the zone's
 * header), the triage habit (owner, 24 Nov 2026). Null when focus is not in that row.
 */
function focusAfter(root: HTMLElement | null, id: number): HTMLElement | null {
  const row = root?.querySelector(`[data-flip="row-${id}"]`);
  const active = document.activeElement;
  if (!row || !active || !row.contains(active)) return null;
  const zone = row.closest("[data-flip-zone]");
  if (!zone) return null;
  const rows = Array.from(zone.querySelectorAll("tr.report-row"));
  const i = rows.indexOf(row);
  const next = rows[i + 1] ?? rows[i - 1];
  const kind = active.classList.contains("threshold-action-accept") ? "accept" : "deny";
  return (
    next?.querySelector<HTMLElement>(`.threshold-action-${kind}`)
    ?? next?.querySelector<HTMLElement>(".threshold-action-btn")
    ?? zone.querySelector<HTMLElement>("[data-flip-landing]")
  );
}

interface ThresholdReviewModalProps {
  open: boolean;
  frameworkId: string;
  frameworkTitle: string;
  /** `changed`: a per-row decision was saved (or may have been) in this opening, so the
   *  page's tags are stale and the caller says so, as after Apply (D42). */
  onClose: (changed: boolean) => void;
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

  // Rows whose decision is on its way to the server: dimmed in place, their buttons at
  // rest, until the answer moves them (or leaves them where they were).
  const [removing, setRemoving] = useState<Set<number>>(new Set());
  // The same set as a ref, read synchronously: a second key press on a row still
  // deciding is ignored, never sent (the CSS rest stops only the mouse).
  const deciding = useRef(new Set<number>());
  // The last decision that landed, for the screen-reader line (see the effect below).
  const [landed, setLanded] = useState<{ zone: "accepted" | "excluded"; n: number } | null>(null);

  // Slider state, and the lines the run was last cut at (null: never cut).
  const [lower, setLower] = useState(DEFAULT_LOWER);
  const [upper, setUpper] = useState(DEFAULT_UPPER);
  const [stored, setStored] = useState<Lines | null>(null);

  const [totalCount, setTotalCount] = useState(0);

  // Off: each quote is one line, cut to fit. On: every quote is drawn whole, which is
  // more scrolling and easier to judge (owner, 24 Nov 2026). Kept across openings.
  const [wordWrap, setWordWrap] = useState(false);

  // A row moving to where a decision put it glides there, and the rows around it make
  // room (utils/reviewMotion.ts): the layout is measured just before the state that
  // moves it is set, and played in the same task, in the commit `flushSync` forces, so
  // nothing (a scroll, another commit) can come between the two.
  const bodyRef = useRef<HTMLDivElement>(null);
  const flip = useRef<Layout | null>(null);
  useLayoutEffect(() => {
    const from = flip.current;
    if (!from) return;
    flip.current = null;
    playLayout(bodyRef.current, from);
  });

  // Moves each time the modal opens (see `review`).
  const opening = useRef(0);
  // A row call landed in this opening, or is still in flight: Close says so (D42).
  const changed = useRef(false);
  const inFlight = useRef(0);

  // Fetch the whole run (min_confidence=0) and the lines it was cut at, together, so
  // the counters never show a cut against the wrong lines.
  useEffect(() => {
    if (!open) return;
    opening.current += 1;
    const mine = opening.current;
    changed.current = false;
    inFlight.current = 0;
    deciding.current = new Set();
    setLanded(null);
    setLoading(true);
    setProposals([]);
    setLoaded([]);
    setRemoving(new Set());
    setLower(DEFAULT_LOWER);
    setUpper(DEFAULT_UPPER);
    setStored(null);
    setError(null);
    setApplying(false);
    // The counters show Apply's outcome against the stored lines, so the run is not
    // drawn without them: a status read that fails, or passes its time limit
    // (`getAutoCodeStatus` is bounded), says the review could not load, and Apply
    // stays off (D43).
    Promise.all([getAutoCodeProposals(frameworkId, 0), getAutoCodeStatus(frameworkId)])
      .then(([resp, job]) => {
        if (opening.current !== mine) return;
        // Seed the sliders from the cutoffs actually applied, so the dialog never
        // draws lines where they weren't. Snapped: an earlier build stored drifted
        // values (0.30000000000000004) and reopening on one would keep sending it.
        // A job with one line stored is cut at it and the default for the other, as
        // the server reads it (`stored_lines`).
        const lines = storedLinesOf(job, { lower: DEFAULT_LOWER, upper: DEFAULT_UPPER });
        if (lines) {
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
    const lines = snapLines(lower, upper);
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

  // Said once per landed decision, for a screen reader: the motion and the rolling counts
  // are the sighted confirmation. Never a live region on the counters themselves, which a
  // slider drag would flood.
  const announced = useRef(0);
  useEffect(() => {
    if (!landed || landed.n === announced.current) return;
    announced.current = landed.n;
    const tally = t("autocode.review.tally", {
      excludedLabel: t("autocode.review.zoneExcluded"),
      tentativeLabel: t("autocode.review.zoneTentative"),
      acceptedLabel: t("autocode.review.zoneAccepted"),
      excluded: excluded.length,
      tentative: tentative.length,
      accepted: accepted.length,
    }).replace(/<\/?[a-z]+>/g, "");
    announce(t("autocode.review.landed", {
      zone: t(landed.zone === "accepted" ? "autocode.review.zoneAccepted" : "autocode.review.zoneExcluded"),
      tally,
    }));
  }, [landed, accepted.length, tentative.length, excluded.length, t]);

  // Per-row accept and deny call the API at once. The row dims where it is, and moves
  // when the server answers, so the motion means "saved" (owner, 24 Nov 2026): it glides
  // to where the decision put it, pinned as the researcher's. A row already decided (an
  // accepted or excluded one, D39) sends the explicit override, naming the status it was
  // shown in (D34, D44); a pending one does not. One that fails says so and undims where
  // it was (R5); one that is gone (404) leaves. One the server says was decided already
  // (any 409: here meanwhile, or differently since the dialog drew it) is read again from
  // the server and drawn as it is there (D44), quietly when it went the way the click
  // asked, saying so otherwise (N33).
  //
  // `opening` moves each time the modal opens and re-reads the run, so an answer from an
  // earlier opening still says so but changes no row.
  const review = useCallback((before: ProposedTagResponse, decision: Decision) => {
    if (isExportMode()) return; // no server in an exported report
    const id = before.id;
    if (deciding.current.has(id)) return;
    deciding.current.add(id);
    const mine = opening.current;
    inFlight.current += 1;
    setRemoving((prev) => new Set(prev).add(id));

    // Draw the answer: measure, change the run and undim the row in one forced commit
    // (the layout effect plays the motion inside it), then hand focus on if it was lost.
    const land = (next: (prev: ProposedTagResponse[]) => ProposedTagResponse[],
      zone?: "accepted" | "excluded") => {
      if (opening.current !== mine) return;
      deciding.current.delete(id);
      const after = focusAfter(bodyRef.current, id);
      flip.current = captureLayout(bodyRef.current, [`row-${id}`]);
      flushSync(() => {
        setProposals(next);
        setRemoving((prev) => { const n = new Set(prev); n.delete(id); return n; });
        if (zone) setLanded((prev) => ({ zone, n: (prev?.n ?? 0) + 1 }));
      });
      const active = document.activeElement;
      if (after?.isConnected && (!active || active === document.body)) {
        after.focus({ preventScroll: true });
      }
    };
    const zoneOf = (status: string) =>
      (status === "accepted" ? "accepted" : status === "denied" ? "excluded" : undefined);

    const call = decision === "accepted" ? acceptProposal : denyProposal;
    call(id, before.status === "pending" ? undefined : before.status).then(
      () => {
        if (opening.current !== mine) return;
        inFlight.current -= 1;
        changed.current = true;
        land((prev) => prev.map((p) => (p.id === id
          ? { ...p, status: decision, decided_by: "researcher" as const } : p)),
          decision === "accepted" ? "accepted" : "excluded");
      },
      (err: ApiError) => {
        console.error("Review proposal failed:", err);
        // Said even when the dialog has since been closed and opened again: the decision
        // did not save, whichever opening is showing.
        const conflict = err?.reason?.startsWith("proposal_");
        if (!conflict || err.reason !== `proposal_${decision}`) toastSaveFailed(err);
        if (opening.current !== mine) return;
        inFlight.current -= 1;
        if (conflict) {
          changed.current = true;
          getAutoCodeProposals(frameworkId, 0).then(
            (resp) => {
              const fresh = resp.proposals.find((p) => p.id === id);
              land((prev) => (fresh
                ? prev.map((p) => (p.id === id ? fresh : p))
                : prev.filter((p) => p.id !== id)), fresh ? zoneOf(fresh.status) : undefined);
            },
            (e) => {
              console.error("Re-read proposals failed:", e);
              land((prev) => prev.map((p) => (p.id === id ? before : p)));
            },
          );
          return;
        }
        land(reviewedElsewhere(err)
          ? (prev) => prev.filter((p) => p.id !== id)
          : (prev) => prev.map((p) => (p.id === id ? before : p)));
      },
    );
  }, [frameworkId]);

  const close = useCallback(
    () => onClose(changed.current || inFlight.current > 0),
    [onClose],
  );

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
  // Apply waits until it would change something: a line moved from where the run was
  // cut (D26), or a pending proposal the lines decide (one whose quote came back,
  // D41). A run never cut has no stored lines: its first Apply is a plain cut,
  // offered while anything is pending, as it always was.
  const linesMoved = stored
    ? snapToStep(lower) !== stored.lower || snapToStep(upper) !== stored.upper
      || [...accepted, ...excluded].some((p) => p.status === "pending")
    : pendingCount > 0;

  return (
    // The header draws its own × in the shell (no crash boundary here), so the
    // shared one is off.
    <Dialog
      open={open}
      onClose={close}
      className="codebook-modal"
      testId="bn-threshold-overlay"
      labelledBy="bn-threshold-title"
      closeButton={false}
    >
        {/* Header */}
        <div className="codebook-modal-header">
          <div>
            <div className="codebook-modal-title" id="bn-threshold-title">
              {t("autocode.review.title", { codebook: frameworkTitle })}
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
            onClick={close}
            aria-label={t("autocode.close")}
          >
            <Icon name="close" decorative />
          </button>
        </div>

        {/* Body */}
        {/* No padding at the top: a zone header sticks to the very top of the scroll (the
            histogram's own room sits inside it), so no row shows above a stuck header. */}
        <div className="codebook-modal-body threshold-body" ref={bodyRef}>
          {loading ? (
            <p style={{ color: "var(--bn-colour-muted)" }}>{t("autocode.loading")}</p>
          ) : !hasProposals ? (
            <p style={{ color: "var(--bn-colour-muted)" }}>{t("autocode.empty")}</p>
          ) : (
            <>
              {/* The Levels control: the histogram is its box, the lines its pointers. */}
              <DualThresholdSlider
                lower={lower}
                upper={upper}
                onLowerChange={setLower}
                onUpperChange={setUpper}
              >
                <ConfidenceHistogram proposals={loaded} lower={lower} upper={upper} />
              </DualThresholdSlider>

              {/* Zone counters */}
              <div className="threshold-zone-counters">
                <span className="threshold-zone-counter threshold-zone-counter--exclude">
                  {t("autocode.review.zoneExclude")}{" "}
                  <span className="threshold-zone-counter-count">
                    <RollingNumber value={excluded.length} />
                  </span>
                </span>
                <span className="threshold-zone-counter threshold-zone-counter--tentative">
                  {t("autocode.review.zoneTentative")}{" "}
                  <span className="threshold-zone-counter-count">
                    <RollingNumber value={tentative.length} />
                  </span>
                </span>
                <span className="threshold-zone-counter threshold-zone-counter--accept">
                  {t("autocode.review.zoneAccept")}{" "}
                  <span className="threshold-zone-counter-count">
                    <RollingNumber value={accepted.length} />
                  </span>
                </span>
              </div>

              {/* Zone lists */}
              <ProposalZoneList
                zone="accepted"
                proposals={accepted}
                wordWrap={wordWrap}
                removing={removing}
                onDeny={handleDeny}
              />
              <ProposalZoneList
                zone="tentative"
                proposals={tentative}
                wordWrap={wordWrap}
                defaultExpanded={true}
                removing={removing}
                onAccept={handleAccept}
                onDeny={handleDeny}
              />
              <ProposalZoneList
                zone="excluded"
                proposals={excluded}
                wordWrap={wordWrap}
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
          <label className="threshold-wrap">
            <input
              type="checkbox"
              checked={wordWrap}
              onChange={(e) => setWordWrap(e.target.checked)}
              data-testid="bn-threshold-wrap"
            />
            {t("autocode.review.wordWrap")}
          </label>
          <button
            className="bn-btn"
            onClick={close}
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
