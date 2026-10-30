import { useId } from "react";

/**
 * The three intensity circles, one implementation for the chart and the quote paragraphs.
 *
 * `m` is the chart's size. `s` is the paragraphs': the circle radius 5% smaller (owner, 30 Oct
 * 2026), the spacing unchanged, so the row of three is a touch lighter beside running text.
 * Half values (1.5, 2.5) draw a half-filled circle; the chart's mean intensity needs them and a
 * single quote's whole number does not.
 */
export type IntensityDotsSize = "m" | "s";

const RADIUS: Record<IntensityDotsSize, number> = { m: 5, s: 4.75 };

export function IntensityDots({
  value,
  size = "m",
  colour = "var(--dot-colour, var(--bn-colour-text))",
  "data-testid": testId,
}: {
  value: number;
  size?: IntensityDotsSize;
  colour?: string;
  "data-testid"?: string;
}) {
  const clipBase = useId();
  const rounded = Math.round(value * 2) / 2;
  const r = RADIUS[size];
  const cx0 = 7;
  const gap = 16;
  const w = cx0 + gap * 2 + 5 + 2; // the width does not change with the size
  const h = 5 * 2 + 2;
  const y = 6; // the centre line does not change either, so the two sizes share a baseline

  const dots: React.ReactNode[] = [];
  for (let i = 0; i < 3; i++) {
    const threshold = i + 1;
    const x = cx0 + i * gap;
    if (rounded >= threshold) {
      dots.push(<circle key={i} cx={x} cy={y} r={r} fill={colour} opacity={0.7} />);
    } else if (rounded >= threshold - 0.5) {
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
      data-size={size}
      data-testid={testId}
    >
      {dots}
    </svg>
  );
}
