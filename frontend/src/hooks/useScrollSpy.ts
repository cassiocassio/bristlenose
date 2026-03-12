/**
 * useScrollSpy — tracks which section heading is currently visible.
 *
 * Listens to `scroll` with `requestAnimationFrame` throttle.
 * Walks the list of IDs bottom-to-top — the first element with
 * `getBoundingClientRect().top <= threshold` is "active".
 *
 * Click intent override: when the user clicks a TOC link, the clicked
 * heading becomes "active" and stays active until the smooth scroll
 * animation finishes AND the user manually scrolls away. This handles
 * the edge case where the page can't scroll far enough to place the
 * clicked heading at the top (e.g. last few headings on the page).
 *
 * The override uses a two-phase approach:
 * 1. Immune phase (first 600ms): the override is unconditional — this
 *    covers the smooth scroll animation where getBoundingClientRect()
 *    can return glitched values in Safari.
 * 2. Sticky phase (after 600ms): the override stays active as long as
 *    the normal scroll-position algorithm wouldn't pick a DIFFERENT
 *    heading that's closer to the clicked one. It clears when the user
 *    scrolls far enough that the standard algorithm picks a heading
 *    that's more than 1 position away from the clicked heading.
 *
 * Returns the active ID (or null if none are above the threshold).
 *
 * @module useScrollSpy
 */

import { useEffect, useRef, useState } from "react";

/**
 * @param ids — ordered list of element IDs to monitor (top to bottom).
 * @param threshold — pixels from viewport top to consider "active" (default 100).
 * @param clickedIdRef — optional ref holding the ID the user clicked in the TOC.
 *   When set, this ID wins over scroll position until the user scrolls away.
 */
export function useScrollSpy(
  ids: string[],
  threshold = 100,
  clickedIdRef?: React.RefObject<string | null>,
): string | null {
  const [activeId, setActiveId] = useState<string | null>(null);
  const rafRef = useRef(0);
  // Timestamp when the user last clicked a TOC link — used to distinguish
  // the smooth-scroll animation period from subsequent manual scrolling.
  const clickTimeRef = useRef(0);

  useEffect(() => {
    if (ids.length === 0) {
      setActiveId(null);
      return;
    }

    /** Grace period covering smooth-scroll animation (Safari can return
     *  glitched getBoundingClientRect values during the animation). */
    const SCROLL_SETTLE_MS = 600;

    // Track the last-seen clickedIdRef value so we can detect new clicks.
    let lastClickedId: string | null = null;

    const onScroll = () => {
      window.cancelAnimationFrame(rafRef.current);
      rafRef.current = window.requestAnimationFrame(() => {
        // ── Detect new click intent ────────────────────────────────
        const clicked = clickedIdRef?.current ?? null;
        if (clicked !== lastClickedId) {
          // New click detected — record the timestamp.
          if (clicked) clickTimeRef.current = Date.now();
          lastClickedId = clicked;
        }

        // ── Standard scroll-position algorithm ────────────────────
        // Walk bottom-to-top: last heading above the threshold wins.
        let found: string | null = null;
        for (let i = ids.length - 1; i >= 0; i--) {
          const el = document.getElementById(ids[i]);
          if (el && el.getBoundingClientRect().top <= threshold) {
            found = ids[i];
            break;
          }
        }
        // Page at top: nothing crossed the threshold yet — default to first section.
        if (!found && ids.length > 0) {
          found = ids[0];
        }

        // ── Click intent override ─────────────────────────────────
        if (clicked && ids.includes(clicked)) {
          const elapsed = Date.now() - clickTimeRef.current;

          if (elapsed < SCROLL_SETTLE_MS) {
            // Phase 1 — immune: smooth scroll is probably still animating.
            // Don't trust getBoundingClientRect; just honour the click.
            setActiveId(clicked);
            return;
          }

          // Phase 2 — sticky: scroll has settled. Keep the override as
          // long as the standard algorithm picks a heading that's "nearby"
          // (within 1 position) of the clicked heading. This handles the
          // case where the page can't scroll far enough — the last heading
          // is clicked but the second-to-last is at the top.
          const clickedIdx = ids.indexOf(clicked);
          const foundIdx = found ? ids.indexOf(found) : -1;
          if (foundIdx >= 0 && Math.abs(foundIdx - clickedIdx) <= 1) {
            setActiveId(clicked);
            return;
          }

          // User has scrolled far away from the clicked heading — clear.
          if (clickedIdRef) clickedIdRef.current = null;
        }

        setActiveId(found);
      });
    };

    // Run once immediately so initial state is correct.
    onScroll();

    window.addEventListener("scroll", onScroll, { passive: true });
    return () => {
      window.removeEventListener("scroll", onScroll);
      // Guard: jsdom + fake timers can leave cancelAnimationFrame undefined.
      if (typeof window.cancelAnimationFrame === "function") {
        window.cancelAnimationFrame(rafRef.current);
      }
    };
  }, [ids, threshold, clickedIdRef]);

  return activeId;
}
