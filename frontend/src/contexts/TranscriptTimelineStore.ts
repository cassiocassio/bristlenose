/**
 * TranscriptTimelineStore — whether the transcript's sticky slot shows the journey chain or the
 * session timeline, and how much timeline (docs/mockups/transcript-timeline-toggle.html).
 *
 * Module-level, like SidebarStore and InspectorStore, so the transcript page, its split control
 * and AppLayout's native-menu handler (View ▸ Show Session Timeline, Timeline Detail ▸) share one
 * answer. `on` and `lanes` are a per-viewer reading mode in localStorage, and since decision #182
 * (9 Nov 2026) one of the R89 report preferences (`utils/nativePrefs.ts`), so the Mac app keeps it
 * past a relaunch; until then its web views forgot it on quit (owner, 17 Oct 2026). `available` is
 * not stored: the transcript page sets it while it shows a session that has a timeline, so the Mac
 * menu greys its rows everywhere else. Nor is `most`, the most detail this session can draw (no
 * quotes, no Sentiment lane; no theme, no Themes lane): the timeline draws `shownLanes()`, the lesser
 * of the two, and only the details up to `most` are offered, so the reader's choice waits, unchanged,
 * for the next session that has the lanes.
 */

import { useSyncExternalStore } from "react";
import type { TapestryLanes } from "../components/SessionTapestry";
import { storePref } from "../utils/nativePrefs";

/** Compact: sections and speakers. Standard: + sentiment. Full: + themes. The timeline's own type
 *  (type-only, so the lazy timeline stays off this store's chunk). */
export type TimelineLanes = TapestryLanes;
export const TIMELINE_LANES: readonly TimelineLanes[] = [2, 3, 5];
/** Standard: the most that stays under a third of a laptop window (the mockup's measurements). */
export const DEFAULT_LANES: TimelineLanes = 3;

export interface TranscriptTimelineState {
  on: boolean;
  lanes: TimelineLanes;
  available: boolean;
  most: TimelineLanes;
}

/** The detail the timeline draws: the reader's choice, down to what this session has. */
export function shownLanes(s: Pick<TranscriptTimelineState, "lanes" | "most">): TimelineLanes {
  return s.lanes <= s.most ? s.lanes : s.most;
}

/** The details worth offering: each one that draws a lane the one before it does not. One left
 *  (Compact) is no choice, so none are offered. */
export function offeredLanes(most: TimelineLanes): readonly TimelineLanes[] {
  const up = TIMELINE_LANES.filter((n) => n <= most);
  return up.length > 1 ? up : [];
}

/** The most detail a session can draw, from its quotes: Sentiment needs a quote, Themes a quote in
 *  a theme. Every session with a timeline has the speaker lanes. */
export function mostLanes(quotes: readonly { theme: string | null }[]): TimelineLanes {
  if (quotes.some((q) => q.theme)) return 5;
  return quotes.length > 0 ? 3 : 2;
}

const LS_KEY = "bn-transcript-timeline";

const isLanes = (n: unknown): n is TimelineLanes => n === 2 || n === 3 || n === 5;

function read(): TranscriptTimelineState {
  try {
    const raw = localStorage.getItem(LS_KEY);
    if (raw) {
      const v = JSON.parse(raw) as { on?: unknown; lanes?: unknown };
      return { on: v.on === true, lanes: isLanes(v.lanes) ? v.lanes : DEFAULT_LANES, available: false, most: 5 };
    }
  } catch {
    // Storage unavailable or unreadable: the chain, at the default detail.
  }
  return { on: false, lanes: DEFAULT_LANES, available: false, most: 5 };
}

let state: TranscriptTimelineState = read();
const listeners = new Set<() => void>();
const willChange = new Set<() => void>();

/** Called just before the slot changes (on/off or detail), whoever changed it — the split control
 *  or the Mac's View menu — so the page can note the reader's place while the old layout stands. */
export function onTimelineWillChange(fn: () => void): () => void {
  willChange.add(fn);
  return () => willChange.delete(fn);
}

function set(next: Partial<TranscriptTimelineState>): void {
  const merged = { ...state, ...next };
  if (merged.on === state.on && merged.lanes === state.lanes && merged.available === state.available
    && merged.most === state.most) return;
  const persist = merged.on !== state.on || merged.lanes !== state.lanes;
  if (persist) willChange.forEach((fn) => fn());
  state = merged;
  // Storage unavailable: `storePref` swallows it, and module state still carries it within this page.
  if (persist) storePref(LS_KEY, JSON.stringify({ on: state.on, lanes: state.lanes }));
  listeners.forEach((l) => l());
}

export function setTimelineOn(on: boolean): void {
  set({ on });
}

export function toggleTimeline(): void {
  set({ on: !state.on });
}

/** Choosing a detail also turns the timeline on: that is plainly what was meant. */
export function setTimelineLanes(lanes: TimelineLanes): void {
  if (isLanes(lanes)) set({ lanes, on: true });
}

/** The Mac's View menu: Show / Hide Session Timeline and Timeline Detail ▸ (MenuCommands.swift).
 *  True when the action was this store's. */
export function applyTimelineMenuAction(action: string, payload?: unknown): boolean {
  if (action === "toggleSessionTimeline") {
    toggleTimeline();
    return true;
  }
  if (action === "setSessionTimelineLanes") {
    const lanes = Number((payload as { lanes?: unknown } | undefined)?.lanes);
    if (isLanes(lanes)) setTimelineLanes(lanes);
    return true;
  }
  return false;
}

/** The transcript page, while it shows a session with a timeline: and how much it can draw. */
export function setTimelineAvailable(available: boolean, most: TimelineLanes = 5): void {
  set({ available, most: available ? most : 5 });
}

export function getTranscriptTimeline(): TranscriptTimelineState {
  return state;
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function useTranscriptTimeline(): TranscriptTimelineState {
  return useSyncExternalStore(subscribe, getTranscriptTimeline, getTranscriptTimeline);
}

/** Tests only. */
export function resetTranscriptTimelineStore(): void {
  try {
    localStorage.removeItem(LS_KEY);
  } catch {
    // nothing to clear
  }
  state = { on: false, lanes: DEFAULT_LANES, available: false, most: 5 };
  listeners.forEach((l) => l());
}
