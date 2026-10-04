/**
 * The Discussion lens's navigator — the discussion guide — as a left panel.
 *
 * The first lens to remember its OWN open/closed setting instead of sharing
 * the one Quotes, Codebooks and Signals use (decided 4 Oct 2026). The guide and
 * the quotes are better as a pair, so it starts open and hiding Contents on
 * another lens does not hide it here. The fitting rule is the shared one
 * (`fitPanels`: the content keeps its floor, and a panel you have just opened
 * is never closed for you); the toolbar button, ⌥⌘L and `[` reach it through
 * the same actions as the other lenses' panels (AppLayout, useKeyboardShortcuts).
 *
 * The lens measures itself and reports what it shows and the width it wants;
 * AppLayout mirrors both to the Mac (`panel-state`), so the View menu reads
 * Show or Hide correctly and the projects column folds before the guide does.
 */

import { useSyncExternalStore } from "react";

const OPEN_KEY = "bn-discussion-guide-open";

interface GuidePanelState {
  /** The researcher's wish. Starts open. */
  wish: boolean;
  /** Opened by hand and not closed since: the fit never closes it (the
   *  shared store's `lastOpened` exemption). */
  justOpened: boolean;
  /** What the lens is showing (reported by the lens). */
  shown: boolean;
  /** The width the wished arrangement needs (reported by the lens). */
  wanted: number;
  /** A guide the Mac has just copied in, being read by a run: its file name.
   *  Never persisted — the report reloads when the run ends, which clears it. */
  pendingGuide: string | null;
}

function readWish(): boolean {
  try {
    return localStorage.getItem(OPEN_KEY) !== "false";
  } catch {
    return true; // private window or blocked storage: start open
  }
}

function writeWish(open: boolean): void {
  try {
    localStorage.setItem(OPEN_KEY, String(open));
  } catch {
    // as above: just not remembered
  }
}

let state: GuidePanelState = { wish: readWish(), justOpened: false, shown: false, wanted: 0, pendingGuide: null };
const listeners = new Set<() => void>();

function setState(next: GuidePanelState): void {
  if (
    next.wish === state.wish && next.justOpened === state.justOpened &&
    next.shown === state.shown && next.wanted === state.wanted && next.pendingGuide === state.pendingGuide
  ) return;
  state = next;
  listeners.forEach((l) => l());
}

function subscribe(l: () => void): () => void {
  listeners.add(l);
  return () => listeners.delete(l);
}

export function useDiscussionGuide(): GuidePanelState {
  return useSyncExternalStore(subscribe, () => state, () => state);
}

export function discussionGuideState(): GuidePanelState {
  return state;
}

/** Open or close it explicitly (View ▸ Show/Hide All Sidebars). */
export function setDiscussionGuideOpen(open: boolean): void {
  writeWish(open);
  setState({ ...state, wish: open, justOpened: open });
}

/** Toggle what is SHOWING, as `toggleToc` does: a guide the fit has folded
 *  reads as closed, so the toggle opens it. */
export function toggleDiscussionGuide(): void {
  setDiscussionGuideOpen(!state.shown);
}

/** The lens's report, every layout frame. Equality-guarded. */
export function reportDiscussionGuide(shown: boolean, wanted: number): void {
  setState({ ...state, shown, wanted });
}

/** The Mac's "a guide is being read" (AppLayout, menu action discussionGuidePending). */
export function setPendingGuide(file: string | null): void {
  setState({ ...state, pendingGuide: file || null });
}

/** For tests. */
export function resetDiscussionGuide(): void {
  try {
    localStorage.removeItem(OPEN_KEY);
  } catch {
    // as above
  }
  state = { wish: true, justOpened: false, shown: false, wanted: 0, pendingGuide: null };
  listeners.forEach((l) => l());
}
