/**
 * ConfidenceHistogram — 20-bin histogram of proposal confidence scores.
 *
 * Two rendering modes:
 * - **Unit-square mode**: each proposal is a coloured square (tag colour),
 *   stacked vertically. Used when the tallest bin fits within the histogram height.
 * - **Continuous bar mode**: solid bars coloured by zone (green/amber/grey).
 *   Fallback for large datasets where unit squares would be too small.
 *
 * `ZoneHistogram` is the same chart drawn small from counts already split by zone, for the
 * tag sidebar's AutoCode overview (docs/design-autocode-landing-plan.md Phase 6, D17, D19):
 * each band stacked excluded, tentative, accepted from the bottom, on a scale the caller holds
 * (it only grows while a run lands), bars only, and the codebook's lines as ticks when
 * there is one pair to draw (during a first run, the lower line and the live accept line).
 */

import { useMemo, useRef, useCallback } from "react";
import type { CSSProperties } from "react";
import { useTranslation } from "react-i18next";
import type { ProposedTagResponse, ZoneBin } from "../utils/types";
import { getTagBg } from "../utils/colours";

const NUM_BINS = 20;
const BIN_WIDTH = 0.05;
const HISTOGRAM_HEIGHT = 120;
const SQUARE_GAP = 1;

interface ConfidenceHistogramProps {
  /** All pending proposals (used to build the histogram — fixed on mount). */
  proposals: ProposedTagResponse[];
  /** Lower threshold (0–1). */
  lower: number;
  /** Upper threshold (0–1). */
  upper: number;
}

/** Assign a proposal to a bin index (0–19). */
export function binIndex(confidence: number): number {
  // Not `confidence / BIN_WIDTH`: 0.7 / 0.05 is 13.999999999999998, which put a
  // proposal sitting exactly on a bin edge one bin low. The epsilon is far below
  // any real confidence's resolution and far above the division's error.
  const idx = Math.floor(confidence * NUM_BINS + 1e-9);
  return Math.max(0, Math.min(idx, NUM_BINS - 1));
}

/** Zone for a bin given thresholds. */
function binZone(binIdx: number, lower: number, upper: number): "grey" | "amber" | "green" {
  const binStart = binIdx * BIN_WIDTH;
  const binEnd = binStart + BIN_WIDTH;
  // Use the midpoint of the bin to determine zone colour
  const mid = (binStart + binEnd) / 2;
  if (mid < lower) return "grey";
  if (mid >= upper) return "green";
  return "amber";
}

export function ConfidenceHistogram({ proposals, lower, upper }: ConfidenceHistogramProps) {
  const { t } = useTranslation();
  const containerRef = useRef<HTMLDivElement>(null);

  /** Build bins: each bin has a count and an array of proposals (for unit-square mode). */
  const bins = useMemo(() => {
    const result: { proposals: ProposedTagResponse[] }[] = Array.from(
      { length: NUM_BINS },
      () => ({ proposals: [] }),
    );
    for (const p of proposals) {
      result[binIndex(p.confidence)].proposals.push(p);
    }
    return result;
  }, [proposals]);

  const maxCount = useMemo(
    () => Math.max(1, ...bins.map((b) => b.proposals.length)),
    [bins],
  );

  /** Decide rendering mode: unit-square vs continuous. */
  const useSquares = useMemo(() => {
    // squareSize = binWidth in pixels ≈ containerWidth / 20
    // In CSS the container is flex with gap:1px, so each bin ≈ (totalWidth - 19) / 20
    // For a typical 600px container, binWidth ≈ 29px → maxStack ≈ 120 / (29+1) = 4
    // We approximate: assume containerWidth ≈ 600px for the decision
    const approxBinWidth = 28;
    const squareSize = approxBinWidth;
    const maxStack = Math.floor(HISTOGRAM_HEIGHT / (squareSize + SQUARE_GAP));
    return maxCount <= maxStack;
  }, [maxCount]);

  /** Render a single bin. */
  const renderBin = useCallback(
    (bin: { proposals: ProposedTagResponse[] }, idx: number) => {
      const zone = binZone(idx, lower, upper);
      const count = bin.proposals.length;

      if (count === 0) {
        return <div key={idx} className="threshold-histogram-bin" />;
      }

      if (useSquares) {
        // Unit-square mode: one square per proposal, tag-coloured
        return (
          <div key={idx} className="threshold-histogram-bin">
            {bin.proposals.map((p) => (
              <div
                key={p.id}
                className="threshold-histogram-square"
                style={{ backgroundColor: getTagBg(p.colour_set, p.colour_index) }}
                title={`${p.tag_name} (${p.confidence.toFixed(2)})`}
              />
            ))}
          </div>
        );
      }

      // Continuous bar mode: zone-coloured
      const heightPct = (count / maxCount) * 100;
      return (
        <div key={idx} className="threshold-histogram-bin">
          <div
            className={`threshold-histogram-bar threshold-histogram-bar--${zone}`}
            style={{ height: `${heightPct}%` }}
            title={t("autocode.proposalCount", { count })}
          />
        </div>
      );
    },
    [lower, upper, maxCount, useSquares, t],
  );

  return (
    <div>
      <div
        ref={containerRef}
        className="threshold-histogram"
        data-testid="bn-threshold-histogram"
        // The tallest stack, so the squares can fit it in the box (threshold-review.css).
        style={{ "--bn-hist-stack": maxCount } as CSSProperties}
      >
        {bins.map((bin, idx) => renderBin(bin, idx))}
      </div>
      <div className="threshold-histogram-axis">
        <span>0.0</span>
        <span>0.2</span>
        <span>0.4</span>
        <span>0.6</span>
        <span>0.8</span>
        <span>1.0</span>
      </div>
    </div>
  );
}

// ── The small zone chart (tag sidebar overview) ──────────────────────────

/** Zones bottom to top, as the chart reads: what is out, what waits, what is in. */
const ZONE_ORDER = [
  ["excluded", "grey"],
  ["tentative", "amber"],
  ["accepted", "green"],
] as const;

/** The ticks a zone chart draws: the lower line always, the upper one once there is one. */
export interface TickLines {
  lower: number;
  upper: number | null;
}

interface ZoneHistogramProps {
  /** 20 bands of 0.05, each split by zone. */
  bins: ZoneBin[];
  /** The count a full-height bar stands for. */
  scale: number;
  /** The codebook's lines, drawn as ticks; null on a chart whose codebooks' lines differ. */
  lines: TickLines | null;
  /** What the chart says, for a screen reader: the tally. */
  label: string;
}

/** Bars only: squares stay the dialog's (owner, review of Phase 6). */
export function ZoneHistogram({ bins, scale, lines, label }: ZoneHistogramProps) {
  return (
    <div
      className="threshold-histogram threshold-histogram--overview"
      role="img"
      aria-label={label}
      data-testid="bn-overview-histogram"
    >
      {bins.map((bin, idx) => (
        <div key={idx} className="threshold-histogram-bin">
          {ZONE_ORDER.map(([zone, colour]) =>
            bin[zone] === 0 ? null : (
              <div
                key={zone}
                className={`threshold-histogram-bar threshold-histogram-bar--${colour}`}
                data-zone={zone}
                style={{ height: `${(bin[zone] / Math.max(1, scale)) * 100}%` }}
              />
            ),
          )}
        </div>
      ))}
      {lines && (
        <span
          className="threshold-histogram-tick"
          data-tick="lower"
          style={{ left: `${lines.lower * 100}%` }}
        />
      )}
      {lines?.upper != null && (
        <span
          className="threshold-histogram-tick"
          data-tick="upper"
          style={{ left: `${lines.upper * 100}%` }}
        />
      )}
    </div>
  );
}
