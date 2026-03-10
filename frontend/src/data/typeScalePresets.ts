/** Type scale presets for the responsive playground. */

export interface TypeScalePreset {
  name: string;
  origin: "Musical" | "Design System" | "Bristlenose";
  /** For ratio-based scales: heading sizes = base * ratio^n */
  ratio?: number;
  /** For explicit scales: exact px sizes (overrides ratio when present) */
  sizes?: number[];
  /** Base size in px (default 16) */
  base?: number;
}

// ── Musical ratios ──────────────────────────────────────────────

export const MUSICAL_PRESETS: TypeScalePreset[] = [
  { name: "Major Second", origin: "Musical", ratio: 1.125 },
  { name: "Minor Third", origin: "Musical", ratio: 1.2 },
  { name: "Major Third", origin: "Musical", ratio: 1.25 },
  { name: "Perfect Fourth", origin: "Musical", ratio: 1.333 },
  { name: "Golden Ratio", origin: "Musical", ratio: 1.618 },
];

// ── Design system scales ────────────────────────────────────────

export const DESIGN_SYSTEM_PRESETS: TypeScalePreset[] = [
  {
    name: "Apple HIG",
    origin: "Design System",
    sizes: [11, 12, 13, 15, 16, 17, 20, 22, 28, 34],
    base: 17,
  },
  {
    name: "Material Design",
    origin: "Design System",
    sizes: [11, 12, 14, 16, 22, 24, 28, 32, 36, 45, 57],
    base: 16,
  },
  {
    name: "IBM Carbon",
    origin: "Design System",
    sizes: [12, 14, 16, 18, 20, 24, 28, 32, 42, 54, 76],
    base: 16,
  },
  {
    name: "GitHub Primer",
    origin: "Design System",
    sizes: [12, 14, 16, 20, 24, 32, 40, 48],
    base: 16,
  },
  {
    name: "Ant Design",
    origin: "Design System",
    sizes: [12, 14, 16, 20, 24, 30, 38],
    base: 14,
  },
];

// ── All presets combined ────────────────────────────────────────

export const ALL_TYPE_SCALE_PRESETS: TypeScalePreset[] = [
  ...MUSICAL_PRESETS,
  ...DESIGN_SYSTEM_PRESETS,
];

/**
 * Compute heading sizes from a ratio-based preset.
 * Returns sizes for steps -3 to +4 relative to the base.
 */
export function computeRatioSizes(
  base: number,
  ratio: number,
  stepsDown = 3,
  stepsUp = 4,
): { step: number; size: number }[] {
  const result: { step: number; size: number }[] = [];
  for (let i = -stepsDown; i <= stepsUp; i++) {
    result.push({ step: i, size: base * Math.pow(ratio, i) });
  }
  return result;
}

/**
 * Map a size (px) to a semantic role name for preview display.
 */
export function sizeToRole(px: number): string {
  if (px < 12) return "badge/caption";
  if (px < 14.5) return "meta/toolbar";
  if (px < 17) return "body";
  if (px < 20) return "h3/subtitle";
  if (px < 24) return "h2/section";
  if (px < 30) return "h1/title";
  return "display";
}

/** Sample text per role for type scale preview. */
export const ROLE_SAMPLES: Record<string, string> = {
  "badge/caption": "frustration",
  "meta/toolbar": "Export CSV",
  body: "The quick brown fox jumps over the lazy dog",
  "h3/subtitle": "Learning Journey",
  "h2/section": "Community",
  "h1/title": "Climbing Study",
  display: "Report",
};
