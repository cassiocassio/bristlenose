/**
 * Screen-reader announcements via a single aria-live region.
 *
 * Usage:
 *   import { announce } from "../utils/announce";
 *   announce("Quote starred");
 *
 * The live region DOM node is rendered by AnnounceRegion (mounted once
 * in AppLayout).  Messages are cleared after 5 seconds so the region
 * doesn't accumulate stale text.
 */

let el: HTMLElement | null = null;
let clearTimer: ReturnType<typeof setTimeout> | undefined;

/** Register the live-region DOM node (called once by AnnounceRegion). */
export function setAnnounceElement(node: HTMLElement | null): void {
  el = node;
}

/**
 * Push a message to the aria-live region.  Successive calls within the
 * same frame are coalesced — only the last message wins.
 */
export function announce(message: string): void {
  if (!el) return;
  // Clear first so repeated identical messages are re-announced.
  el.textContent = "";
  clearTimeout(clearTimer);
  // RAF ensures the empty-then-set is two distinct DOM states,
  // which AT engines need to detect a change.
  requestAnimationFrame(() => {
    if (!el) return;
    el.textContent = message;
    clearTimer = setTimeout(() => {
      if (el) el.textContent = "";
    }, 5000);
  });
}
