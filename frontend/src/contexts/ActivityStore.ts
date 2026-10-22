/**
 * ActivityStore — module-level store for background job tracking.
 *
 * Owns the list of active jobs (e.g. AutoCode runs). Lives at the module
 * level so it survives React Router navigation — components subscribe via
 * `useActivityJobs()` which uses `useSyncExternalStore`.
 *
 * Same pattern as QuotesContext.tsx and SidebarStore.ts.
 */

import { useSyncExternalStore } from "react";
import type { NormalisedJobStatus } from "../components/ActivityChipStack";
import { getClipExtractionStatus, getScreensExportStatus, listAutoCodeJobs } from "../utils/api";
import { isExportMode } from "../utils/exportData";

export interface ActivityJobEntry {
  /** "catchup" = the on-enable delta re-apply (numberless chip; §4a). */
  type: "autocode" | "clips" | "catchup" | "screens";
  frameworkId: string;
  frameworkTitle: string;
  /** Which codebook lens started this job — the route its "View Report" action
   *  should return to.
   *
   *  Two lenses run side by side (D29), and the chip used to send every
   *  reader to `/report/codebook` regardless. A researcher who installed a
   *  codebook from v2 and clicked View Report landed in v1 — a different lens
   *  than the one they were working in, with no indication anything had moved.
   *  Absent means the shipped lens, which is the pre-v2 behaviour. */
  originRoute?: string;
  /** Total items (clips count) — used by clips jobs. */
  total?: number;
  /** A screens export that ends by putting its files on the clipboard (the Mac app's Copy
   *  Screens). */
  copyWhenDone?: boolean;
  /** The server's id for the clip or screens export this chip stands for. The server holds one
   *  export of each kind, so a chip whose id is no longer the server's has been replaced by a newer
   *  export, and must not show or copy it (RE#38). */
  jobId?: string;
  /** How the job ended, once this window's chip has seen it end. A chip carried across a reload
   *  with an outcome shows it and does nothing more: no read, no second copy. */
  outcome?: NormalisedJobStatus;
}

// ── Module-level state ───────────────────────────────────────────────────

let jobs = new Map<string, ActivityJobEntry>();
let snapshot = new Map<string, ActivityJobEntry>();
const listeners = new Set<() => void>();

function notify(): void {
  for (const l of listeners) l();
}

// ── The window's chips across a reload (RE#38) ───────────────────────────
//
// The list above lives in the page, so a reload emptied it. It is kept in session storage, which
// belongs to this window (a browser tab, or the Mac app's web view, which ⌘R and Retry reload in
// place) and goes with it: another window keeps its own list, and quitting the app or restarting
// the serve, which ends every export anyway, starts empty (the key names the serve, `serveStamp`).
// A dismissed chip has left the list, so it does not come back. Set by `rehydrateActivityJobs`,
// never in an exported report.

const STORAGE_PREFIX = "bristlenose-activity:";
let storageKey: string | null = null;
/** Where this window keeps its chips for `projectId`, or null when the page cannot tell its serve
 *  from another (no token): then they are not kept, rather than shared between studies. */
export function activityStorageKey(projectId: string): string | null {
  const stamp = serveStamp();
  return stamp ? `${STORAGE_PREFIX}${projectId}:${stamp}` : null;
}

/** The chips this load brought back from the last one; only they can stand for an export the
 *  server has since replaced (a chip started now names the export its own start returned). */
let carriedIds = new Set<string>();

/**
 * Which serve the page came from. Every serve says project 1, and the CLI's serves share one port
 * and so one origin, so a tab reloaded onto another study's serve would otherwise get this study's
 * chips. The bearer token is minted per serve start; only a digest of it goes into the key. With
 * no token there is nothing to tell serves apart by, so nothing is kept (`activityStorageKey`).
 */
function serveStamp(): string {
  const token = (window as unknown as Record<string, unknown>).__BRISTLENOSE_AUTH_TOKEN__;
  if (typeof token !== "string" || token === "") return "";
  let h = 0x811c9dc5;
  for (let i = 0; i < token.length; i++) h = Math.imul(h ^ token.charCodeAt(i), 0x01000193);
  return (h >>> 0).toString(36);
}

const TYPES = new Set<ActivityJobEntry["type"]>(["autocode", "clips", "catchup", "screens"]);
/** How a carried chip may have ended; "running" is not an ending, and such a chip would never poll. */
const ENDINGS = new Set<NormalisedJobStatus["status"]>(["completed", "partial", "failed", "cancelled"]);
let persistWarned = false;

function persist(): void {
  if (storageKey === null) return;
  try {
    sessionStorage.setItem(storageKey, JSON.stringify([...jobs]));
  } catch (err) {
    // No session storage (blocked, full): the window forgets its chips on a reload, as it used to.
    // An older list left behind would be worse than none (a chip settled since, carried back as
    // running, would copy again), so it goes too.
    try {
      sessionStorage.removeItem(storageKey);
    } catch {
      // Nothing more to do.
    }
    if (!persistWarned) {
      persistWarned = true;
      console.warn("Activity: the window's chips could not be kept for a reload", err);
    }
  }
}

/** The carried list, each entry checked: anything of another shape is left behind. */
function carried(key: string): [string, ActivityJobEntry][] {
  let raw: unknown;
  try {
    raw = JSON.parse(sessionStorage.getItem(key) ?? "[]");
  } catch {
    return [];
  }
  if (!Array.isArray(raw)) return [];
  const out: [string, ActivityJobEntry][] = [];
  for (const item of raw) {
    if (!Array.isArray(item) || typeof item[0] !== "string") continue;
    const e = item[1] as Partial<ActivityJobEntry> | null;
    if (!e || typeof e !== "object" || !TYPES.has(e.type as ActivityJobEntry["type"])) continue;
    if (typeof e.frameworkId !== "string" || typeof e.frameworkTitle !== "string") continue;
    const entry = { ...e } as ActivityJobEntry;
    if (entry.outcome && !ENDINGS.has(entry.outcome.status)) delete entry.outcome;
    out.push([item[0], entry]);
  }
  return out;
}

// ── Mutations ────────────────────────────────────────────────────────────

export function addJob(id: string, entry: ActivityJobEntry): void {
  jobs = new Map(jobs);
  jobs.set(id, entry);
  snapshot = jobs;
  persist();
  notify();
}

export function removeJob(id: string): void {
  if (!jobs.has(id)) return;
  jobs = new Map(jobs);
  jobs.delete(id);
  snapshot = jobs;
  persist();
  notify();
}

/** This page load's stamp, so a chip id is never one a carried chip already has: the producers'
 *  counters start again at every load, and a new run under a carried chip's id would inherit its
 *  finished state in the stack. */
const PAGE_LOAD = Date.now().toString(36);
let jobSeq = 0;

/** A new chip id for one run, e.g. `newJobId("clips")` or `newJobId("autocode:garrett")`. */
export function newJobId(kind: string): string {
  return `${kind}:${PAGE_LOAD}-${++jobSeq}`;
}

/** Record how a job ended, so a reload brings its chip back finished rather than asking again. */
export function settleJob(id: string, outcome: NormalisedJobStatus): void {
  const entry = jobs.get(id);
  if (!entry) return;
  jobs = new Map(jobs);
  jobs.set(id, { ...entry, outcome });
  snapshot = jobs;
  persist();
  notify();
}

/** Whether a chip for export `mine` may show the server's export `theirs`: not when the server
 *  names a different one. Absent on either side (an older chip, a server holding none) says nothing,
 *  and the chip's own read decides. */
export function sameExport(mine: string | undefined, theirs: string | null | undefined): boolean {
  return !mine || !theirs || mine === theirs;
}

// ── Subscription ─────────────────────────────────────────────────────────

export function getJobs(): Map<string, ActivityJobEntry> {
  return snapshot;
}

function subscribe(cb: () => void): () => void {
  listeners.add(cb);
  return () => listeners.delete(cb);
}

export function useActivityJobs(): Map<string, ActivityJobEntry> {
  return useSyncExternalStore(subscribe, getJobs, getJobs);
}

// ── Rehydration ──────────────────────────────────────────────────────────

let rehydratedProjectId: string | null = null;
let retried = false;

/** A read that failed on load is tried once more after this long; the page loads once. */
const REHYDRATE_RETRY_MS = 5_000;

/** Whether the page already has a chip still waiting on a job like this; a finished one does not
 *  stand for a newer run the server has started since. */
function hasJob(test: (job: ActivityJobEntry) => boolean): boolean {
  for (const job of jobs.values()) if (!job.outcome && test(job)) return true;
  return false;
}

/**
 * Put back the window's chips after a reload, once per project, when the report loads.
 *
 * First the chips this window carried across the reload (RE#38): exactly the list it had, in order,
 * a finished one with how it ended and a Copy Screens still a copy. That is what catches a job that
 * finished during the reload, which the server's reads below cannot tell from one that finished
 * long ago and was dismissed.
 *
 * Then the jobs the server is still running that the window has no chip for (R14): another window
 * started them, or the window had no session storage. A codebook's catch-up (switched back on with
 * new sessions to code) comes back as a catch-up chip. A job a producer has added meanwhile is kept,
 * not doubled (the server holds one export of each kind per project, and one AutoCode run per
 * codebook), and the producers remove a restored chip by type, as they do their own, when they
 * start the next run. A Copy Screens started in another window comes back here as a plain export:
 * only the window that asked copies.
 * Never rejects. A failed read adds nothing and all three are read once more a little later, since
 * the report loads once; what was restored by then is kept, not doubled.
 */
export function rehydrateActivityJobs(projectId: string): Promise<void> {
  if (isExportMode() || rehydratedProjectId === projectId) return Promise.resolve();
  rehydratedProjectId = projectId;
  const key = activityStorageKey(projectId);
  if (key !== null && storageKey !== key) {
    storageKey = key;
    const back = carried(storageKey).filter(([id]) => !jobs.has(id));
    carriedIds = new Set(back.map(([id]) => id));
    if (back.length > 0) {
      jobs = new Map([...back, ...jobs]);
      snapshot = jobs;
      notify();
    }
    persist();
  }
  // Started inside a promise, so a helper that throws rather than rejects is a failed read too.
  const read = <T>(fn: () => Promise<T>) => Promise.resolve().then(fn);
  return Promise.allSettled([
    read(() => getClipExtractionStatus()),
    read(() => getScreensExportStatus()),
    read(() => listAutoCodeJobs()),
  ]).then(([clips, screens, autocode]) => {
    if (rehydratedProjectId !== projectId) return;
    let failed = false;
    for (const [kind, r] of [["clips", clips], ["screens", screens], ["autocode", autocode]] as const) {
      if (r.status === "rejected") {
        failed = true;
        console.warn(`Activity: the ${kind} status read failed on load`, r.reason);
      }
    }
    if (failed && !retried) {
      retried = true;
      setTimeout(() => {
        if (rehydratedProjectId !== projectId) return;
        rehydratedProjectId = null;
        void rehydrateActivityJobs(projectId);
      }, REHYDRATE_RETRY_MS);
    }
    // A carried clip or screens chip whose export the server has since replaced goes: finished,
    // its Reveal would show the newer export; running, it would drop itself at its first read.
    for (const [kind, r] of [["clips", clips], ["screens", screens]] as const) {
      if (r.status !== "fulfilled") continue;
      for (const [id, j] of jobs) {
        if (!carriedIds.has(id) || j.type !== kind) continue;
        if (j.jobId && r.value?.job_id && j.jobId !== r.value.job_id) removeJob(id);
      }
    }
    // What is left of that kind names the running export (or carries no id), so it is its chip.
    if (clips.status === "fulfilled" && clips.value?.status === "running" && !hasJob((j) => j.type === "clips")) {
      addJob(newJobId("clips:restored"), {
        type: "clips", frameworkId: "", frameworkTitle: "", total: clips.value.total,
        ...(clips.value.job_id ? { jobId: clips.value.job_id } : {}),
      });
    }
    if (screens.status === "fulfilled" && screens.value?.status === "running" && !hasJob((j) => j.type === "screens")) {
      addJob(newJobId("screens:restored"), {
        type: "screens", frameworkId: "", frameworkTitle: "", total: screens.value.total, copyWhenDone: false,
        ...(screens.value.job_id ? { jobId: screens.value.job_id } : {}),
      });
    }
    const runs = autocode.status === "fulfilled" ? autocode.value?.jobs : undefined;
    if (!Array.isArray(runs)) return;
    for (const run of runs) {
      if (typeof run?.framework_id !== "string") continue;
      // A running job that finished once is a catch-up: switching a codebook back on is the
      // only path that sets a finished job running again (§4a). It comes back as the chip the
      // switch gave it (R12).
      if (run.completed_at) {
        if (hasJob((j) => j.type === "catchup" && j.frameworkId === run.framework_id)) continue;
        addJob(newJobId(`catchup:${run.framework_id}:restored`), {
          type: "catchup",
          frameworkId: run.framework_id,
          frameworkTitle: run.title,
        });
        continue;
      }
      if (hasJob((j) => j.type === "autocode" && j.frameworkId === run.framework_id)) continue;
      addJob(newJobId(`autocode:${run.framework_id}:restored`), {
        type: "autocode",
        frameworkId: run.framework_id,
        frameworkTitle: run.title,
        originRoute: "/report/codebook/",
      });
    }
  }).catch((err: unknown) => console.warn("Activity: restoring the chips on load failed", err));
}

/** Reset for tests. `keepSession` stands for a reload: the page's memory goes, the window's
 *  session storage stays. */
export function resetActivityStore({ keepSession = false }: { keepSession?: boolean } = {}): void {
  jobs = new Map();
  snapshot = jobs;
  rehydratedProjectId = null;
  storageKey = null;
  carriedIds = new Set();
  retried = false;
  persistWarned = false;
  if (!keepSession) {
    try {
      for (const key of Object.keys(sessionStorage)) {
        if (key.startsWith(STORAGE_PREFIX)) sessionStorage.removeItem(key);
      }
    } catch {
      // No session storage to clear.
    }
  }
  notify();
}
