/**
 * AutoCodePlayback — the one store between a running AutoCode run and every view that shows its
 * tags (docs/design-autocode-landing-plan.md Phase 4, D7–D11, D19–D21).
 *
 * A first apply's proposals and its live acceptances are invisible to ordinary readers until the
 * run's cut (D32), so the live page reads them itself: while a run lands, the store polls the
 * live read (`getAutoCodeLive`), reconciles what it holds, queues every change and plays the
 * queue out at a paced rate (`utils/livePacing.ts`). What has been played is published:
 *
 * - into the quotes store as `QuotesState.live` (`utils/liveTags.ts`), which the quote cards, the
 *   tag sidebar's accepted counts and the filters fold into their data;
 * - as this store's snapshot, which the tag sidebar's tentative counts, the Codebook lens's
 *   counts and its rows' flashes read (`useLiveCodebook`, `useLiveTagFlash`), and which the tag
 *   sidebar overview (Phase 6) will read for its histograms (`liveProposals`).
 *
 * So no view shows a tag another has not played yet. When a run has settled and its queue is
 * played out, the activity chip says done (D11, `playbackPending`), its completion hands over
 * (`beginHandover`) and fires the one `codebook-changed` + `bn:tags-changed` of the run, and the
 * overlay is kept, deduplicated against the reloaded data, until every view has read the
 * ordinary data again; then it goes, with nothing on screen moving.
 *
 * A page opened mid-run, or reloaded, shows what is already saved at once, without flashing it
 * (the first read is not played). A hidden window pauses playback and catches up quickly when
 * shown. Under reduced motion or with the app's analysis animation off, tags land as they arrive,
 * unflashed. An exported report has no server: nothing here runs, and every view draws the
 * embedded data as it is.
 *
 * A researcher's own accept or deny of a tag the run is landing shows at once, never queued
 * behind the playback, and is pinned (D2).
 *
 * Module-level state with `useSyncExternalStore`, the pattern of `QuotesContext` and
 * `ActivityStore`. Nothing is kept in browser storage: a reload works the state out again from
 * the server (frontend/gotchas.md, `localStorage`).
 *
 * @module AutoCodePlayback
 */

import { useMemo, useSyncExternalStore } from "react";
import { acceptProposal, denyProposal, getAutoCodeLive, toastSaveFailed } from "../utils/api";
import type { ApiError } from "../utils/api";
import { isExportMode } from "../utils/exportData";
import { newPacer, stepPacer } from "../utils/livePacing";
import type { PacerState } from "../utils/livePacing";
import { EMPTY_LIVE } from "../utils/liveTags";
import type { LiveOverlay, LiveTag } from "../utils/liveTags";
import type { NormalisedJobStatus } from "../components/ActivityChipStack";
import type {
  AutoCodeJobStatus,
  CodebookResponse,
  LiveProposalsResponse,
  ProposedTagResponse,
} from "../utils/types";
import { setLiveOverlay } from "./QuotesContext";

// ── Timings ──────────────────────────────────────────────────────────────

/** How often the live read is polled while a run lands: the activity chip's cadence. */
export const LIVE_POLL_MS = 2000;
/** The playback clock's step. */
const STEP_MS = 50;
/** The `badge-accept-flash` animation (atoms/badge.css), with a frame to spare. */
export const FLASH_MS = 450;
/** Live reads failing in a row after which the page stops following the run: the chip still
 *  ends, and the run's end reloads the ordinary data as before Phase 4. */
const MAX_READ_FAILURES = 5;
/** The longest the activity chip waits, after the server has finished, for the playback to land
 *  the last tag (D11). A playback that cannot finish (hidden window, a read failing) never keeps
 *  the chip running past it. */
export const CHIP_WAIT_MS = 20_000;
/** How long the overlay is kept after the run's end hands over, so every view has read the
 *  ordinary data again before it goes. */
export const HANDOVER_GRACE_MS = 10_000;
/** D8: tentative tags pulse during a run and for a minute after, then calm to a still dashed
 *  outline over 30 s (atoms/badge.css, `data-autocode-tentative`). */
export const PULSE_AFTER_MS = 60_000;
export const CALM_MS = 30_000;

// ── State ────────────────────────────────────────────────────────────────

type Shown = "tentative" | "accepted";
type Pin = "accepted" | "denied";

interface Row {
  id: number;
  quote_id: number;
  dom_id: string;
  tag_definition_id: number;
  tag_name: string;
  group_name: string;
  colour_set: string;
  colour_index: number;
  confidence: number;
  rationale: string;
  status: ProposedTagResponse["status"];
  decided_by: ProposedTagResponse["decided_by"];
}

interface Follow {
  frameworkId: string;
  /** A first apply's rows are hidden from ordinary readers until its cut (D32); a catch-up's are
   *  not, which decides what the Codebook lens's counts add (`liveCounts`). */
  kind: "first" | "catchup";
  rows: Map<number, Row>;
  shown: Map<number, Shown>;
  /** Accepted when the page started following (a catch-up's earlier tags, already counted). */
  acceptedAtStart: Set<number>;
  /** The researcher's own decisions on this page: shown at once and kept over the server's
   *  state until the run's end (D2). */
  pins: Map<number, Pin>;
  flashUntil: Map<number, number>;
  cursor: number | null;
  needFull: boolean;
  started: boolean;
  settled: boolean;
  stopped: boolean;
  reading: boolean;
  failures: number;
  pollTimer: ReturnType<typeof setTimeout> | null;
  /** When the chip first asked whether to wait (D11's bound runs from here). */
  chipWaitFrom: number | null;
  handoverAt: number | null;
}

const follows = new Map<string, Follow>();
/** One queue across every run that lands, so the flash limit holds for the screen. */
let queue: { fw: string; id: number }[] = [];
let pacer: PacerState = newPacer();
let catchingUp = false;
let stepTimer: ReturnType<typeof setInterval> | null = null;
let lastStepAt = 0;
let wasHidden = false;
let landings = 0;

// The D8 schedule.
let lastActiveAt: number | null = null;
let pulseTimer: ReturnType<typeof setTimeout> | null = null;

// ── Snapshot ─────────────────────────────────────────────────────────────

export interface LiveCounts {
  /** Landed tentative, per tag definition. */
  tentative: Map<number, number>;
  /** Landed accepted that the ordinary data cannot have yet, per tag definition. */
  accepted: Map<number, number>;
}

export interface PlaybackFramework {
  kind: "first" | "catchup";
  handoverAt: number | null;
  counts: LiveCounts;
}

export interface PlaybackSnapshot {
  frameworks: ReadonlyMap<string, PlaybackFramework>;
  /** Tag definitions flashing as a tag lands on them accepted. */
  flashingTagIds: ReadonlySet<number>;
  /** The same, by tag name, for the tag sidebar. */
  flashingTagNames: ReadonlySet<string>;
  /** Landings so far (the scroll keeper restores after each). */
  landings: number;
}

const EMPTY_SNAPSHOT: PlaybackSnapshot = {
  frameworks: new Map(),
  flashingTagIds: new Set(),
  flashingTagNames: new Set(),
  landings: 0,
};

let snapshot: PlaybackSnapshot = EMPTY_SNAPSHOT;
const listeners = new Set<() => void>();

function subscribe(cb: () => void): () => void {
  listeners.add(cb);
  return () => listeners.delete(cb);
}

export function getPlaybackSnapshot(): PlaybackSnapshot {
  return snapshot;
}

export function usePlayback(): PlaybackSnapshot {
  return useSyncExternalStore(subscribe, getPlaybackSnapshot, getPlaybackSnapshot);
}

function desiredOf(f: Follow, id: number): Shown | null {
  const pin = f.pins.get(id);
  if (pin) return pin === "accepted" ? "accepted" : null;
  const row = f.rows.get(id);
  if (!row) return null;
  return row.status === "pending" ? "tentative" : row.status === "accepted" ? "accepted" : null;
}

/** Recompute what every view reads, and tell them. */
function publish(): void {
  const now = Date.now();
  const byQuote: Record<string, LiveTag[]> = {};
  const held = new Set<number>();
  const waitingAccept = new Set<string>();
  const frameworks = new Map<string, PlaybackFramework>();
  const flashingTagIds = new Set<number>();
  const flashingTagNames = new Set<string>();
  for (const f of follows.values()) {
    const counts: LiveCounts = { tentative: new Map(), accepted: new Map() };
    for (const row of f.rows.values()) {
      held.add(row.id);
      const shown = f.shown.get(row.id);
      if (desiredOf(f, row.id) === "accepted" && shown !== "accepted") {
        waitingAccept.add(`${row.dom_id}|${row.tag_name.toLowerCase()}`);
      }
      if (!shown) continue;
      const flash = (f.flashUntil.get(row.id) ?? 0) > now;
      (byQuote[row.dom_id] ??= []).push({
        id: row.id,
        dom_id: row.dom_id,
        tag_definition_id: row.tag_definition_id,
        tag_name: row.tag_name,
        group_name: row.group_name,
        colour_set: row.colour_set,
        colour_index: row.colour_index,
        confidence: row.confidence,
        rationale: row.rationale,
        shown,
        flash,
      });
      const tag = row.tag_definition_id;
      if (shown === "tentative") {
        counts.tentative.set(tag, (counts.tentative.get(tag) ?? 0) + 1);
      } else if (f.kind === "first" || !f.acceptedAtStart.has(row.id)) {
        counts.accepted.set(tag, (counts.accepted.get(tag) ?? 0) + 1);
      }
      if (flash && shown === "accepted") {
        flashingTagIds.add(tag);
        flashingTagNames.add(row.tag_name);
      }
    }
    frameworks.set(f.frameworkId, { kind: f.kind, handoverAt: f.handoverAt, counts });
  }
  const overlay: LiveOverlay = held.size === 0 ? EMPTY_LIVE : { byQuote, held, waitingAccept };
  snapshot = { frameworks, flashingTagIds, flashingTagNames, landings };
  setLiveOverlay(overlay);
  for (const l of listeners) l();
  updatePulse();
}

// ── Following a run ──────────────────────────────────────────────────────

/**
 * Follow a codebook's run on this page: called for every AutoCode or catch-up chip still
 * running. Idempotent while the run is followed; a new run of a codebook whose last run is
 * handing over starts a fresh follow. Nothing in an exported report.
 */
export function followAutoCode(frameworkId: string, kind: "first" | "catchup"): void {
  if (isExportMode()) return;
  const existing = follows.get(frameworkId);
  if (existing && existing.handoverAt === null && !existing.stopped) return;
  if (existing) dropFollow(existing);
  const f: Follow = {
    frameworkId,
    kind,
    rows: new Map(),
    shown: new Map(),
    acceptedAtStart: new Set(),
    pins: new Map(),
    flashUntil: new Map(),
    cursor: null,
    needFull: true,
    started: false,
    settled: false,
    stopped: false,
    reading: false,
    failures: 0,
    pollTimer: null,
    chipWaitFrom: null,
    handoverAt: null,
  };
  follows.set(frameworkId, f);
  lastActiveAt = null;
  ensureVisibilityListener();
  poll(f);
}

function current(f: Follow): boolean {
  return follows.get(f.frameworkId) === f;
}

function poll(f: Follow): void {
  if (f.reading || f.stopped || f.settled || !current(f)) return;
  f.reading = true;
  const since = f.needFull ? null : f.cursor;
  // Started inside a promise, so a helper that throws rather than rejects is a failed read too.
  Promise.resolve()
    // A follow dropped before the read started (a reset, a newer run) does not read.
    .then(() => (current(f) ? getAutoCodeLive(f.frameworkId, since) : null))
    .then((resp) => {
      if (!current(f)) return;
      if (!resp || !Array.isArray(resp.states) || !Array.isArray(resp.proposals) || !resp.run) {
        // Not the live read's answer (an older server): following cannot work, so the run's
        // tags show when it ends, as before.
        console.warn("AutoCode: the live read answered without its states; not following the run");
        f.stopped = true;
        publish();
        return;
      }
      f.failures = 0;
      reconcile(f, resp);
    })
    .catch((err: unknown) => {
      if (!current(f)) return;
      f.failures += 1;
      if (f.failures >= MAX_READ_FAILURES) {
        console.warn("AutoCode: the live read keeps failing; the run's tags show when it ends", err);
        f.stopped = true;
        publish();
      }
    })
    .finally(() => {
      f.reading = false;
      if (current(f) && !f.stopped && !f.settled && f.handoverAt === null) {
        f.pollTimer = setTimeout(() => {
          f.pollTimer = null;
          poll(f);
        }, LIVE_POLL_MS);
      }
    });
}

function toRow(p: ProposedTagResponse): Row {
  return {
    id: p.id,
    quote_id: p.quote_id,
    dom_id: p.dom_id,
    tag_definition_id: p.tag_definition_id,
    tag_name: p.tag_name,
    group_name: p.group_name,
    colour_set: p.colour_set,
    colour_index: p.colour_index,
    confidence: p.confidence,
    rationale: p.rationale,
    status: p.status,
    decided_by: p.decided_by ?? null,
  };
}

function isQueued(fw: string, id: number): boolean {
  return queue.some((q) => q.fw === fw && q.id === id);
}

function unqueue(fw: string, id: number): void {
  queue = queue.filter((q) => !(q.fw === fw && q.id === id));
}

/**
 * Fold one live read into what the follow holds (the reconcile rule of the live read,
 * `routes/autocode.py` `get_proposals`): the new rows in full; every held row takes its state;
 * a held row with no state is gone; a held row whose state names another quote or tag is an id
 * SQLite reused, and so is a state at or below the cursor with no held row: both are fetched
 * again with a full read. The next read starts at `run.cursor`; the first read with
 * `run.settled` is the last.
 */
function reconcile(f: Follow, resp: LiveProposalsResponse): void {
  const states = new Map(resp.states.map((s) => [s.id, s]));
  for (const p of resp.proposals) f.rows.set(p.id, toRow(p));
  let needFull = false;
  for (const [id, row] of f.rows) {
    const s = states.get(id);
    if (!s) {
      f.rows.delete(id);
      continue;
    }
    if (s.quote_id !== row.quote_id || s.tag_definition_id !== row.tag_definition_id) {
      f.rows.delete(id);
      needFull = true;
      continue;
    }
    row.status = s.status;
    row.decided_by = s.decided_by ?? null;
  }
  const cursor = resp.run.cursor;
  let above = false;
  for (const s of resp.states) {
    if (f.rows.has(s.id)) continue;
    if (cursor !== null && s.id <= cursor) needFull = true;
    else above = true;
  }
  f.needFull = needFull;
  f.cursor = cursor;

  // A row gone, or reused by another quote or tag: off the screen at once (a removal, not a
  // landing).
  for (const id of [...f.shown.keys()]) {
    if (!f.rows.has(id)) {
      f.shown.delete(id);
      unqueue(f.frameworkId, id);
    }
  }
  for (const id of f.rows.keys()) {
    const want = desiredOf(f, id);
    if (!f.started) {
      // What is already saved when the page starts following shows at once, unflashed.
      if (want) f.shown.set(id, want);
      if (want === "accepted") f.acceptedAtStart.add(id);
      continue;
    }
    if (want !== (f.shown.get(id) ?? null) && !isQueued(f.frameworkId, id)) {
      queue.push({ fw: f.frameworkId, id });
    }
  }
  f.started = true;
  if (resp.run.settled && !needFull && !above) {
    f.settled = true;
    if (f.pollTimer !== null) clearTimeout(f.pollTimer);
    f.pollTimer = null;
  }
  captureScrollAnchor();
  publish();
  ensureClock();
}

function dropFollow(f: Follow): void {
  if (f.pollTimer !== null) clearTimeout(f.pollTimer);
  f.pollTimer = null;
  f.stopped = true;
  queue = queue.filter((q) => q.fw !== f.frameworkId);
  if (current(f)) follows.delete(f.frameworkId);
}

// ── The clock ────────────────────────────────────────────────────────────

function isHidden(): boolean {
  return typeof document !== "undefined" && document.visibilityState === "hidden";
}

/** Flashes and pacing are motion: off under reduced motion and with the app's "Show animation
 *  while analysing" off (`data-analysis-animation`, atoms/shimmer.css). */
function motionAllowed(): boolean {
  const reduced =
    typeof window !== "undefined" &&
    (window.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches ?? false);
  const off =
    typeof document !== "undefined" &&
    document.documentElement.getAttribute("data-analysis-animation") === "off";
  return !reduced && !off;
}

function ensureClock(): void {
  if (stepTimer !== null) return;
  lastStepAt = Date.now();
  stepTimer = setInterval(step, STEP_MS);
}

function stopClock(): void {
  if (stepTimer !== null) clearInterval(stepTimer);
  stepTimer = null;
}

function anyFlashing(now: number): boolean {
  for (const f of follows.values()) for (const t of f.flashUntil.values()) if (t > now) return true;
  return false;
}

function settledFor(fw: string): boolean {
  const f = follows.get(fw);
  return !f || f.settled || f.stopped;
}

function step(): void {
  const now = Date.now();
  const dt = Math.min(0.25, Math.max(0, (now - lastStepAt) / 1000));
  lastStepAt = now;
  let changed = expireFlashes(now);
  if (isHidden()) {
    // Paused; shown again, what waited is caught up quickly.
    wasHidden = true;
    if (changed) publish();
    return;
  }
  if (wasHidden) {
    wasHidden = false;
    if (queue.length > 0) catchingUp = true;
  }
  if (queue.length > 0) {
    let n: number;
    let flash = true;
    if (!motionAllowed()) {
      n = queue.length;
      flash = false;
    } else {
      const drain = catchingUp || queue.every((q) => settledFor(q.fw));
      n = stepPacer(pacer, dt, queue.length, drain ? "drain" : "buffer");
    }
    if (n > 0) {
      land(n, flash, now);
      changed = true;
    }
    if (queue.length === 0) catchingUp = false;
  } else {
    stepPacer(pacer, dt, 0, "buffer");
    catchingUp = false;
  }
  if (changed) publish();
  if (queue.length === 0 && !anyFlashing(now)) {
    stopClock();
    maybeEndFollows();
  }
}

function expireFlashes(now: number): boolean {
  let changed = false;
  for (const f of follows.values()) {
    for (const [id, until] of f.flashUntil) {
      if (until <= now) {
        f.flashUntil.delete(id);
        changed = true;
      }
    }
  }
  return changed;
}

/** Land the next `n` changes from the queue: one landing, every tag in it at once. */
function land(n: number, flash: boolean, now: number): void {
  captureScrollAnchor();
  let landed = 0;
  while (landed < n && queue.length > 0) {
    const { fw, id } = queue.shift()!;
    const f = follows.get(fw);
    if (!f) continue;
    const want = desiredOf(f, id);
    const was = f.shown.get(id) ?? null;
    if (want === was) continue;
    if (want) f.shown.set(id, want);
    else f.shown.delete(id);
    if (flash && want === "accepted") f.flashUntil.set(id, now + FLASH_MS);
    landed += 1;
  }
  if (landed > 0) landings += 1;
}

/** A follow whose run has settled and whose queue is empty is done; it waits for its chip to
 *  hand over. */
function maybeEndFollows(): void {
  const now = Date.now();
  for (const f of [...follows.values()]) {
    if (f.handoverAt !== null && now - f.handoverAt >= HANDOVER_GRACE_MS && !queue.some((q) => q.fw === f.frameworkId)) {
      dropFollow(f);
      publish();
    }
  }
}

// ── Visibility ───────────────────────────────────────────────────────────

let visibilityListening = false;
function ensureVisibilityListener(): void {
  if (visibilityListening || typeof document === "undefined") return;
  visibilityListening = true;
  document.addEventListener("visibilitychange", onVisibility);
}

function onVisibility(): void {
  if (isHidden()) {
    wasHidden = true;
    return;
  }
  if (queue.length > 0) {
    wasHidden = false;
    catchingUp = true;
    ensureClock();
  }
}

// ── The chip (D11) and the handover ──────────────────────────────────────

function hasQueued(fw: string): boolean {
  return queue.some((q) => q.fw === fw);
}

/**
 * Whether the activity chip of a run the server has finished should still say it is running:
 * yes while this page is landing the run's last tags, so "done" comes after the last one has
 * landed on screen (D11). Never in a hidden window, never once the page has stopped following
 * (a read failing, an export), and never past `CHIP_WAIT_MS` from the first time it is asked.
 */
export function playbackPending(frameworkId: string): boolean {
  const f = follows.get(frameworkId);
  // Nothing read yet means nothing to land: the chip does not wait on a read.
  if (!f || !f.started || f.stopped || f.handoverAt !== null || isHidden()) return false;
  const now = Date.now();
  f.chipWaitFrom ??= now;
  if (now - f.chipWaitFrom >= CHIP_WAIT_MS) return false;
  return !(f.settled && !hasQueued(frameworkId));
}

/**
 * A finished AutoCode run's chip status, held at "running" while the page is still landing the
 * run's last tags (D11; `playbackPending` bounds the wait and never holds in a hidden window or
 * after the page stopped following). Every other status passes through.
 */
export function holdForPlayback(
  frameworkId: string,
  norm: NormalisedJobStatus,
  status?: AutoCodeJobStatus,
): NormalisedJobStatus {
  if (norm.status !== "completed" && norm.status !== "partial") return norm;
  if (!playbackPending(frameworkId)) return norm;
  return {
    ...norm,
    status: "running",
    progressLabel: status ? `${status.processed_quotes}/${status.total_quotes}` : null,
    durationLabel: null,
    partialMessage: null,
  };
}

/** Resolves once the run's tags have landed, the playback cannot go on, or `limitMs` has passed.
 *  Never rejects. For a chip that ended without waiting (a Stop, a failure), before it hands
 *  over. */
export function whenPlayedOut(frameworkId: string, limitMs = CHIP_WAIT_MS): Promise<void> {
  const deadline = Date.now() + limitMs;
  return new Promise((resolve) => {
    const check = () => {
      const f = follows.get(frameworkId);
      const done =
        !f || f.stopped || f.handoverAt !== null || isHidden() ||
        (!f.started && !f.reading) || (f.settled && !hasQueued(frameworkId));
      if (done || Date.now() >= deadline) resolve();
      else setTimeout(check, 250);
    };
    check();
  });
}

/**
 * The run's end hands over to the ordinary data: called by the chip's completion just before it
 * fires the run's one `codebook-changed` + `bn:tags-changed`. The overlay stays, deduplicated
 * against what the views read again, for `HANDOVER_GRACE_MS` and until its queue is empty, then
 * goes. A view that read its codebook after this moment has the run in it
 * (`snapshotHasRun`).
 */
export function beginHandover(frameworkId: string): void {
  const f = follows.get(frameworkId);
  if (!f || f.handoverAt !== null) return;
  f.handoverAt = Date.now();
  if (f.pollTimer !== null) clearTimeout(f.pollTimer);
  f.pollTimer = null;
  publish();
  setTimeout(() => {
    maybeEndFollows();
    // Still landing (a hidden window): the clock ends it when the queue empties.
    if (current(f) && hasQueued(frameworkId)) ensureClock();
  }, HANDOVER_GRACE_MS);
}

// ── A researcher's own decision on a tag the run is landing (D2) ─────────

function followOf(id: number): Follow | null {
  for (const f of follows.values()) if (f.rows.has(id)) return f;
  return null;
}

function reviewedElsewhere(err: ApiError | null | undefined): boolean {
  return !!err?.reason?.startsWith("proposal_") || err?.status === 404;
}

function decide(id: number, pin: Pin, call: () => Promise<void>, onFail: (f: Follow, err: ApiError) => void): void {
  if (isExportMode()) return;
  const f = followOf(id);
  if (!f) return;
  f.pins.set(id, pin);
  unqueue(f.frameworkId, id);
  if (pin === "accepted") f.shown.set(id, "accepted");
  else f.shown.delete(id);
  publish();
  call().catch((err: ApiError) => {
    console.error("AutoCode: a decision on a landing tag failed:", err);
    if (!current(f)) return;
    onFail(f, err);
    const want = desiredOf(f, id);
    if (want) f.shown.set(id, want);
    else f.shown.delete(id);
    publish();
  });
}

/** Accept a tentative tag the run is landing: it turns accepted on every view at once (the card
 *  flashes it as it does any accept). Accepted elsewhere keeps it; denied elsewhere or gone drops
 *  it; anything else puts it back, and says so. */
export function acceptLiveProposal(id: number): void {
  decide(id, "accepted", () => acceptProposal(id), (f, err) => {
    if (err?.reason === "proposal_accepted") return;
    toastSaveFailed(err);
    if (err?.reason === "proposal_denied" || err?.status === 404) f.pins.set(id, "denied");
    else f.pins.delete(id);
  });
}

/** Exclude a tentative tag the run is landing, as the card's ✗ does. */
export function denyLiveProposal(id: number): void {
  decide(id, "denied", () => denyProposal(id), (f, err) => {
    if (err?.reason === "proposal_denied") return;
    toastSaveFailed(err);
    if (err?.reason === "proposal_accepted") f.pins.set(id, "accepted");
    else if (!reviewedElsewhere(err)) f.pins.delete(id);
    // Gone (404): it stays off the screen.
  });
}

/** Remove an accepted tag the run has landed and the quote does not carry yet (its tag is made at
 *  the run's cut): the excluding override of the review dialog's ✗ on an accepted row (D34),
 *  which takes the tag off when AutoCode made it and pins the exclusion (D2). */
export function removeLiveAccepted(id: number): void {
  decide(id, "denied", () => denyProposal(id, "accepted"), (f, err) => {
    if (err?.reason === "proposal_denied") return;
    toastSaveFailed(err);
    f.pins.delete(id);
  });
}

// ── What the views read ──────────────────────────────────────────────────

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

/**
 * A codebook with the playback's counts folded in, for every codebook the playback is landing
 * whose read predates its end: the tentative count is the landed tentative tags (the live read
 * lists exactly what the codebook's `tentative_count` counts once the run has been cut), and the
 * accepted count gains the landed accepted tags the ordinary data cannot have yet. The codebook
 * itself when nothing is landing.
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
    return {
      ...g,
      tags: g.tags.map((t) => ({
        ...t,
        tentative_count: fw.counts.tentative.get(t.id) ?? 0,
        count: t.count + (fw.counts.accepted.get(t.id) ?? 0),
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

/** Whether a codebook row's tag is flashing as a tag lands on it accepted (Codebook lens). */
export function useLiveTagFlash(tagId: number): boolean {
  return useSyncExternalStore(
    subscribe,
    () => snapshot.flashingTagIds.has(tagId),
    () => false,
  );
}

/** The run's landed proposals with their confidence and how they show, for a chart that grows
 *  live (the tag sidebar overview, Phase 6). */
export function liveProposals(frameworkId: string): { id: number; tag_definition_id: number; confidence: number; shown: Shown }[] {
  const f = follows.get(frameworkId);
  if (!f) return [];
  const out: { id: number; tag_definition_id: number; confidence: number; shown: Shown }[] = [];
  for (const [id, shown] of f.shown) {
    const row = f.rows.get(id);
    if (row) out.push({ id, tag_definition_id: row.tag_definition_id, confidence: row.confidence, shown });
  }
  return out;
}

// ── D8: the pulse schedule ───────────────────────────────────────────────

function setPulse(state: "pulse" | "calm" | null): void {
  if (typeof document === "undefined") return;
  const root = document.documentElement;
  const now = root.getAttribute("data-autocode-tentative");
  if (state === null) {
    if (now !== null) root.removeAttribute("data-autocode-tentative");
  } else if (now !== state) {
    root.setAttribute("data-autocode-tentative", state);
  }
}

/** Tentative tags pulse while a run lands and for a minute after, then calm over 30 s to a still
 *  dashed outline (D8). The CSS gates the motion itself on reduced motion and the analysis
 *  animation setting. */
function updatePulse(): void {
  if (isExportMode()) return;
  const now = Date.now();
  const landing = [...follows.values()].some(
    (f) => !f.stopped && f.handoverAt === null && !(f.settled && !hasQueued(f.frameworkId)),
  );
  if (pulseTimer !== null) clearTimeout(pulseTimer);
  pulseTimer = null;
  if (landing) {
    lastActiveAt = null;
    setPulse("pulse");
    return;
  }
  if (lastActiveAt === null) {
    // Nothing has landed on this page: still, as a study with no run in it.
    if (!document.documentElement.hasAttribute("data-autocode-tentative")) return;
    lastActiveAt = now;
  }
  const since = now - lastActiveAt;
  if (since < PULSE_AFTER_MS) {
    setPulse("pulse");
    pulseTimer = setTimeout(updatePulse, PULSE_AFTER_MS - since);
  } else if (since < PULSE_AFTER_MS + CALM_MS) {
    setPulse("calm");
    pulseTimer = setTimeout(updatePulse, PULSE_AFTER_MS + CALM_MS - since);
  } else {
    setPulse(null);
  }
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
    const r = cards[mid].getBoundingClientRect();
    if (r.bottom > 0) {
      found = cards[mid];
      hi = mid - 1;
    } else {
      lo = mid + 1;
    }
  }
  return found;
}

function captureScrollAnchor(): void {
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

// ── Tests ────────────────────────────────────────────────────────────────

/** Reset for tests. */
export function resetPlayback(): void {
  for (const f of follows.values()) if (f.pollTimer !== null) clearTimeout(f.pollTimer);
  follows.clear();
  queue = [];
  pacer = newPacer();
  catchingUp = false;
  stopClock();
  wasHidden = false;
  landings = 0;
  lastActiveAt = null;
  if (pulseTimer !== null) clearTimeout(pulseTimer);
  pulseTimer = null;
  anchor = null;
  snapshot = EMPTY_SNAPSHOT;
  if (typeof document !== "undefined") document.documentElement.removeAttribute("data-autocode-tentative");
  setLiveOverlay(EMPTY_LIVE);
  for (const l of listeners) l();
}

/** The queue's length, for tests. */
export function _queuedForTest(): number {
  return queue.length;
}
