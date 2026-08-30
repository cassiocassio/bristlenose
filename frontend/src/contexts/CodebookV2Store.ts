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
 * NOT persisted to localStorage — it is a within-visit position, and a
 * researcher returning to the lens should land on their own tags rather than on
 * whichever framework they last inspected.
 *
 * @module CodebookV2Store
 */

import { useSyncExternalStore } from "react";

export interface CodebookV2State {
  /** `framework_id`, or `""` for the floor (the researcher's own tags). */
  selectedId: string;
}

let state: CodebookV2State = { selectedId: "" };

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

/** Select a codebook. `""` is the floor. */
export function selectCodebookV2(id: string): void {
  if (state.selectedId === id) return; // identity-stable: no needless re-render
  state = { selectedId: id };
  emit();
}

/**
 * Reset to the floor.
 *
 * Called when the lens unmounts so a later visit starts on the researcher's own
 * tags. Without it the module-level state outlives the component — which is the
 * cost of hoisting selection out of the tree, and worth paying once here rather
 * than surprising someone later.
 */
export function resetCodebookV2Selection(): void {
  selectCodebookV2("");
}

export function useCodebookV2Store(): CodebookV2State {
  return useSyncExternalStore(subscribe, getSnapshot);
}
