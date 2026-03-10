/** Device viewport presets for the responsive playground. */

export interface DevicePreset {
  name: string;
  width: number | null; // null = full (natural) width
  category: "phone" | "tablet" | "laptop" | "desktop";
}

export const DEVICE_PRESETS: DevicePreset[] = [
  { name: "iPhone SE", width: 375, category: "phone" },
  { name: "iPhone 14 Pro", width: 393, category: "phone" },
  { name: "iPad Mini", width: 768, category: "tablet" },
  { name: 'iPad Pro 11"', width: 1024, category: "tablet" },
  { name: 'MacBook Air 13"', width: 1470, category: "laptop" },
  { name: 'MacBook Pro 14"', width: 1512, category: "laptop" },
  { name: 'MacBook Pro 16"', width: 1728, category: "laptop" },
  { name: 'iMac 24"', width: 2240, category: "desktop" },
  { name: "Studio Display", width: 2560, category: "desktop" },
  { name: "Pro Display XDR", width: 3008, category: "desktop" },
  { name: "Full width", width: null, category: "desktop" },
];

/** Named breakpoint set — a set of viewport-width thresholds. */
export interface BreakpointSet {
  name: string;
  values: number[];
  source: string;
}

export const BREAKPOINT_SETS: Record<string, BreakpointSet> = {
  bristlenose: {
    name: "Bristlenose",
    values: [600, 900, 1100],
    source: "Current",
  },
  tailwind: {
    name: "Tailwind",
    values: [640, 768, 1024, 1280, 1536],
    source: "Tailwind CSS v3",
  },
  bootstrap: {
    name: "Bootstrap",
    values: [576, 768, 992, 1200, 1400],
    source: "Bootstrap 5",
  },
  material: {
    name: "Material",
    values: [600, 905, 1240, 1440],
    source: "Material Design 3",
  },
  minimal: {
    name: "Minimal",
    values: [600, 1200],
    source: "Two-breakpoint",
  },
  contentFirst: {
    name: "Content-first",
    values: [720, 1040, 1360],
    source: "45/65/85 ch",
  },
};

/**
 * Find the closest device name at or below a given viewport width.
 */
export function getDeviceName(width: number): string {
  let best = DEVICE_PRESETS[0];
  for (const d of DEVICE_PRESETS) {
    if (d.width !== null && d.width <= width) best = d;
  }
  return best.name;
}

/**
 * Return the breakpoint zone index (0-based) for a given width and set.
 * Zone 0 is below the first breakpoint, zone N is above the last.
 */
export function getBreakpointZone(
  width: number,
  values: number[],
): number {
  for (let i = 0; i < values.length; i++) {
    if (width < values[i]) return i;
  }
  return values.length;
}
