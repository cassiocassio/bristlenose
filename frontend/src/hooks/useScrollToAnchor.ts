/**
 * useScrollToAnchor — retry-aware scroll to an anchor element.
 *
 * Port of `scrollToAnchor()` from global-nav.js. Retries up to 5 seconds
 * (50 × 100ms) for async-rendered targets (cross-tab navigation requires
 * the destination page to mount and fetch data before anchors exist).
 * Returns a stable callback.
 */

import { useCallback } from "react";

export interface ScrollToAnchorOptions {
  block?: ScrollLogicalPosition;
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
        el.scrollIntoView({ behavior: "smooth", block });
        if (highlight) {
          el.classList.remove("anchor-highlight");
          // Force reflow so animation restarts
          void el.offsetWidth;
          el.classList.add("anchor-highlight");
        }
        return;
      }
      attempt++;
      if (attempt < maxRetries) {
        setTimeout(tryScroll, 100);
      }
    }

    requestAnimationFrame(tryScroll);
  }, []);
}
