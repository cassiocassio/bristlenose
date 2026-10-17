/**
 * TranscriptTimelineStore — whether the transcript's sticky slot shows the journey chain or the
 * session timeline, and how much timeline (docs/mockups/transcript-timeline-toggle.html).
 *
 * Module-level, like SidebarStore and InspectorStore, so the transcript page, its split control
 * and AppLayout's native-menu handler (View ▸ Show Session Timeline, Timeline Detail ▸) share one
 * answer. `on` and `lanes` are a per-viewer convenience in localStorage: the Mac app's web views
 * forget it on quit, and that is fine (owner, 17 Oct 2026). `available` is not stored: the
 * transcript page sets it while it shows a session that has a timeline, so the Mac menu greys its
 * rows everywhere else.
 */

import { useSyncExternalStore } from "react";
import type { TapestryLanes } from "../components/SessionTapestry";

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
}

const LS_KEY = "bn-transcript-timeline";

const isLanes = (n: unknown): n is TimelineLanes => n === 2 || n === 3 || n === 5;

function read(): TranscriptTimelineState {
  try {
    const raw = localStorage.getItem(LS_KEY);
    if (raw) {
      const v = JSON.parse(raw) as { on?: unknown; lanes?: unknown };
      return { on: v.on === true, lanes: isLanes(v.lanes) ? v.lanes : DEFAULT_LANES, available: false };
    }
  } catch {
    // Storage unavailable or unreadable: the chain, at the default detail.
  }
  return { on: false, lanes: DEFAULT_LANES, available: false };
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
  if (merged.on === state.on && merged.lanes === state.lanes && merged.available === state.available) return;
  const persist = merged.on !== state.on || merged.lanes !== state.lanes;
  if (persist) willChange.forEach((fn) => fn());
  state = merged;
  if (persist) {
    try {
      localStorage.setItem(LS_KEY, JSON.stringify({ on: state.on, lanes: state.lanes }));
    } catch {
      // Storage unavailable: module state still carries it within this page.
    }
  }
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

export function setTimelineAvailable(available: boolean): void {
  set({ available });
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
  state = { on: false, lanes: DEFAULT_LANES, available: false };
  listeners.forEach((l) => l());
}
