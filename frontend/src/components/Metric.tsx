import { IntensityDots } from "./IntensityDots";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface MetricBarViz {
  type: "bar";
  /** Percentage 0–100 for the fill width. */
  percentage: number;
}

interface MetricDotsViz {
  type: "dots";
  /** Value 0–3 (supports halves like 1.5, 2.5). */
  value: number;
}

interface MetricNoneViz {
  type: "none";
}

export type MetricViz = MetricBarViz | MetricDotsViz | MetricNoneViz;

interface MetricProps {
  label: string;
  /** The short form, shown instead of `label` when the card is narrow (`signals.css`). */
  shortLabel?: string;
  title?: string;
  displayValue: string;
  viz: MetricViz;
  "data-testid"?: string;
}

// ---------------------------------------------------------------------------
// Metric
// ---------------------------------------------------------------------------

/**
 * A metric's name in two lengths. The long one is the default; below the card's narrow width
 * (`@container` in `signals.css`) the short one takes over. Both are in the markup and the one
 * that is not shown is `display: none`, so assistive technology reads only the one on screen.
 */
export function MetricLabel({
  label,
  shortLabel,
  title,
  "data-testid": testId,
}: {
  label: string;
  shortLabel?: string;
  title?: string;
  "data-testid"?: string;
}) {
  return (
    <span className="metric-label" title={title} data-testid={testId}>
      {shortLabel && shortLabel !== label ? (
        <>
          <span className="metric-label-long">{label}</span>
          <span className="metric-label-short">{shortLabel}</span>
        </>
      ) : (
        label
      )}
    </span>
  );
}

export function Metric({
  label,
  shortLabel,
  title,
  displayValue,
  viz,
  "data-testid": testId,
}: MetricProps) {
  return (
    <>
      <MetricLabel
        label={label}
        shortLabel={shortLabel}
        title={title}
        data-testid={testId ? `${testId}-label` : undefined}
      />
      <span className="metric-value" data-testid={testId ? `${testId}-value` : undefined}>
        {displayValue}
      </span>
      <span className="metric-viz" data-testid={testId ? `${testId}-viz` : undefined}>
        {viz.type === "bar" && (
          <span className="conc-bar-track">
            <span
              className="conc-bar-fill"
              style={{ width: `${Math.min(100, Math.max(0, viz.percentage))}%` }}
            />
          </span>
        )}
        {viz.type === "dots" && <IntensityDots value={viz.value} data-testid="bn-metric-dots" />}
      </span>
    </>
  );
}
