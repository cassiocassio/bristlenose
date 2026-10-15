/**
 * Whether the window is being resized right now, so expensive layout can wait until it stops.
 *
 * Two sources, one answer. In the Mac app, native says exactly when a live resize starts and ends
 * (`NSWindow.willStartLiveResize` / `didEndLiveResize`, pushed through `window.__bristlenose
 * .setLiveResize`) — which also covers what no pointer event can: tiling, full screen and the
 * green button. Everything else that resizes the page — a browser window, a web view resized by its
 * column toggling under the Mac's fit-to-width model — has no such event, so a resize counts as
 * over once no size change has arrived for SETTLE_MS (the usual trailing debounce). Native's exact
 * signal overrides the debounce only while it says a live resize is under way; the rest of the
 * time the debounce still answers (a review caught the first version switching it off for good
 * once native had spoken once).
 *
 * Consumers: the Screens board holds its cards still while this is true and glides them home
 * once when it goes false.
 */

/** How long without a size change before a browser resize counts as over. */
export const SETTLE_MS = 200;

let nativeLive = false;
let debounced = false;
let timer: ReturnType<typeof setTimeout> | null = null;
const listeners = new Set<() => void>();

function emit(): void {
  for (const l of listeners) l();
}

/** True while the window is being resized. */
export function isLiveResizing(): boolean {
  return nativeLive || debounced;
}

/** Subscribe to changes of `isLiveResizing()` (for useSyncExternalStore). */
export function subscribeLiveResize(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

/** Native's exact signal. While it says live, it alone decides: the debounce is not consulted,
 *  and its end is exact. A pending debounce is dropped at the start, so it cannot outlive it. */
export function setLiveResize(on: boolean): void {
  if (on === nativeLive) return;
  const was = isLiveResizing();
  nativeLive = on;
  if (on && timer !== null) {
    clearTimeout(timer);
    timer = null;
    debounced = false;
  }
  if (isLiveResizing() !== was) emit();
}

/** A size change the page observed. Starts or extends the browser's debounced resize. */
export function noteResize(): void {
  if (nativeLive) return; // native's live resize is answering exactly
  if (timer !== null) clearTimeout(timer);
  timer = setTimeout(() => {
    timer = null;
    if (debounced) {
      debounced = false;
      emit();
    }
  }, SETTLE_MS);
  if (!debounced) {
    debounced = true;
    emit();
  }
}

let installed = false;
/** Watch window resizes for the browser's debounce (idempotent). */
export function installLiveResizeWatch(): void {
  if (installed || typeof window === "undefined") return;
  installed = true;
  window.addEventListener("resize", noteResize, { passive: true });
}

/** Tests only. */
export function resetLiveResize(): void {
  nativeLive = false;
  debounced = false;
  if (timer !== null) clearTimeout(timer);
  timer = null;
  listeners.clear();
  installed = false;
}
