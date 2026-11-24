/**
 * DualThresholdSlider — the two confidence thresholds, drawn as a Levels control
 * (Pixelmator Pro's; owner, 24 Nov 2026, frame B of docs/mockups/autocode-levels-slider.html).
 *
 * The histogram (`children`) is the control's box: a dotted guide rises through it at
 * each threshold, and the two pointers hang from its floor, tip up at their value, the
 * value inside, orange for the lower line and green for the upper. The pointers carry
 * the zones' colours; the histogram's ground stays plain (owner, 24 Nov 2026). Step
 * granularity: 0.05 (matches histogram bins).
 */

import { useCallback, useRef } from "react";
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { CONFIDENCE_STEP, confidenceText, snapToStep } from "../utils/confidenceStep";

const STEP = CONFIDENCE_STEP;
const MIN_GAP = 0.05;

interface DualThresholdSliderProps {
  lower: number;
  upper: number;
  onLowerChange: (value: number) => void;
  onUpperChange: (value: number) => void;
  /** The histogram the thresholds cut. */
  children?: ReactNode;
}

/** A pointer: tip up at x = 0, widened to hold its value (40 × 24). */
const POINTER = "M0 0.75 L5.5 6 L18.5 6 Q19.25 6 19.25 6.75 L19.25 22.5 Q19.25 23.25 18.5 23.25 "
  + "L-18.5 23.25 Q-19.25 23.25 -19.25 22.5 L-19.25 6.75 Q-19.25 6 -18.5 6 L-5.5 6 Z";

function Pointer() {
  return (
    <svg className="threshold-slider-pointer" width="40" height="24" viewBox="-20 0 40 24"
      aria-hidden="true">
      <path d={POINTER} />
    </svg>
  );
}

/** Snap a raw 0–1 value to the nearest 0.05 step (see `snapToStep`). */
const snap = snapToStep;

/** Clamp a value to [min, max]. */
function clamp(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, value));
}

/**
 * Clamp a step value to bounds, then snap again: the bounds are `upper - 0.05`
 * and `lower + 0.05`, which drift the same way (0.7 - 0.05 is 0.6499999999999999).
 */
function clampStep(value: number, min: number, max: number): number {
  return snap(clamp(value, min, max));
}

export function DualThresholdSlider({
  lower,
  upper,
  onLowerChange,
  onUpperChange,
  children,
}: DualThresholdSliderProps) {
  const { t, i18n } = useTranslation();
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
          onLowerChange(clampStep(raw, 0, upper - MIN_GAP));
        } else {
          onUpperChange(clampStep(raw, lower + MIN_GAP, 1));
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
        onLowerChange(clampStep(snap(lower + delta), 0, upper - MIN_GAP));
      } else {
        onUpperChange(clampStep(snap(upper + delta), lower + MIN_GAP, 1));
      }
    },
    [lower, upper, onLowerChange, onUpperChange],
  );

  const lowerPct = `${lower * 100}%`;
  const upperPct = `${upper * 100}%`;

  return (
    <div className="threshold-slider" data-testid="bn-threshold-slider">
      {/* The box: the histogram, and a guide at each line. It is also what a drag
          measures against. */}
      <div className="threshold-slider-track" ref={trackRef}>
        {children}
        <div className="threshold-slider-guide threshold-slider-guide--lower" style={{ left: lowerPct }} />
        <div className="threshold-slider-guide threshold-slider-guide--upper" style={{ left: upperPct }} />
      </div>

      {/* The pointers hang from the box's floor. */}
      <div className="threshold-slider-rail">
        <div
          className="threshold-slider-thumb threshold-slider-thumb--lower"
          style={{ left: lowerPct }}
          role="slider"
          aria-label={t("autocode.lowerThreshold")}
          aria-valuemin={0}
          aria-valuemax={snap(upper - MIN_GAP)}
          aria-valuenow={lower}
          aria-valuetext={confidenceText(lower, i18n.language)}
          tabIndex={0}
          onPointerDown={startDrag("lower")}
          onKeyDown={handleKeyDown("lower")}
          data-testid="bn-threshold-lower"
        >
          <Pointer />
          <span className="threshold-slider-label">{confidenceText(lower, i18n.language)}</span>
        </div>
        <div
          className="threshold-slider-thumb threshold-slider-thumb--upper"
          style={{ left: upperPct }}
          role="slider"
          aria-label={t("autocode.upperThreshold")}
          aria-valuemin={snap(lower + MIN_GAP)}
          aria-valuemax={1}
          aria-valuenow={upper}
          aria-valuetext={confidenceText(upper, i18n.language)}
          tabIndex={0}
          onPointerDown={startDrag("upper")}
          onKeyDown={handleKeyDown("upper")}
          data-testid="bn-threshold-upper"
        >
          <Pointer />
          <span className="threshold-slider-label">{confidenceText(upper, i18n.language)}</span>
        </div>
      </div>
    </div>
  );
}
