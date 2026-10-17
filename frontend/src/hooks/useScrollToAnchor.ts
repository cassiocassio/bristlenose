/**
 * useScrollToAnchor — retry-aware scroll to an anchor element.
 *
 * Port of `scrollToAnchor()` from global-nav.js. Retries up to 5 seconds
 * (50 × 100ms) for async-rendered targets (cross-tab navigation requires
 * the destination page to mount and fetch data before anchors exist).
 * Returns a stable callback.
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
        scrollToLand(el, block);
        if (highlight) markArrived(el);
        return;
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
