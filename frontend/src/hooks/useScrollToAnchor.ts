/**
 * useScrollToAnchor — retry-aware scroll to an anchor element.
 *
 * Port of `scrollToAnchor()` from global-nav.js. Retries up to 5 seconds
 * (50 × 100ms) for async-rendered targets (cross-tab navigation requires
 * the destination page to mount and fetch data before anchors exist).
 * Returns a stable callback.
 *
 * Once the target exists, the hook first offers it to the page with an in-page, cancelable
 * `bn:reveal-anchor` event (`detail.id`), like `bn:signal-focus`. A page that owns the target and
 * lands it its own way calls `preventDefault()`, and the hook stops: the Signals page does, for a
 * card id it knows, because a card may sit on a place it is not showing (`[hidden]`) and because
 * its first card lands with the place title (`scrollToCard`). Unclaimed, a visible target is
 * landed with `scrollToLand` as before; a hidden one is retried until it shows. Added for
 * decision #182 (9 Nov 2026), where a reopened study comes back to the card the reader was on.
 */

import { useCallback } from "react";
import { markArrived } from "../utils/arrival";
import { scrollToLand } from "../utils/scrollToLand";

export interface ScrollToAnchorOptions {
  block?: ScrollLogicalPosition;
  /** Flash the element on landing (utils/arrival.ts). */
  highlight?: boolean;
}

export function useScrollToAnchor() {
  return useCallback((anchorId: string, opts?: ScrollToAnchorOptions) => {
    const block = opts?.block ?? "start";
    const highlight = opts?.highlight ?? false;
    const maxRetries = 50; // 50 × 100ms = 5s
    let attempt = 0;

    function tryScroll() {
      const el = document.getElementById(anchorId);
      if (el) {
        const reveal = new CustomEvent("bn:reveal-anchor", { detail: { id: anchorId }, cancelable: true });
        // false: a page claimed it, showed the target and landed it.
        if (!window.dispatchEvent(reveal)) {
          if (highlight) markArrived(el);
          return;
        }
        if (!el.closest("[hidden]")) {
          scrollToLand(el, block);
          if (highlight) markArrived(el);
          return;
        }
      }
      attempt++;
      if (attempt < maxRetries) {
        setTimeout(tryScroll, 100);
      } else {
        // The anchor never appeared (a grouping without it, a filter hiding its group, an old
        // address): the caller's link landed nowhere, so say so where it can be seen.
        console.warn("scrollToAnchor: gave up waiting for", anchorId);
      }
    }

    requestAnimationFrame(tryScroll);
  }, []);
}
