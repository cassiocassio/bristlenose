/**
 * What the Discussion lens remembers between visits. Mode, session and focus
 * live for the page's lifetime (module state), so switching to another lens and
 * back lands where the researcher left it; the navigator width is a per-viewer
 * convenience kept in localStorage. Phase 4 proper replaces this with a
 * DiscussionStore on the SignalStore pattern (plan §3).
 */

import type { Focus, GuideView, Mode } from "./model";

export interface LensState {
  mode: Mode;
  guideView: GuideView;
  session: string | null;
  focus: Focus | null;
  navWidth: number | null;
}

const WIDTH_KEY = "bn-discussion-nav-width";
let memory: Omit<LensState, "navWidth"> = { mode: "merged", guideView: "summary", session: null, focus: null };

export function readLensState(): LensState {
  let navWidth: number | null = null;
  try {
    const v = Number(localStorage.getItem(WIDTH_KEY));
    navWidth = Number.isFinite(v) && v > 0 ? v : null;
  } catch {
    // private window or blocked storage: the width just isn't remembered
  }
  return { ...memory, navWidth };
}

export function writeLensState(s: LensState): void {
  memory = { mode: s.mode, guideView: s.guideView, session: s.session, focus: s.focus };
  try {
    if (s.navWidth) localStorage.setItem(WIDTH_KEY, String(Math.round(s.navWidth)));
  } catch {
    // as above
  }
}

/** For tests: forget everything. */
export function resetLensState(): void {
  memory = { mode: "merged", guideView: "summary", session: null, focus: null };
  try {
    localStorage.removeItem(WIDTH_KEY);
  } catch {
    // as above
  }
}
