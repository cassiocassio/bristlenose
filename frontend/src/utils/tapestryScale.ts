/** Session tapestry scale — the parts SessionsTable needs before any slice is opened. */

export const TAPESTRY_GUTTER = 82;
export const TAPESTRY_RIGHT = 14;

/**
 * One shared scale for every slice: fit the longest session, clamped to 1–4 s/px.
 * Upper clamp: a short project is never blown up. Lower clamp: below 4 s/px a
 * 60-minute session still fits a laptop's grid; longer ones scroll.
 * Measured basis: experiments/session-tapestry/README.md.
 */
export function fitScale(longestSeconds: number, width: number): number {
  const usable = Math.max(1, width - TAPESTRY_GUTTER - TAPESTRY_RIGHT);
  return Math.min(4, Math.max(1, longestSeconds / usable));
}

/** Zoom slider 0–100 → seconds per pixel, log-spaced from fit down to 0.25 s/px. */
export function zoomScale(fit: number, value: number): number {
  return Math.exp(Math.log(fit) + (Math.log(0.25) - Math.log(fit)) * (value / 100));
}
