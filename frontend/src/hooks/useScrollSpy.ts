/**
 * useScrollSpy — tracks which section heading is currently visible.
 *
 * Listens to `scroll` with `requestAnimationFrame` throttle.
 * Walks the list of IDs bottom-to-top — the first element with
 * `getBoundingClientRect().top <= threshold` is "active".
 *
 * Returns the active ID (or null if none are above the threshold).
 *
 * @module useScrollSpy
 */

import { useEffect, useRef, useState } from "react";

/**
 * @param ids — ordered list of element IDs to monitor (top to bottom).
 * @param threshold — pixels from viewport top to consider "active" (default 100).
 */
export function useScrollSpy(ids: string[], threshold = 100): string | null {
  const [activeId, setActiveId] = useState<string | null>(null);
  const rafRef = useRef(0);

  useEffect(() => {
    if (ids.length === 0) {
      setActiveId(null);
      return;
    }

    const onScroll = () => {
      cancelAnimationFrame(rafRef.current);
      rafRef.current = requestAnimationFrame(() => {
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
        setActiveId(found);
      });
    };

    // Run once immediately so initial state is correct.
    onScroll();

    window.addEventListener("scroll", onScroll, { passive: true });
    return () => {
      window.removeEventListener("scroll", onScroll);
      cancelAnimationFrame(rafRef.current);
    };
  }, [ids, threshold]);

  return activeId;
}
