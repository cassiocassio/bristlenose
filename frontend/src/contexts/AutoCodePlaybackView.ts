/**
 * What every view reads of an AutoCode run's live landing, and the doors into the playback.
 *
 * The playback itself (`AutoCodePlayback.ts`: polling, reconcile, pacing, the chip and the
 * decisions) is loaded only when a run starts landing on this page, so a report with no run in it
 * (and every exported report) never fetches it. This small module is what the views import:
 *
 * - the playback's snapshot (`usePlayback`): landed counts per codebook and the flashes, which
 *   the tag sidebar, the Codebook lens and its navigator, and the quote cards' flashes read;
 * - `useLiveCodebook` / `applyLiveCounts`, which fold the landed counts into a codebook read, and
 *   `stampedRead`, which remembers when that read started, so a read from after the run's end
 *   (which has the run in it) is left alone and the handover never double-counts or jumps;
 * - the reading position kept in WebKit (`restoreScrollAnchor`);
 * - thin doors to the playback (`followRun`, `holdForPlayback`, the decisions), which load it on
 *   first use and are no-ops while nothing lands.
 *
 * The landed tags themselves are `QuotesState.live` (`utils/liveTags.ts`).
 *
 * @module AutoCodePlaybackView
 */

import { useMemo, useSyncExternalStore } from "react";
import type { NormalisedJobStatus } from "../components/ActivityChipStack";
import { isExportMode } from "../utils/exportData";
import type { LiveTag } from "../utils/liveTags";
import type { AutoCodeJobStatus, CodebookResponse } from "../utils/types";

type Engine = typeof import("./AutoCodePlayback");

// ── Snapshot ─────────────────────────────────────────────────────────────

/** One landed accepted tag, with when the page first knew its quote carried it as a tag:
 *  null while it is only a proposal's status (a first apply before its cut), `-Infinity` for one
 *  any codebook read already counts. */
export interface LandedAccepted {
  tag: number;
  taggedAt: number | null;
}

export interface PlaybackFramework {
  kind: "first" | "catchup";
  handoverAt: number | null;
  /** Landed tentative, per tag definition. */
  tentative: ReadonlyMap<number, number>;
  accepted: readonly LandedAccepted[];
}

export interface PlaybackSnapshot {
  frameworks: ReadonlyMap<string, PlaybackFramework>;
  /** Tag definitions flashing as a tag lands on them accepted (Codebook lens rows). */
  flashingTagIds: ReadonlySet<number>;
  /** The same, by tag name (tag sidebar rows). */
  flashingTagNames: ReadonlySet<string>;
  /** `${dom_id}:${tag name}`, the quote card's `flashingTags` key. */
  flashingCardKeys: ReadonlySet<string>;
}

export const EMPTY_SNAPSHOT: PlaybackSnapshot = Object.freeze({
  frameworks: new Map(),
  flashingTagIds: new Set<number>(),
  flashingTagNames: new Set<string>(),
  flashingCardKeys: new Set<string>(),
});

let snapshot: PlaybackSnapshot = EMPTY_SNAPSHOT;
const listeners = new Set<() => void>();

function subscribe(cb: () => void): () => void {
  listeners.add(cb);
  return () => listeners.delete(cb);
}

export function getPlaybackSnapshot(): PlaybackSnapshot {
  return snapshot;
}

/** The playback's only write here. */
export function setPlaybackSnapshot(next: PlaybackSnapshot): void {
  if (next === snapshot) return;
  snapshot = next;
  for (const l of listeners) l();
}

export function usePlayback(): PlaybackSnapshot {
  return useSyncExternalStore(subscribe, getPlaybackSnapshot, getPlaybackSnapshot);
}

/** Whether a codebook row's tag is flashing as a tag lands on it accepted (Codebook lens). */
export function useLiveTagFlash(tagId: number): boolean {
  return useSyncExternalStore(subscribe, () => snapshot.flashingTagIds.has(tagId), () => false);
}

// ── Codebook counts ──────────────────────────────────────────────────────

/** When each codebook read started, so a view can tell whether its data has the run in it. */
const readStarted = new WeakMap<object, number>();

/** Read the codebook (or anything a view draws counts from) and remember when the read started. */
export function stampedRead<T extends object>(read: () => Promise<T>): Promise<T> {
  const at = Date.now();
  return read().then((value) => {
    if (value && typeof value === "object") readStarted.set(value, at);
    return value;
  });
}

/** Whether data read with `stampedRead` already has this run's end in it: read after the run
 *  handed over. Unstamped data is treated as older. */
export function snapshotHasRun(data: object | null | undefined, fw: PlaybackFramework): boolean {
  if (!data || fw.handoverAt === null) return false;
  const at = readStarted.get(data);
  return at !== undefined && at >= fw.handoverAt;
}

/** The landed accepted tags a codebook read cannot count yet: a proposal's status alone (a
 *  first apply before its cut), or a tag the page first saw after the read started. */
function acceptedSince(fw: PlaybackFramework, data: object): Map<number, number> {
  const since = readStarted.get(data) ?? -Infinity;
  const out = new Map<number, number>();
  for (const a of fw.accepted) {
    if (a.taggedAt === null || a.taggedAt > since) out.set(a.tag, (out.get(a.tag) ?? 0) + 1);
  }
  return out;
}

/**
 * A codebook with the playback's counts folded in, for every codebook the playback is landing
 * whose read predates the run's end: the tentative count is the landed tentative tags (the live
 * read lists exactly what the codebook's `tentative_count` counts), and the accepted count gains
 * the landed accepted tags the read cannot have counted. The codebook itself when nothing lands.
 */
export function applyLiveCounts(
  codebook: CodebookResponse | null,
  snap: PlaybackSnapshot,
): CodebookResponse | null {
  if (!codebook || snap.frameworks.size === 0) return codebook;
  let changed = false;
  const groups = codebook.groups.map((g) => {
    const fw = g.framework_id ? snap.frameworks.get(g.framework_id) : undefined;
    if (!fw || snapshotHasRun(codebook, fw)) return g;
    changed = true;
    const accepted = acceptedSince(fw, codebook);
    return {
      ...g,
      tags: g.tags.map((t) => ({
        ...t,
        tentative_count: fw.tentative.get(t.id) ?? 0,
        count: t.count + (accepted.get(t.id) ?? 0),
      })),
    };
  });
  if (!changed) return codebook;
  const out = { ...codebook, groups };
  const at = readStarted.get(codebook);
  if (at !== undefined) readStarted.set(out, at);
  return out;
}

/** `applyLiveCounts` for a component: the codebook it read, with the playback folded in. */
export function useLiveCodebook(codebook: CodebookResponse | null): CodebookResponse | null {
  const snap = usePlayback();
  return useMemo(() => applyLiveCounts(codebook, snap), [codebook, snap]);
}

/** A codebook's landed tentative total in place of `read`'s, or null when the playback does not
 *  speak for it (nothing lands, or the read already has the run's end). For the navigator's
 *  pending badge. */
export function liveTentativeTotal(snap: PlaybackSnapshot, frameworkId: string, read: object | null): number | null {
  const fw = snap.frameworks.get(frameworkId);
  if (!fw || snapshotHasRun(read, fw)) return null;
  let n = 0;
  for (const v of fw.tentative.values()) n += v;
  return n;
}

// ── Holding the reading position (WebKit) ────────────────────────────────
//
// Chromium and Firefox keep the reading position when content above it grows (CSS scroll
// anchoring). WebKit has no `overflow-anchor`, so a tag that wraps a card above the viewport, or
// a quote a filter takes in above it (D10), would move the page. There, the first quote card at
// the top of the window is measured before a landing and the page scrolled back by however far
// it moved (`components/PlaybackScrollKeeper.tsx`, mounted by AppLayout).

let anchor: { el: Element; top: number } | null = null;

function nativeAnchoring(): boolean {
  return typeof CSS !== "undefined" && typeof CSS.supports === "function" && CSS.supports("overflow-anchor", "auto");
}

/** The first quote card whose bottom is below the top of the window, found by bisection: cards
 *  are in reading order, and measuring every one would lay out the ones `content-visibility`
 *  skips. */
function topCard(): Element | null {
  const cards = document.querySelectorAll("blockquote.quote-card");
  let lo = 0;
  let hi = cards.length - 1;
  let found: Element | null = null;
  while (lo <= hi) {
    const mid = (lo + hi) >> 1;
    if (cards[mid].getBoundingClientRect().bottom > 0) {
      found = cards[mid];
      hi = mid - 1;
    } else {
      lo = mid + 1;
    }
  }
  return found;
}

/** Before a landing changes what the cards draw. */
export function captureScrollAnchor(): void {
  if (typeof document === "undefined" || nativeAnchoring() || window.scrollY <= 0) {
    anchor = null;
    return;
  }
  const el = topCard();
  anchor = el ? { el, top: el.getBoundingClientRect().top } : null;
}

/** After a landing has been drawn: scroll back by however far the anchor card moved. */
export function restoreScrollAnchor(): void {
  const a = anchor;
  anchor = null;
  if (!a || !a.el.isConnected) return;
  const moved = a.el.getBoundingClientRect().top - a.top;
  if (Math.abs(moved) >= 1) window.scrollBy(0, moved);
}

// ── Doors into the playback ──────────────────────────────────────────────

let engine: Engine | null = null;
let loading: Promise<Engine> | null = null;

/** The playback, loaded on first use. */
export function playbackEngine(): Promise<Engine> {
  if (engine) return Promise.resolve(engine);
  loading ??= import("./AutoCodePlayback").then((m) => (engine = m));
  return loading;
}

/** The playback if it has been loaded, for a door that must answer now. */
export function loadedEngine(): Engine | null {
  return engine;
}

/** Follow a run's landing on this page (an AutoCode or catch-up chip still running; `jobKey` is
 *  the chip's id). Nothing in an exported report. */
export function followRun(frameworkId: string, kind: "first" | "catchup", jobKey: string): void {
  if (isExportMode()) return;
  void playbackEngine().then((m) => m.followAutoCode(frameworkId, kind, jobKey));
}

/** The chip's status, held at "running" while the page lands a finished run's last tags (D11). */
export function holdForPlayback(
  frameworkId: string,
  jobKey: string,
  norm: NormalisedJobStatus,
  status?: AutoCodeJobStatus,
): NormalisedJobStatus {
  return engine ? engine.holdForPlayback(frameworkId, jobKey, norm, status) : norm;
}

/** Resolves once the run's tags have landed, or the bound from the server's finish has passed. */
export function whenPlayedOut(frameworkId: string, jobKey: string): Promise<void> {
  return engine ? engine.whenPlayedOut(frameworkId, jobKey) : Promise.resolve();
}

/** The run's end hands over to the ordinary data, just before its one reload. */
export function beginHandover(frameworkId: string, jobKey: string): void {
  engine?.beginHandover(frameworkId, jobKey);
}

/** Whether the server has finished this run (the chip only lands its last tags): nothing to stop. */
export function serverFinished(frameworkId: string, jobKey: string): boolean {
  return engine?.serverFinished(frameworkId, jobKey) ?? false;
}

/** A researcher's ✓ on a tentative tag the run is landing. */
export function acceptLanding(domId: string, t: LiveTag): void {
  void playbackEngine().then((m) => m.acceptLanding(domId, t));
}

/** A researcher's ✗ on a tentative tag the run is landing. */
export function denyLanding(domId: string, t: LiveTag): void {
  void playbackEngine().then((m) => m.denyLanding(domId, t));
}

/** A researcher's × on an accepted tag the run has landed. `ordinary` is the card's own removal,
 *  used when the quote's tags in the store already carry it. */
export function removeLanding(domId: string, t: LiveTag, storeHasTag: boolean, ordinary: () => void): void {
  void playbackEngine().then((m) => m.removeLanding(domId, t, storeHasTag, ordinary));
}

/** Reset for tests (the playback's own `resetPlayback` calls it). */
export function resetPlaybackView(): void {
  snapshot = EMPTY_SNAPSHOT;
  anchor = null;
  for (const l of listeners) l();
}
