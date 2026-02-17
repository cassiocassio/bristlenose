import { useId } from "react";

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
  title?: string;
  displayValue: string;
  viz: MetricViz;
  "data-testid"?: string;
}

// ---------------------------------------------------------------------------
// Intensity dots SVG — matches analysis.js intensityDotsSvg()
// ---------------------------------------------------------------------------

function IntensityDots({ value }: { value: number }) {
  const clipBase = useId();
  const rounded = Math.round(value * 2) / 2;
  const r = 5;
  const cx0 = 7;
  const gap = 16;
  const w = cx0 + gap * 2 + r + 2;
  const h = r * 2 + 2;
  const colour = "var(--dot-colour, var(--bn-colour-text))";

  const dots: React.ReactNode[] = [];

  for (let i = 0; i < 3; i++) {
    const threshold = i + 1;
    const x = cx0 + i * gap;
    const y = r + 1;

    if (rounded >= threshold) {
      // Filled dot
      dots.push(
        <circle key={i} cx={x} cy={y} r={r} fill={colour} opacity={0.7} />,
      );
    } else if (rounded >= threshold - 0.5) {
      // Half-filled dot
      const clipId = `${clipBase}-${i}`;
      dots.push(
        <g key={i}>
          <defs>
            <clipPath id={`${clipId}-l`}>
              <rect x={x - r} y={y - r} width={r} height={r * 2} />
            </clipPath>
            <clipPath id={`${clipId}-r`}>
              <rect x={x} y={y - r} width={r} height={r * 2} />
            </clipPath>
          </defs>
          <circle cx={x} cy={y} r={r} fill={colour} opacity={0.7} clipPath={`url(#${clipId}-l)`} />
          <circle cx={x} cy={y} r={r} fill="none" stroke={colour} strokeWidth={1.2} opacity={0.35} clipPath={`url(#${clipId}-r)`} />
          <circle cx={x} cy={y} r={r} fill="none" stroke={colour} strokeWidth={1.2} opacity={0.35} />
        </g>,
      );
    } else {
      // Empty dot
      dots.push(
        <circle key={i} cx={x} cy={y} r={r} fill="none" stroke={colour} strokeWidth={1.2} opacity={0.35} />,
      );
    }
  }

  return (
    <svg
      className="intensity-dots-svg"
      width={w}
      height={h}
      viewBox={`0 0 ${w} ${h}`}
      data-testid="bn-metric-dots"
    >
      {dots}
    </svg>
  );
}

// ---------------------------------------------------------------------------
// Metric
// ---------------------------------------------------------------------------

export function Metric({
  label,
  title,
  displayValue,
  viz,
  "data-testid": testId,
}: MetricProps) {
  return (
    <>
      <span className="metric-label" title={title} data-testid={testId ? `${testId}-label` : undefined}>
        {label}
      </span>
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
        {viz.type === "dots" && <IntensityDots value={viz.value} />}
      </span>
    </>
  );
}
