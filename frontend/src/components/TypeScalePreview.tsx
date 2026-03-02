/**
 * TypeScalePreview — compact type hierarchy display for the playground.
 *
 * Shows each step in the current type scale with rendered sample text,
 * pixel size, ratio from base, and semantic role. Live-updates when
 * the user changes scale ratio, base size, or switches presets.
 */

import { useMemo, useState } from "react";
import { usePlaygroundStore, TOKEN_DEFAULTS } from "../contexts/PlaygroundStore";
import {
  computeRatioSizes,
  sizeToRole,
  ROLE_SAMPLES,
} from "../data/typeScalePresets";

const WEIGHT_FOR_ROLE: Record<string, number> = {
  "badge/caption": 420,
  "meta/toolbar": 420,
  body: 420,
  "h3/subtitle": 490,
  "h2/section": 490,
  "h1/title": 700,
  display: 700,
};

export function TypeScalePreview() {
  const pg = usePlaygroundStore();
  const [expanded, setExpanded] = useState(false);

  const base = pg.baseFontSize ?? TOKEN_DEFAULTS.baseFontSize;
  const ratio = pg.typeScaleRatio ?? TOKEN_DEFAULTS.typeScaleRatio;

  const steps = useMemo(
    () => computeRatioSizes(base, ratio, 2, 4),
    [base, ratio],
  );

  const presetLabel = pg.typeScalePreset ?? `${ratio.toFixed(3)}`;

  return (
    <div className="pg-type-preview">
      <button
        className="pg-section-toggle"
        onClick={() => setExpanded(!expanded)}
        type="button"
      >
        <span className="pg-section-arrow">{expanded ? "\u25BC" : "\u25B6"}</span>
        <span className="pg-section-label">Type Scale</span>
        <span className="pg-section-value">{presetLabel}</span>
      </button>

      {expanded && (
        <div className="pg-type-grid">
          <div className="pg-type-header">
            <span>Step</span>
            <span>px</span>
            <span>Ratio</span>
            <span>Role</span>
            <span>Sample</span>
          </div>
          {steps.map(({ step, size }) => {
            const role = sizeToRole(size);
            const sample = ROLE_SAMPLES[role] ?? "Sample text";
            const weight = WEIGHT_FOR_ROLE[role] ?? 420;
            const isBase = step === 0;
            return (
              <div
                key={step}
                className={`pg-type-row${isBase ? " pg-type-base" : ""}`}
              >
                <span className="pg-type-step">
                  {step > 0 ? `+${step}` : step}
                </span>
                <span className="pg-type-px">{size.toFixed(1)}</span>
                <span className="pg-type-ratio">
                  {(size / base).toFixed(2)}x
                </span>
                <span className="pg-type-role">{role}</span>
                <span
                  className="pg-type-sample"
                  style={{ fontSize: `${size}px`, fontWeight: weight }}
                >
                  {sample}
                </span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
