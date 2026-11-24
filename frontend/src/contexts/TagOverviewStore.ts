/**
 * The tag sidebar overview's read and its view state, held for the page (landing plan Phase 6,
 * D12): a module-level store, as the other stores here (`frontend/CLAUDE.md`), so a sidebar that
 * remounts (a lens switch, the drag) draws the overview at once, as it was, with no second read
 * and no flash of the wrong wording.
 *
 * - **The read** (`GET /tag-overview`, stamped so a read from before a run's end is told from
 *   one after it): again after a run's end or a codebook change (`bn:tags-changed`,
 *   `codebook-changed`) and when a run's follow leaves the playback. Only the newest read
 *   started is applied, so a slow early answer never overwrites a later one.
 * - **The view** (open, split): the first read's, then the researcher's for this window. Two
 *   windows on one study each keep their own after that first read; the server remembers the
 *   last one written (Q3 (a)).
 * - **Opened by itself** this session: so a view write carries `auto_opened: true` from then on,
 *   and an auto-open whose own write failed cannot open the overview again.
 *
 * Nothing here runs in an exported report: proposals never leave the server.
 *
 * @module TagOverviewStore
 */

import { useSyncExternalStore } from "react";
import { getTagOverview, patchTagOverview } from "../utils/api";
import { isExportMode } from "../utils/exportData";
import type { TagOverviewResponse } from "../utils/types";
import { stampedRead } from "./AutoCodePlaybackView";

export interface TagOverviewState {
  read: TagOverviewResponse | null;
  /** The first read has answered, or failed: until then the line keeps its height, blank. */
  settled: boolean;
  view: { open: boolean; split: boolean } | null;
  /** The overview opened by itself in this window (D12). */
  autoOpened: boolean;
}

const INITIAL: TagOverviewState = { read: null, settled: false, view: null, autoOpened: false };

let state: TagOverviewState = INITIAL;
const listeners = new Set<() => void>();
let started = 0;
let listening = false;

function set(next: TagOverviewState): void {
  state = next;
  for (const l of listeners) l();
}

function isOverview(value: unknown): value is TagOverviewResponse {
  const v = value as TagOverviewResponse | null;
  return !!v && typeof v === "object" && Array.isArray(v.codebooks) && typeof v.open === "boolean";
}

/** Read the overview. Only the newest read started is applied. */
export function loadTagOverview(): void {
  if (isExportMode()) return;
  const mine = ++started;
  stampedRead(getTagOverview).then(
    (r) => {
      if (mine !== started) return;
      if (!isOverview(r)) {
        set({ ...state, settled: true });
        return;
      }
      set({ ...state, read: r, settled: true, view: state.view ?? { open: r.open, split: r.split } });
    },
    (err: unknown) => {
      if (mine !== started) return;
      // The overview is an extra: the line falls back to its plain words.
      console.warn("Tag overview: read failed", err);
      set({ ...state, settled: true });
    },
  );
}

function ensureListening(): void {
  if (listening || typeof document === "undefined") return;
  listening = true;
  document.addEventListener("bn:tags-changed", loadTagOverview);
  window.addEventListener("codebook-changed", loadTagOverview);
}

function subscribe(cb: () => void): () => void {
  listeners.add(cb);
  return () => listeners.delete(cb);
}

/** The store, read once per page: the first subscriber starts the read and the listeners. */
export function useTagOverview(): TagOverviewState {
  return useSyncExternalStore(subscribe, () => state, () => state);
}

/** Start the first read, once for the page. */
export function startTagOverview(): void {
  if (isExportMode()) return;
  ensureListening();
  if (started === 0) loadTagOverview();
}

function write(fields: Partial<Pick<TagOverviewResponse, "open" | "split" | "auto_opened">>): void {
  // A cosmetic view state: a failed write is logged by the request, never toasted.
  patchTagOverview(fields).catch(() => undefined);
}

/** The researcher opened, closed, merged or split the overview. Once the overview has opened by
 *  itself (here or as the server says), every write says so too, so a lost auto-open write
 *  heals with the next one. */
export function rememberView(view: { open: boolean; split: boolean }): void {
  set({ ...state, view });
  const healed = state.autoOpened || !!state.read?.auto_opened;
  write(healed ? { ...view, auto_opened: true } : view);
}

/** The overview opens by itself, once, after a first run (D12). */
export function autoOpenOverview(): void {
  if (state.autoOpened) return;
  set({ ...state, autoOpened: true, view: { open: true, split: state.view?.split ?? false } });
  write({ open: true, auto_opened: true });
}

/** Reset for tests. */
export function resetTagOverviewStore(): void {
  state = INITIAL;
  started = 0;
  for (const l of listeners) l();
}
