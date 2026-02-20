/**
 * DualThresholdSlider — two-handle slider for lower/upper confidence thresholds.
 *
 * Renders a horizontal track with three coloured segments (grey/amber/green)
 * and two draggable thumb handles. Step granularity: 0.05 (matches histogram bins).
 */

import { useCallback, useRef } from "react";

const STEP = 0.05;
const MIN_GAP = 0.05;

interface DualThresholdSliderProps {
  lower: number;
  upper: number;
  onLowerChange: (value: number) => void;
  onUpperChange: (value: number) => void;
}

/** Snap a raw 0–1 value to the nearest 0.05 step. */
function snap(value: number): number {
  return Math.round(value / STEP) * STEP;
}

/** Clamp a value to [min, max]. */
function clamp(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, value));
}

export function DualThresholdSlider({
  lower,
  upper,
  onLowerChange,
  onUpperChange,
}: DualThresholdSliderProps) {
  const trackRef = useRef<HTMLDivElement>(null);

  /** Convert a mouse/touch clientX to a 0–1 value along the track. */
  const clientXToValue = useCallback((clientX: number): number => {
    const track = trackRef.current;
    if (!track) return 0;
    const rect = track.getBoundingClientRect();
    const ratio = (clientX - rect.left) / rect.width;
    return clamp(ratio, 0, 1);
  }, []);

  /** Start dragging a thumb. */
  const startDrag = useCallback(
    (which: "lower" | "upper") => (e: React.PointerEvent) => {
      e.preventDefault();
      const target = e.currentTarget as HTMLElement;
      target.setPointerCapture(e.pointerId);

      const onMove = (ev: PointerEvent) => {
        const raw = snap(clientXToValue(ev.clientX));
        if (which === "lower") {
          onLowerChange(clamp(raw, 0, upper - MIN_GAP));
        } else {
          onUpperChange(clamp(raw, lower + MIN_GAP, 1));
        }
      };

      const onUp = () => {
        target.removeEventListener("pointermove", onMove);
        target.removeEventListener("pointerup", onUp);
      };

      target.addEventListener("pointermove", onMove);
      target.addEventListener("pointerup", onUp);
    },
    [clientXToValue, lower, upper, onLowerChange, onUpperChange],
  );

  /** Keyboard support: arrow keys move by one step. */
  const handleKeyDown = useCallback(
    (which: "lower" | "upper") => (e: React.KeyboardEvent) => {
      let delta = 0;
      if (e.key === "ArrowLeft" || e.key === "ArrowDown") delta = -STEP;
      if (e.key === "ArrowRight" || e.key === "ArrowUp") delta = STEP;
      if (delta === 0) return;
      e.preventDefault();
      if (which === "lower") {
        onLowerChange(clamp(snap(lower + delta), 0, upper - MIN_GAP));
      } else {
        onUpperChange(clamp(snap(upper + delta), lower + MIN_GAP, 1));
      }
    },
    [lower, upper, onLowerChange, onUpperChange],
  );

  const lowerPct = `${lower * 100}%`;
  const upperPct = `${upper * 100}%`;

  return (
    <div className="threshold-slider" data-testid="bn-threshold-slider">
      <div className="threshold-slider-track" ref={trackRef}>
        {/* Grey segment: 0 → lower */}
        <div
          className="threshold-slider-segment threshold-slider-segment--grey"
          style={{ left: 0, width: lowerPct }}
        />
        {/* Amber segment: lower → upper */}
        <div
          className="threshold-slider-segment threshold-slider-segment--amber"
          style={{ left: lowerPct, width: `${(upper - lower) * 100}%` }}
        />
        {/* Green segment: upper → 1.0 */}
        <div
          className="threshold-slider-segment threshold-slider-segment--green"
          style={{ left: upperPct, width: `${(1 - upper) * 100}%` }}
        />
      </div>

      {/* Lower thumb */}
      <div
        className="threshold-slider-thumb"
        style={{ left: lowerPct }}
        role="slider"
        aria-label="Lower threshold"
        aria-valuemin={0}
        aria-valuemax={upper - MIN_GAP}
        aria-valuenow={lower}
        tabIndex={0}
        onPointerDown={startDrag("lower")}
        onKeyDown={handleKeyDown("lower")}
        data-testid="bn-threshold-lower"
      >
        <span className="threshold-slider-label">{lower.toFixed(2)}</span>
      </div>

      {/* Upper thumb */}
      <div
        className="threshold-slider-thumb"
        style={{ left: upperPct }}
        role="slider"
        aria-label="Upper threshold"
        aria-valuemin={lower + MIN_GAP}
        aria-valuemax={1}
        aria-valuenow={upper}
        tabIndex={0}
        onPointerDown={startDrag("upper")}
        onKeyDown={handleKeyDown("upper")}
        data-testid="bn-threshold-upper"
      >
        <span className="threshold-slider-label">{upper.toFixed(2)}</span>
      </div>
    </div>
  );
}
