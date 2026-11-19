/**
 * CodebookV2Store — which codebook the v2 lens is showing.
 *
 * The v2 navigator lives in the standard left sidebar, which `AppLayout`
 * renders as a *sibling* of the lens, not a child — so the selection cannot be
 * component state the way it was while the rail sat inside the lens. Both sides
 * read it from here.
 *
 * Same shape as `SidebarStore` / `InspectorStore`: plain module-level state,
 * `useSyncExternalStore`, no context provider. The selection is deliberately
 * NOT persisted to localStorage — it is a within-session position: leaving the
 * lens for another and coming back returns to the codebook the researcher was
 * on (19 Nov 2026), but quitting the app or opening another project starts
 * fresh. Until they pick a row the selection is `null` and `resolveSelectedId`
 * supplies the landing: the Bristlenose UXR codebook if it is installed (the
 * house default put it there because the study shows screens), else the first
 * Default codebook (sentiment). It used to land on the empty "own tags" floor,
 * which a researcher who has not tagged anything yet finds blank.
 *
 * @module CodebookV2Store
 */

import { useSyncExternalStore } from "react";

export interface CodebookV2State {
  /** `framework_id`, `""` for the floor (the researcher's own tags), or `null` for "not chosen yet". */
  selectedId: string | null;
}

let state: CodebookV2State = { selectedId: null };
/** Which project `state` belongs to, so a remembered pick never crosses projects. */
let scope: string | null = null;

const listeners = new Set<() => void>();

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

function getSnapshot(): CodebookV2State {
  return state;
}

function emit(): void {
  for (const listener of listeners) listener();
}

/** Select a codebook. `""` is the floor; `null` forgets the choice. */
export function selectCodebookV2(id: string | null): void {
  if (state.selectedId === id) return; // identity-stable: no needless re-render
  state = { selectedId: id };
  emit();
}

/**
 * Forget the choice. The lens does NOT call this when it unmounts (a return
 * visit remembers); it is for tests and `scopeCodebookV2`.
 */
export function resetCodebookV2Selection(): void {
  selectCodebookV2(null);
}

/**
 * Tie the remembered pick to a project. A different project clears it: a
 * framework id picked in one study means nothing in the next.
 */
export function scopeCodebookV2(projectId: string): void {
  if (scope === projectId) return;
  const hadScope = scope !== null;
  scope = projectId;
  if (hadScope) selectCodebookV2(null);
}

/** The codebook a study that shows screens has installed for the researcher. */
const LANDING_PREFERENCE = "uxr";

/**
 * The row to show: the researcher's pick, else the first codebook that is not the
 * floor — the UXR codebook when installed, else the Default section's first row (what
 * auto-tagging found) — else the floor.
 * One rule for the rail and the page, so they cannot disagree about where we landed.
 */
export function resolveSelectedId(
  selected: string | null,
  books: ReadonlyArray<{ id: string; floor: boolean }>,
): string {
  if (selected !== null) return selected;
  const landing =
    books.find((b) => !b.floor && b.id === LANDING_PREFERENCE) ?? books.find((b) => !b.floor);
  return landing?.id ?? "";
}

export function useCodebookV2Store(): CodebookV2State {
  return useSyncExternalStore(subscribe, getSnapshot);
}
