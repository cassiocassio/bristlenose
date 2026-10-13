/**
 * The tapestry's hover thumbnail: a still of the participant's screen under the timeline.
 *
 * Stepped, not scrubbed. A frame stands for a stretch of a participant turn (one per turn, one more
 * at each colour change inside it — utils/turn_frames.py), and the preview changes only when the
 * pointer has rested on another stretch for `restMs`. It opens `openMs` after the pointer enters the
 * participant track, at once if it closed less than `warmMs` ago (the tooltip warm-up rule), and
 * closes `graceMs` after the pointer leaves, so crossing from one session's timeline to the next
 * does not blink. Over a moderator turn it holds the last participant frame. Constants: the
 * `thumb` group in tapestryTuning.ts. Decided in experiments/session-tapestry/thumb-mockup.html.
 *
 * One controller for the page, not one per slice: the warm-up and the grace span sessions. Mouse
 * only, and the preview is aria-hidden — the transcript and the strip carry the same information.
 */

import { useSyncExternalStore } from "react";
import { apiGet } from "./api";
import { isExportMode } from "./exportData";
import { getTapestryTuning } from "./tapestryTuning";
import type { TurnFrame, TurnFramesResponse } from "./types";

/** The frame standing for the moment `sec`: the stretch containing it, else (over a moderator turn
 *  or a turn with no frame) the last frame before it, else the first. -1 with no frames. */
export function frameIndexAt(frames: TurnFrame[], sec: number): number {
  let last = -1;
  for (let i = 0; i < frames.length; i++) {
    const f = frames[i];
    if (sec >= f.a && sec < f.b) return i;
    if (f.b <= sec) last = i;
  }
  return last >= 0 ? last : frames.length ? 0 : -1;
}

// ── Frames: fetched the first time the pointer enters a slice, kept per (session, key) ──

const resolved = new Map<string, TurnFrame[]>();
const loading = new Set<string>();
/** Asked for and not got: not asked again until the key changes, or every pointer move would ask. */
const failed = new Set<string>();

/** The session's frames if they have arrived; otherwise starts fetching them and returns null. A
 *  new `framesKey` means new frames (the turns moved since). Never in an exported report, which
 *  carries no participant screens. */
export function framesFor(sessionId: string, framesKey: string | null | undefined): TurnFrame[] | null {
  if (!framesKey || isExportMode()) return null;
  const id = `${sessionId}\u0000${framesKey}`;
  const have = resolved.get(id);
  if (have) return have;
  if (!loading.has(id) && !failed.has(id)) {
    loading.add(id);
    apiGet<TurnFramesResponse>(`/sessions/${encodeURIComponent(sessionId)}/turn-frames`)
      .then((r) => {
        // Frames taken for turns that have since moved are never asked for again.
        for (const k of resolved.keys()) if (k.startsWith(`${sessionId}\u0000`)) resolved.delete(k);
        resolved.set(`${sessionId}\u0000${r.key}`, r.frames);
        // Newer frames than the timeline this slice draws (another window moved the turns): kept
        // for when the grid's next poll brings their key, and not shown against the old turns.
        if (r.key !== framesKey) {
          failed.add(id);
          return;
        }
        controller.frames(sessionId, r.frames);
      })
      .catch((err) => {
        failed.add(id);
        console.warn("SessionTapestry: no hover frames", err);
      })
      .finally(() => loading.delete(id));
  }
  return null;
}

// ── The controller ────────────────────────────────────────────────────────

export interface ThumbView {
  sessionId: string;
  frames: TurnFrame[];
  index: number;
  /** The pointer's clientX: the preview follows it along the timeline. */
  clientX: number;
}

let view: ThumbView | null = null;
const listeners = new Set<() => void>();
let armed = false;
let cur: { sessionId: string; frames: TurnFrame[] | null; sec: number; clientX: number } | null = null;
let shown: { sessionId: string; frames: TurnFrame[]; index: number } | null = null;
/** The frame a scheduled swap will show, so a swap is rescheduled only when the target moves. */
let pending: string | null = null;
let lastClose = -Infinity;
let tOpen: ReturnType<typeof setTimeout> | undefined;
let tSwap: ReturnType<typeof setTimeout> | undefined;
let tClose: ReturnType<typeof setTimeout> | undefined;

const indexOf = (c: NonNullable<typeof cur>) => (c.frames ? frameIndexAt(c.frames, c.sec) : -1);

function publish(): void {
  const next = shown && cur ? { ...shown, clientX: cur.clientX } : null;
  if (next?.sessionId === view?.sessionId && next?.index === view?.index && next?.clientX === view?.clientX
    && next?.frames === view?.frames) return;
  view = next;
  listeners.forEach((l) => l());
}

function show(): void {
  pending = null;
  if (!armed || !cur) return;
  const index = indexOf(cur);
  shown = index >= 0 && cur.frames ? { sessionId: cur.sessionId, frames: cur.frames, index } : null;
  publish();
}

function close(): void {
  armed = false;
  shown = null;
  lastClose = Date.now();
  publish();
}

const controller = {
  /** The pointer entered a session's participant track. */
  enter(): void {
    clearTimeout(tClose);
    if (armed) return;
    clearTimeout(tOpen);
    const { openMs, warmMs } = getTapestryTuning().thumb;
    const warm = Date.now() - lastClose < warmMs;
    tOpen = setTimeout(() => {
      armed = true;
      show();
    }, warm ? 0 : openMs);
  },
  /** The pointer is at `sec` on the session's timeline; `frames` is null while they load. */
  move(sessionId: string, frames: TurnFrame[] | null, sec: number, clientX: number): void {
    cur = { sessionId, frames, sec, clientX };
    if (!armed) return;
    const index = indexOf(cur);
    const target = index >= 0 ? `${sessionId}\u0000${index}` : null;
    const showing = shown && shown.frames === frames ? `${shown.sessionId}\u0000${shown.index}` : null;
    if (target === showing) {
      clearTimeout(tSwap); // back on the frame shown before a swap was due
      pending = null;
    } else if (target !== pending) {
      clearTimeout(tSwap);
      pending = target;
      tSwap = setTimeout(show, getTapestryTuning().thumb.restMs);
    }
    publish(); // the preview follows the pointer while the frame waits to change
  },
  /** Frames arrived for a session: show them at once if the preview is open on it. */
  frames(sessionId: string, frames: TurnFrame[]): void {
    if (!cur || cur.sessionId !== sessionId) return;
    cur = { ...cur, frames };
    if (armed) show();
  },
  /** The pointer left the participant track. */
  leave(): void {
    clearTimeout(tOpen);
    clearTimeout(tSwap);
    clearTimeout(tClose);
    pending = null;
    // Never opened: nothing to close, and crossing a lane on the way past must not count as a
    // close, or the next lane would open at once.
    if (!armed) return;
    tClose = setTimeout(close, getTapestryTuning().thumb.graceMs);
  },
  /** The slice closed or unmounted: never leave its preview behind. */
  forget(sessionId: string): void {
    if (cur?.sessionId !== sessionId && shown?.sessionId !== sessionId) return;
    clearTimeout(tOpen);
    clearTimeout(tSwap);
    clearTimeout(tClose);
    cur = null;
    if (shown) close();
    else armed = false;
  },
  /** Where a click should land when the preview shows a colour-change frame for this session:
   *  the change itself, which the caller moves 1 s earlier. Null otherwise. */
  changeAt(sessionId: string): number | null {
    if (!view || view.sessionId !== sessionId) return null;
    const f = view.frames[view.index];
    return f.change ? f.a : null;
  },
};

export const tapestryThumb = controller;

function subscribe(l: () => void): () => void {
  listeners.add(l);
  return () => {
    listeners.delete(l);
  };
}
const snapshot = () => view;

/** The preview showing now, or null. */
export function useTapestryThumb(): ThumbView | null {
  return useSyncExternalStore(subscribe, snapshot, snapshot);
}

/** Tests only. */
export function resetTapestryThumb(): void {
  clearTimeout(tOpen);
  clearTimeout(tSwap);
  clearTimeout(tClose);
  view = null;
  armed = false;
  cur = null;
  shown = null;
  pending = null;
  lastClose = -Infinity;
  resolved.clear();
  loading.clear();
  failed.clear();
}
