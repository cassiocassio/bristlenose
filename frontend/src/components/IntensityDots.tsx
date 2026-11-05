import { useId } from "react";

/**
 * The intensity mark: three circles that grow, one implementation for the chart and the quote
 * paragraphs.
 *
 * Three equal circles read as a page indicator. Here the radii grow 3.8, 4.6, 5.4 on a common
 * centre line at an equal pitch, so the tangents run straight to a point (a cone) and the mark
 * reads as one rising quantity, not as three objects with one flagged. The ramp is gentle on
 * purpose: ink adds up as the circles fill, and this ramp keeps the perceived steps near even
 * (measured 1 : 1.8 : 2.7 against 1 : 1.6 : 2.2 for equal circles) while a steep cone left level 1
 * a speck. A circle not yet reached stays as a faint ghost so the ceiling is always visible.
 * Chosen by the owner, 5 Nov 2026 (`docs/design-intensity-mark-research.md`, mockup
 * `docs/mockups/intensity-graded-circles.html`, row G).
 *
 * `m` is the chart's size, drawn from the left edge of the box. `s` is the paragraphs': the radii
 * 5% smaller (owner, 30 Oct 2026), drawn from the right edge because the paragraph's mark floats
 * to the top right corner. The box is 46 x 12 for both and the centre line is shared.
 * Half values (1.5, 2.5) fill half of the next circle; the chart's mean intensity needs them and a
 * single quote's whole number does not.
 */
export type IntensityDotsSize = "m" | "s";

const SCALE: Record<IntensityDotsSize, number> = { m: 1, s: 0.95 };
const RADII = [3.8, 4.6, 5.4];
const PITCH = 11.5;
const BOX_W = 46;
const BOX_H = 12;
const EDGE = 1; // clear space between the ink and the box edge it is drawn from
const GHOST_OPACITY = 0.22;
const FILL_OPACITY = 0.8;

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
  const k = SCALE[size];
  const radii = RADII.map((r) => r * k);
  const y = BOX_H / 2; // the centre line is the same for both sizes
  // The first centre: left-aligned for the chart, right-aligned for the paragraph.
  const cx0 =
    size === "m" ? EDGE + radii[0] : BOX_W - EDGE - radii[2] - PITCH * 2;

  const dots: React.ReactNode[] = [];
  for (let i = 0; i < 3; i++) {
    const threshold = i + 1;
    const x = cx0 + i * PITCH;
    const r = radii[i];
    if (rounded >= threshold) {
      dots.push(<circle key={i} cx={x} cy={y} r={r} fill={colour} opacity={FILL_OPACITY} />);
    } else if (rounded >= threshold - 0.5) {
      const clipId = `${clipBase}-${i}`;
      dots.push(
        <g key={i}>
          <defs>
            <clipPath id={clipId}>
              <rect x={x - r} y={y - r} width={r} height={r * 2} />
            </clipPath>
          </defs>
          <circle cx={x} cy={y} r={r} fill={colour} opacity={GHOST_OPACITY} />
          <circle cx={x} cy={y} r={r} fill={colour} opacity={FILL_OPACITY} clipPath={`url(#${clipId})`} />
        </g>,
      );
    } else {
      dots.push(<circle key={i} cx={x} cy={y} r={r} fill={colour} opacity={GHOST_OPACITY} />);
    }
  }

  return (
    <svg
      className="intensity-dots-svg"
      width={BOX_W}
      height={BOX_H}
      viewBox={`0 0 ${BOX_W} ${BOX_H}`}
      data-size={size}
      data-testid={testId}
    >
      {dots}
    </svg>
  );
}
