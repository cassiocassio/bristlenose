/**
 * The Screens lens's navigator — the list of screens — as a left panel.
 *
 * Wired the way the Discussion lens's guide is (islands/discussion/guidePanel.ts):
 * the navigator is a column inside the lens rather than the shared left panel,
 * it remembers its own open/closed setting, and the toolbar button, ⌥⌘L and `[`
 * reach it through the same actions (AppLayout, useKeyboardShortcuts).
 *
 * Unlike the guide it is not fitted to the window: it is shown whenever it is
 * wished (docs/design-screens.md). The lens reports what it
 * shows and the width it wants; AppLayout mirrors both to the Mac
 * (`panel-state`), so the View menu reads Show or Hide correctly.
 */

import { useSyncExternalStore } from "react";
import { storePref } from "../../utils/nativePrefs";

const OPEN_KEY = "bn-screens-nav-open";

interface NavPanelState {
  /** The researcher's wish. Starts open. */
  wish: boolean;
  /** What the lens is showing (reported by the lens). */
  shown: boolean;
  /** The width the wished arrangement needs (reported by the lens). */
  wanted: number;
}

function readWish(): boolean {
  try {
    return localStorage.getItem(OPEN_KEY) !== "false";
  } catch {
    return true; // private window or blocked storage: start open
  }
}

/** Through storePref, so the Mac app keeps it past a relaunch (R89). */
function writeWish(open: boolean): void {
  storePref(OPEN_KEY, String(open));
}

let state: NavPanelState = { wish: readWish(), shown: false, wanted: 0 };
const listeners = new Set<() => void>();

function setState(next: NavPanelState): void {
  if (next.wish === state.wish && next.shown === state.shown && next.wanted === state.wanted) return;
  state = next;
  listeners.forEach((l) => l());
}

function subscribe(l: () => void): () => void {
  listeners.add(l);
  return () => listeners.delete(l);
}

export function useScreensNav(): NavPanelState {
  return useSyncExternalStore(subscribe, () => state, () => state);
}

export function screensNavState(): NavPanelState {
  return state;
}

/** Open or close it explicitly (View ▸ Show/Hide All Sidebars). */
export function setScreensNavOpen(open: boolean): void {
  writeWish(open);
  setState({ ...state, wish: open });
}

/** Toggle what is SHOWING, as `toggleDiscussionGuide` does (toolbar button, ⌥⌘L, `[`). The View
 *  menu and the rail button both read `shown`; toggling the wish instead would, in a state with no
 *  board, close a navigator they say is closed and remember it closed. */
export function toggleScreensNav(): void {
  setScreensNavOpen(!state.shown);
}

/** The lens's report. Equality-guarded. */
export function reportScreensNav(shown: boolean, wanted: number): void {
  setState({ ...state, shown, wanted });
}

/** For tests. */
export function resetScreensNav(): void {
  try {
    localStorage.removeItem(OPEN_KEY);
  } catch {
    // as above
  }
  state = { wish: true, shown: false, wanted: 0 };
  listeners.forEach((l) => l());
}
