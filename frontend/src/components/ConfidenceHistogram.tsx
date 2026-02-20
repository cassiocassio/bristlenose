/**
 * ConfidenceHistogram — 20-bin histogram of proposal confidence scores.
 *
 * Two rendering modes:
 * - **Unit-square mode**: each proposal is a coloured square (tag colour),
 *   stacked vertically. Used when the tallest bin fits within the histogram height.
 * - **Continuous bar mode**: solid bars coloured by zone (green/amber/grey).
 *   Fallback for large datasets where unit squares would be too small.
 */

import { useMemo, useRef, useCallback } from "react";
import type { ProposedTagResponse } from "../utils/types";
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
function binIndex(confidence: number): number {
  const idx = Math.floor(confidence / BIN_WIDTH);
  return Math.min(idx, NUM_BINS - 1);
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
            title={`${count} proposal${count !== 1 ? "s" : ""}`}
          />
        </div>
      );
    },
    [lower, upper, maxCount, useSquares],
  );

  return (
    <div>
      <div
        ref={containerRef}
        className="threshold-histogram"
        data-testid="bn-threshold-histogram"
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
