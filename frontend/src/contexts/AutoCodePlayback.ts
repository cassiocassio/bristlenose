/**
 * AutoCodePlayback — the one store between a running AutoCode run and every view that shows its
 * tags (docs/design-autocode-landing-plan.md Phase 4, D7–D11, D19–D21).
 *
 * Loaded only when a run starts landing on this page (`AutoCodePlaybackView.playbackEngine`);
 * the views import the small `AutoCodePlaybackView` module, never this one.
 *
 * A first apply's proposals and its live acceptances are invisible to ordinary readers until the
 * run's cut (D32), so the live page reads them itself: while a run lands, the store polls the
 * live read (`getAutoCodeLive`), reconciles what it holds, queues every change and plays the
 * queue out at a paced rate (`utils/livePacing.ts`). What has been played is published:
 *
 * - into the quotes store as `QuotesState.live` (`utils/liveTags.ts`), which the quote cards, the
 *   tag sidebar's accepted counts and the filters fold into their data. It changes only when what
 *   is landed changes: at most once a landing, never for a read that brought nothing new, never
 *   for a flash ending;
 * - as the playback snapshot (`AutoCodePlaybackView`): counts and flashes, which the tag sidebar,
 *   the Codebook lens and its navigator, and the cards' flashes read.
 *
 * So no view shows a tag another has not played yet. When a run has settled and its queue is
 * played out, the activity chip says done (D11, `holdForPlayback`), its completion hands over
 * (`beginHandover`) and fires the one `codebook-changed` + `bn:tags-changed` of the run, and the
 * overlay is kept, deduplicated against the reloaded data, for `HANDOVER_GRACE_MS`; then it goes,
 * with nothing on screen moving. A follow belongs to one chip (`jobKey`): a handover from another
 * chip is ignored, and a new run of the codebook (a Resume) takes the follow over with what is
 * already landed, so nothing blinks or flashes again.
 *
 * A page opened mid-run, or reloaded, shows what is already saved at once, without flashing it
 * (the first read is not played). A hidden window pauses playback and catches up quickly when
 * shown. Under reduced motion or with the app's analysis animation off, tags land as they arrive,
 * unflashed. An exported report has no server: nothing here runs, and every view draws the
 * embedded data as it is.
 *
 * A researcher's own accept, deny or remove of a tag the run is landing shows at once, never
 * queued behind the playback, and is pinned (D2): a refusal caused by the playback lagging the
 * server is retried once as an explicit override, so the researcher's decision wins. During the
 * handover grace the decision goes the ordinary way (the quotes store's own write) and is only
 * pinned here, so it stays when the overlay goes.
 *
 * Nothing is kept in browser storage: a reload works the state out again from the server
 * (frontend/gotchas.md, `localStorage`).
 *
 * @module AutoCodePlayback
 */

import type { NormalisedJobStatus } from "../components/ActivityChipStack";
import { acceptProposal, denyProposal, getAutoCodeLive, toastSaveFailed } from "../utils/api";
import type { ApiError, DecidedStatus } from "../utils/api";
import { isExportMode } from "../utils/exportData";
import { newPacer, stepPacer } from "../utils/livePacing";
import type { PacerState } from "../utils/livePacing";
import { EMPTY_LIVE, liveTagAsTag, waitingKey } from "../utils/liveTags";
import type { LiveOverlay, LiveTag } from "../utils/liveTags";
import type { AutoCodeJobStatus, LiveProposalsResponse, ProposedTagResponse } from "../utils/types";
import {
  EMPTY_SNAPSHOT,
  captureScrollAnchor,
  resetPlaybackView,
  setPlaybackSnapshot,
} from "./AutoCodePlaybackView";
import type { LandedAccepted, PlaybackFramework } from "./AutoCodePlaybackView";
import { acceptProposedTag, denyProposedTag, getQuotesSnapshot, setLiveOverlay } from "./QuotesContext";

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
/** The longest, from the moment the server has finished a run, until its chip says done and the
 *  run's reload fires (D11): the chip's hold and the completion's wait share it. A playback that
 *  cannot finish (hidden window, a read failing) never keeps the chip running past it. The final
 *  wave takes about 3 s (`PACING.drain`), the last read up to a poll more. */
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
  /** The chip this follow belongs to. */
  jobKey: string;
  /** A first apply's live acceptances make no tag until its cut (D32); a catch-up makes its tags
   *  batch by batch. Decides what a codebook read already counts (`taggedAt`). */
  kind: "first" | "catchup";
  rows: Map<number, Row>;
  shown: Map<number, Shown>;
  /** When the page first knew each accepted row's quote carried it as a tag (`LandedAccepted`). */
  taggedAt: Map<number, number | null>;
  /** The researcher's own decisions on this page: shown at once and kept over the server's
   *  state until the overlay goes (D2). */
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
  /** When the server was first seen to have finished (D11's bound runs from here). */
  finishedAt: number | null;
  handoverAt: number | null;
}

const follows = new Map<string, Follow>();
/** One queue across every run that lands, so the flash limit holds for the screen. */
let queue: { fw: string; id: number }[] = [];
let pacer: PacerState = newPacer();
let catchingUp = false;
/** The queue has been put strongest first for the drain under way. */
let drainSorted = false;
let stepTimer: ReturnType<typeof setInterval> | null = null;
let lastStepAt = 0;
let wasHidden = false;

/** What is landed has changed since the overlay was last built. */
let overlayDirty = false;
let lastOverlay: LiveOverlay = EMPTY_LIVE;

// The D8 schedule.
let lastActiveAt: number | null = null;
let pulseTimer: ReturnType<typeof setTimeout> | null = null;

function desiredOf(f: Follow, id: number): Shown | null {
  const pin = f.pins.get(id);
  if (pin) return pin === "accepted" ? "accepted" : null;
  const row = f.rows.get(id);
  if (!row) return null;
  return row.status === "pending" ? "tentative" : row.status === "accepted" ? "accepted" : null;
}

function buildOverlay(): LiveOverlay {
  const byQuote: Record<string, LiveTag[]> = {};
  const held = new Set<number>();
  const waitingAccept = new Set<string>();
  for (const f of follows.values()) {
    for (const row of f.rows.values()) {
      held.add(row.id);
      const shown = f.shown.get(row.id);
      if (desiredOf(f, row.id) === "accepted" && shown !== "accepted") {
        waitingAccept.add(waitingKey(row.dom_id, row.tag_definition_id));
      }
      if (!shown) continue;
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
      });
    }
  }
  return held.size === 0 ? EMPTY_LIVE : { byQuote, held, waitingAccept };
}

/** Recompute what every view reads, and tell them: the overlay only when what is landed has
 *  changed, the snapshot (counts, flashes) every time. */
function publish(): void {
  if (overlayDirty) {
    overlayDirty = false;
    const overlay = buildOverlay();
    if (overlay !== lastOverlay) {
      lastOverlay = overlay;
      setLiveOverlay(overlay);
    }
  }
  const now = Date.now();
  const frameworks = new Map<string, PlaybackFramework>();
  const flashingTagIds = new Set<number>();
  const flashingTagNames = new Set<string>();
  const flashingCardKeys = new Set<string>();
  for (const f of follows.values()) {
    const tentative = new Map<number, number>();
    const accepted: LandedAccepted[] = [];
    for (const [id, shown] of f.shown) {
      const row = f.rows.get(id);
      if (!row) continue;
      const tag = row.tag_definition_id;
      if (shown === "tentative") {
        tentative.set(tag, (tentative.get(tag) ?? 0) + 1);
        continue;
      }
      accepted.push({ tag, taggedAt: f.taggedAt.get(id) ?? null });
      if ((f.flashUntil.get(id) ?? 0) > now) {
        flashingTagIds.add(tag);
        flashingTagNames.add(row.tag_name);
        flashingCardKeys.add(`${row.dom_id}:${row.tag_name}`);
      }
    }
    frameworks.set(f.frameworkId, { kind: f.kind, handoverAt: f.handoverAt, tentative, accepted });
  }
  setPlaybackSnapshot(
    frameworks.size === 0 ? EMPTY_SNAPSHOT : { frameworks, flashingTagIds, flashingTagNames, flashingCardKeys },
  );
  updatePulse();
}

// ── Following a run ──────────────────────────────────────────────────────

/**
 * Follow a codebook's run on this page: called for every AutoCode or catch-up chip still
 * running, with the chip's id. Idempotent for the same chip. Another chip of the codebook (a
 * Resume, a catch-up after the first apply) takes the follow over, keeping what is landed so
 * nothing blinks or flashes again. Nothing in an exported report.
 */
export function followAutoCode(frameworkId: string, kind: "first" | "catchup", jobKey: string): void {
  if (isExportMode()) return;
  const existing = follows.get(frameworkId);
  if (existing && existing.jobKey === jobKey) return;
  const f: Follow = {
    frameworkId,
    jobKey,
    kind,
    rows: existing ? existing.rows : new Map(),
    shown: existing ? existing.shown : new Map(),
    taggedAt: existing ? existing.taggedAt : new Map(),
    pins: existing ? existing.pins : new Map(),
    flashUntil: existing ? existing.flashUntil : new Map(),
    cursor: null,
    needFull: true,
    // Taking over: the next read is played against what is landed, not shown wholesale.
    started: existing ? existing.started : false,
    settled: false,
    stopped: false,
    reading: false,
    failures: 0,
    pollTimer: null,
    finishedAt: null,
    handoverAt: null,
  };
  if (existing) retire(existing);
  follows.set(frameworkId, f);
  lastActiveAt = null;
  ensureVisibilityListener();
  poll(f);
}

/** Stop a follow's reads; its rows and queue entries stay with whoever takes it over. */
function retire(f: Follow): void {
  if (f.pollTimer !== null) clearTimeout(f.pollTimer);
  f.pollTimer = null;
  f.stopped = true;
}

function current(f: Follow): boolean {
  return follows.get(f.frameworkId) === f;
}

function poll(f: Follow): void {
  if (f.reading || f.stopped || f.settled || !current(f)) return;
  f.reading = true;
  const since = f.needFull ? null : f.cursor;
  Promise.resolve()
    // A follow retired before the read started (a reset, a newer run) does not read.
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

/** Whether the quote already carries this tag in the quotes store (a hand-added tag, or one a
 *  reload brought): any codebook read counts it. */
function quoteCarries(row: Row): boolean {
  return (getQuotesSnapshot().tags[row.dom_id] ?? []).some((t) => t.id === row.tag_definition_id);
}

/** Note when the page first knew an accepted row's quote carried it as a tag. */
function noteTagged(f: Follow, row: Row, now: number): void {
  if (f.taggedAt.has(row.id) || desiredOf(f, row.id) !== "accepted") return;
  const isTag =
    f.pins.get(row.id) === "accepted" ||
    row.decided_by === "researcher" || row.decided_by === "unknown" ||
    f.kind === "catchup" || quoteCarries(row);
  // Before the page followed the run, any read may already count it.
  f.taggedAt.set(row.id, isTag ? (f.started && !quoteCarries(row) ? now : -Infinity) : null);
}

/**
 * Fold one live read into what the follow holds (the reconcile rule of the live read,
 * `routes/autocode.py` `get_proposals`): the new rows in full; every held row takes its state;
 * a held row with no state is gone; a held row whose state names another quote or tag is an id
 * SQLite reused, and so is a state at or below the cursor with no held row: both are fetched
 * again with a full read. The next read starts at `run.cursor`; the first read with
 * `run.settled` is the last. Nothing is published for a read that changed nothing.
 */
function reconcile(f: Follow, resp: LiveProposalsResponse): void {
  const now = Date.now();
  let changed = !f.started;
  const states = new Map(resp.states.map((s) => [s.id, s]));
  for (const p of resp.proposals) {
    const was = f.rows.get(p.id);
    if (
      !was || was.quote_id !== p.quote_id || was.tag_definition_id !== p.tag_definition_id ||
      was.status !== p.status || was.decided_by !== (p.decided_by ?? null)
    ) {
      changed = true;
    }
    f.rows.set(p.id, toRow(p));
  }
  let needFull = false;
  for (const [id, row] of f.rows) {
    const s = states.get(id);
    if (!s) {
      f.rows.delete(id);
      changed = true;
      continue;
    }
    if (s.quote_id !== row.quote_id || s.tag_definition_id !== row.tag_definition_id) {
      f.rows.delete(id);
      needFull = true;
      changed = true;
      continue;
    }
    if (row.status !== s.status || row.decided_by !== (s.decided_by ?? null)) {
      row.status = s.status;
      row.decided_by = s.decided_by ?? null;
      changed = true;
    }
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
      overlayDirty = true;
    }
  }
  for (const [id, row] of f.rows) {
    noteTagged(f, row, now);
    const want = desiredOf(f, id);
    if (!f.started) {
      // What is already saved when the page starts following shows at once, unflashed.
      if (want) f.shown.set(id, want);
      continue;
    }
    if (want !== (f.shown.get(id) ?? null) && !isQueued(f.frameworkId, id)) {
      queue.push({ fw: f.frameworkId, id });
    }
  }
  // Rows held or their states changed: `held` and `waitingAccept` with them.
  if (changed) overlayDirty = true;
  f.started = true;
  if (resp.run.settled && !needFull && !above) {
    f.settled = true;
    f.finishedAt ??= now;
    if (f.pollTimer !== null) clearTimeout(f.pollTimer);
    f.pollTimer = null;
    // The snapshot and the pulse change, not the overlay.
    changed = true;
  }
  if (!changed && !overlayDirty) return;
  captureScrollAnchor();
  publish();
  ensureClock();
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

function confidenceOf(q: { fw: string; id: number }): number {
  return follows.get(q.fw)?.rows.get(q.id)?.confidence ?? 0;
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
      if (drain && !drainSorted) {
        // The final wave plays strongest first (owner, 23 Nov 2026); arrivals keep their order.
        drainSorted = true;
        queue = queue
          .map((q, i) => ({ q, i }))
          .sort((a, b) => confidenceOf(b.q) - confidenceOf(a.q) || a.i - b.i)
          .map(({ q }) => q);
      }
      n = stepPacer(pacer, dt, queue.length, drain ? "drain" : "buffer");
    }
    if (n > 0 && land(n, flash, now)) changed = true;
    if (queue.length === 0) {
      catchingUp = false;
      drainSorted = false;
    }
  } else {
    stepPacer(pacer, dt, 0, "buffer");
    catchingUp = false;
    drainSorted = false;
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
function land(n: number, flash: boolean, now: number): boolean {
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
  if (landed > 0) overlayDirty = true;
  return landed > 0;
}

/** A follow handed over, past its grace and with nothing left to land, goes. */
function maybeEndFollows(): void {
  const now = Date.now();
  let gone = false;
  for (const f of [...follows.values()]) {
    if (
      f.handoverAt !== null && now - f.handoverAt >= HANDOVER_GRACE_MS &&
      !queue.some((q) => q.fw === f.frameworkId)
    ) {
      retire(f);
      follows.delete(f.frameworkId);
      gone = true;
    }
  }
  if (gone) {
    overlayDirty = true;
    publish();
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

function followFor(frameworkId: string, jobKey: string): Follow | null {
  const f = follows.get(frameworkId);
  return f && f.jobKey === jobKey ? f : null;
}

/**
 * Whether the activity chip of a run the server has finished should still say it is running:
 * yes while this page is landing the run's last tags, so "done" comes after the last one has
 * landed on screen (D11). Never in a hidden window, never once the page has stopped following
 * (a read failing, an export), never before a first read, and never past `CHIP_WAIT_MS` from the
 * first time the server was seen to have finished.
 */
export function playbackPending(frameworkId: string, jobKey: string): boolean {
  const f = followFor(frameworkId, jobKey);
  if (!f || !f.started || f.stopped || f.handoverAt !== null || isHidden()) return false;
  const now = Date.now();
  f.finishedAt ??= now;
  if (now - f.finishedAt >= CHIP_WAIT_MS) return false;
  return !(f.settled && !hasQueued(frameworkId));
}

/** Whether the server has finished this chip's run (the chip only lands its last tags). */
export function serverFinished(frameworkId: string, jobKey: string): boolean {
  return followFor(frameworkId, jobKey)?.finishedAt != null;
}

/**
 * A finished AutoCode run's chip status, held at "running" while the page is still landing the
 * run's last tags (`playbackPending`), and marked `landing` so the chip offers no Stop: the run
 * has ended, and a Stop would be sent to a finished job. Every other status passes through.
 */
export function holdForPlayback(
  frameworkId: string,
  jobKey: string,
  norm: NormalisedJobStatus,
  status?: AutoCodeJobStatus,
): NormalisedJobStatus {
  if (norm.status !== "completed" && norm.status !== "partial") return norm;
  if (!playbackPending(frameworkId, jobKey)) return norm;
  return {
    ...norm,
    status: "running",
    progressLabel: status ? `${status.processed_quotes}/${status.total_quotes}` : null,
    durationLabel: null,
    partialMessage: null,
    landing: true,
  };
}

/** Resolves once the run's tags have landed, the playback cannot go on, or `CHIP_WAIT_MS` has
 *  passed since the server was first seen to have finished: the same bound as the chip's hold,
 *  so a chip that held for it does not wait again. Never rejects. */
export function whenPlayedOut(frameworkId: string, jobKey: string): Promise<void> {
  return new Promise((resolve) => {
    const check = () => {
      const f = followFor(frameworkId, jobKey);
      if (f) f.finishedAt ??= Date.now();
      const done =
        !f || f.stopped || f.handoverAt !== null || isHidden() ||
        (!f.started && !f.reading) || (f.settled && !hasQueued(frameworkId)) ||
        Date.now() - (f.finishedAt ?? 0) >= CHIP_WAIT_MS;
      if (done) resolve();
      else setTimeout(check, 250);
    };
    check();
  });
}

/**
 * The run's end hands over to the ordinary data: called by the chip's completion just before it
 * fires the run's one `codebook-changed` + `bn:tags-changed`. Ignored from a chip the follow no
 * longer belongs to (a Stop's completion after a Resume took over). The overlay stays,
 * deduplicated against what the views read again, for `HANDOVER_GRACE_MS` and until its queue is
 * empty, then goes. A view that read its codebook after this moment has the run in it.
 */
export function beginHandover(frameworkId: string, jobKey: string): void {
  const f = followFor(frameworkId, jobKey);
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

/** Show a researcher's decision here at once and keep it over the server's state; no request. */
function pinLocal(f: Follow, id: number, pin: Pin): void {
  f.pins.set(id, pin);
  if (pin === "accepted" && !(f.taggedAt.get(id) != null)) f.taggedAt.set(id, Date.now());
  unqueue(f.frameworkId, id);
  if (pin === "accepted") f.shown.set(id, "accepted");
  else f.shown.delete(id);
  overlayDirty = true;
  publish();
}

const REFUSED_AS: Record<string, DecidedStatus> = {
  proposal_accepted: "accepted",
  proposal_denied: "denied",
};

/**
 * Send a researcher's decision on a row the playback holds. The row's status here may lag the
 * server (a live acceptance not read yet, the end's top-up), so a refusal that names the status
 * the row is in is the playback's lag, not someone else's decision: it is sent once more as an
 * explicit override of that status, and the researcher's decision wins (D2, D34). A decision on a
 * row already decided by the lines is sent as an override at once. Anything else puts the row
 * back as the server has it, and says so; a row gone (404) stays off.
 */
function decide(f: Follow, id: number, pin: Pin, send: (expected?: DecidedStatus) => Promise<void>): void {
  if (isExportMode()) return;
  const row = f.rows.get(id);
  const expected = row && row.status !== "pending" ? row.status : undefined;
  pinLocal(f, id, pin);
  const attempt = (exp: DecidedStatus | undefined, retried: boolean): void => {
    send(exp).catch((err: ApiError) => {
      const now = err?.status === 409 && err.reason ? REFUSED_AS[err.reason] : undefined;
      if (now && !retried) {
        attempt(now, true);
        return;
      }
      console.error("AutoCode: a decision on a landing tag failed:", err);
      if (!current(f)) return;
      if (err?.status === 404) return;
      toastSaveFailed(err);
      f.pins.delete(id);
      const want = desiredOf(f, id);
      if (want) f.shown.set(id, want);
      else f.shown.delete(id);
      overlayDirty = true;
      publish();
    });
  };
  attempt(expected, false);
}

/** ✓ on a tentative tag the run is landing: accepted on every view at once (the card flashes it
 *  as it does any accept). During the handover grace it is the quotes store's own accept. */
export function acceptLanding(domId: string, t: LiveTag): void {
  const f = followOf(t.id);
  if (!f) return;
  if (f.handoverAt !== null) {
    acceptProposedTag(domId, t.id, liveTagAsTag(t));
    pinLocal(f, t.id, "accepted");
    return;
  }
  decide(f, t.id, "accepted", (exp) => acceptProposal(t.id, exp));
}

/** ✗ on a tentative tag the run is landing. During the handover grace it is the quotes store's
 *  own deny. */
export function denyLanding(domId: string, t: LiveTag): void {
  const f = followOf(t.id);
  if (!f) return;
  if (f.handoverAt !== null) {
    denyProposedTag(domId, t.id);
    pinLocal(f, t.id, "denied");
    return;
  }
  decide(f, t.id, "denied", (exp) => denyProposal(t.id, exp));
}

/**
 * × on an accepted tag the run has landed. When the quote's tags in the store already carry it
 * (a catch-up's tag after a reload, the cut's after the handover, a researcher's own), it is the
 * card's own removal, and the playback only pins the exclusion so it does not draw the tag again.
 * Otherwise the tag is made only at the run's cut, so the proposal's acceptance is overridden
 * (the review dialog's ✗ on an accepted row, D34), which pins the exclusion on the server (D2).
 */
export function removeLanding(_domId: string, t: LiveTag, storeHasTag: boolean, ordinary: () => void): void {
  const f = followOf(t.id);
  if (!f) return;
  if (storeHasTag) {
    ordinary();
    pinLocal(f, t.id, "denied");
    return;
  }
  decide(f, t.id, "denied", (exp) => denyProposal(t.id, exp ?? "accepted"));
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

// ── Tests ────────────────────────────────────────────────────────────────

/** Reset for tests. */
export function resetPlayback(): void {
  for (const f of follows.values()) retire(f);
  follows.clear();
  queue = [];
  pacer = newPacer();
  catchingUp = false;
  drainSorted = false;
  stopClock();
  wasHidden = false;
  overlayDirty = false;
  lastOverlay = EMPTY_LIVE;
  lastActiveAt = null;
  if (pulseTimer !== null) clearTimeout(pulseTimer);
  pulseTimer = null;
  if (typeof document !== "undefined") document.documentElement.removeAttribute("data-autocode-tentative");
  setLiveOverlay(EMPTY_LIVE);
  resetPlaybackView();
}

/** The queue's length, for tests. */
export function _queuedForTest(): number {
  return queue.length;
}

/** The queue's rows in order, for tests. */
export function _queueForTest(): number[] {
  return queue.map((q) => q.id);
}
