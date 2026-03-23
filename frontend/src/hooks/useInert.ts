/**
 * useInert — sets `inert` on `#bn-app-root` while a modal is open.
 *
 * Prevents Tab from reaching background content behind portaled modals.
 * Reference-counted so overlapping modals (rare but possible) work correctly:
 * `inert` is only removed when the last modal closes.
 *
 * @module useInert
 */

import { useEffect } from "react";

let inertCount = 0;

export function useInert(active: boolean): void {
  useEffect(() => {
    if (!active) return;
    const root = document.getElementById("bn-app-root");
    if (!root) return;
    inertCount++;
    root.setAttribute("inert", "");
    return () => {
      inertCount--;
      if (inertCount === 0) {
        root.removeAttribute("inert");
      }
    };
  }, [active]);
}

/** Reset counter — test-only. */
export function resetInertCount(): void {
  inertCount = 0;
}
