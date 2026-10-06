/**
 * Session tapestry tuning — the one place its type steps and container padding live.
 *
 * The defaults ARE the shipped design. The dev-only playground (TapestryPlayground, `serve --dev`)
 * moves them live so the owner can tune by eye, then hands back a list of changes to commit here.
 * Deliberately narrow: type moves only along the existing `--bn-text-*` ladder (no new sizes),
 * popover padding only along the `--bn-space-*` scale, and the few raw-pixel paddings only through a
 * short list of snapped values. Making a new token should take a decision, not a slider.
 */

import { useSyncExternalStore } from "react";

/** The type ladder, smallest first (tokens.css / tokens-desktop.css). */
export const LADDER = ["micro", "badge", "caption", "label", "body", "heading"] as const;
export type Step = (typeof LADDER)[number];

/** The space scale (tokens.css). */
export const SPACE = ["xs", "sm", "md", "lg"] as const;
export type Space = (typeof SPACE)[number];

export interface TapestryTuning {
  type: {
    lane: Step; // Sections / Moderator / … lane labels
    flag: Step; // section flags
    clip: Step; // names on speaker clips
    theme: Step; // theme tags
    tick: Step; // timecodes under the timeline
    popMeta: Step; // popover: timecode and section line
    popQuote: Step; // popover: the quote
  };
  pad: {
    flagX: number; // flag label inset, each side (px)
    flagH: number; // flag height (px)
    clipX: number; // clip label inset (px)
    clipH: number; // moderator clip height; participant clips are 2px taller (px)
    themeX: number; // theme chip inset, each side (px)
    themeH: number; // theme chip height (px)
    themeGap: number; // gap between theme rows (px)
    barW: number; // sentiment bar width (px)
    popover: Space; // popover padding
  };
}

export const DEFAULTS: TapestryTuning = {
  // Tuned by eye in the playground, 6 Oct 2026: section flags and theme tags up to label, clip
  // names up to badge; taller flags (18) and theme chips (18), and a pixel more between theme rows.
  // Sentiment bars 4 → 6px wide, the same day.
  type: { lane: "caption", flag: "label", clip: "badge", theme: "label", tick: "micro", popMeta: "caption", popQuote: "body" },
  pad: { flagX: 3, flagH: 18, clipX: 4, clipH: 16, themeX: 4, themeH: 18, themeGap: 4, barW: 6, popover: "md" },
};

/** Snapped choices for the raw-pixel paddings — the only values the playground offers. */
export const PAD_STEPS: Record<Exclude<keyof TapestryTuning["pad"], "popover">, number[]> = {
  flagX: [2, 3, 4, 5, 6],
  flagH: [12, 14, 16, 18, 20],
  clipX: [2, 3, 4, 5, 6],
  clipH: [14, 16, 18, 20, 22],
  themeX: [2, 3, 4, 5, 6, 8],
  themeH: [14, 16, 18, 20],
  themeGap: [1, 2, 3, 4, 6],
  barW: [4, 5, 6, 7, 8],
};

let state: TapestryTuning = DEFAULTS;
const listeners = new Set<() => void>();
const emit = () => listeners.forEach((l) => l());

export function getTapestryTuning(): TapestryTuning {
  return state;
}
export function setTapestryTuning(next: TapestryTuning): void {
  state = next;
  emit();
}
export function resetTapestryTuning(): void {
  state = DEFAULTS;
  emit();
}
export function useTapestryTuning(): TapestryTuning {
  return useSyncExternalStore(
    (l) => {
      listeners.add(l);
      return () => listeners.delete(l);
    },
    () => state,
    () => state,
  );
}

/** Human-readable differences from the defaults, for handing back to be committed. */
export function tuningChanges(t: TapestryTuning): string[] {
  const out: string[] = [];
  for (const k of Object.keys(t.type) as (keyof TapestryTuning["type"])[]) {
    if (t.type[k] !== DEFAULTS.type[k]) out.push(`type.${k}: --bn-text-${DEFAULTS.type[k]} → --bn-text-${t.type[k]}`);
  }
  for (const k of Object.keys(t.pad) as (keyof TapestryTuning["pad"])[]) {
    if (t.pad[k] !== DEFAULTS.pad[k]) {
      out.push(k === "popover"
        ? `pad.popover: --bn-space-${DEFAULTS.pad.popover} → --bn-space-${t.pad.popover}`
        : `pad.${k}: ${DEFAULTS.pad[k]}px → ${t.pad[k]}px`);
    }
  }
  return out;
}
