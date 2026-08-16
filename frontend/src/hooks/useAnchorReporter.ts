/**
 * useAnchorReporter — tells the native shell where the reader is on the page,
 * so reopening a project can land there instead of at the top.
 *
 * The desktop app restores the **lens** a project was left on from
 * `projects.json` (`LensMemory` on the Swift side). This is the finer half: the
 * position *within* that lens. It reports a heading id, never a pixel offset —
 * the content is mutable, and a stored offset into changed content lands
 * *somewhere* and looks deliberate, which is worse than landing at the top. A
 * heading id either resolves or falls back honestly.
 *
 * Only runs in the embedded (WKWebView) build. In a browser there is no shell
 * to tell, and `postAnchorChange` no-ops anyway; the early return keeps a scroll
 * listener off the page entirely.
 *
 * @module useAnchorReporter
 */

import { useEffect } from "react";

import { postAnchorChange } from "../shims/bridge";

/**
 * Which elements count as restorable positions, per lens.
 *
 * The table is the spec (`docs/design-workspace.md` §P3b), and deliberately
 * small:
 *
 * - **quotes** — the group headings. Sections and themes are the same UI object
 *   (both are `QuoteGroup`, both render `<h3 id={anchor}>`), so both count;
 *   watching only themes would make the Sections half of the lens report
 *   nothing and always restore to the top.
 * - **codebook** — the framework section headers, the direct sibling of a
 *   theme heading one lens over.
 * - **analysis**, **project** — absent on purpose. Decided 16 Aug 2026: these
 *   restore to the top. Neither has a stable structural position worth
 *   remembering, and inventing one would be a guess the reader can't predict.
 * - **sessions** — absent here because its position is a *route*
 *   (`/report/sessions/s3`), not a scroll offset. The native side already
 *   tracks it, in `SessionsRouteMemory`.
 *
 * A DOM selector rather than a marker attribute: an attribute has to be
 * remembered at every new call site, and this codebase has already been bitten
 * by that (`SectionHeading` exists because a class you must remember to type
 * gets forgotten). One table that can be read in a single screen is easier to
 * keep true than a convention spread across files — but it *is* coupled to the
 * id shapes above, so changing one means changing the other.
 */
const ANCHOR_SELECTORS: Record<string, string> = {
  quotes: "h3[id^='section-'], h3[id^='theme-']",
  codebook: "[id^='codebook-fw-']",
};

/** Distance from the viewport top at which a heading counts as "the one you're at". */
const THRESHOLD_PX = 120;

/** Quiet period after scrolling stops before the position is reported. */
const SETTLE_MS = 400;

/** The lens a report pathname is on, or null if it isn't a lens route. */
function lensFor(pathname: string): string | null {
  const match = /^\/report\/([a-z]+)/.exec(pathname);
  return match ? match[1] : null;
}

/**
 * Report the topmost heading that has scrolled past the threshold.
 *
 * @param pathname — the current route, which selects the lens.
 * @param embedded — whether we are inside the native shell.
 */
export function useAnchorReporter(pathname: string, embedded: boolean): void {
  useEffect(() => {
    if (!embedded) return;
    const lens = lensFor(pathname) ?? "";
    const selector = ANCHOR_SELECTORS[lens];
    if (!selector) {
      // A lens with no anchors restores to the top — say so explicitly rather
      // than leaving whatever the last lens reported standing.
      postAnchorChange(lens, null);
      return;
    }

    let settleTimer: ReturnType<typeof setTimeout> | undefined;
    let rafId = 0;
    let lastPosted: string | null | undefined;

    /**
     * Re-queries the DOM each time rather than caching an id list, because the
     * content arrives asynchronously — themes land after a fetch, and a list
     * captured at mount would be empty for the first render and stale after an
     * edit or a re-analysis.
     */
    function currentAnchor(): string | null {
      const elements = Array.from(document.querySelectorAll<HTMLElement>(selector));
      // Bottom-to-top: the last heading above the threshold is the one you are
      // reading under. Same walk as `useScrollSpy`, which does this for the
      // table of contents; kept separate because that hook's contract is an
      // ordered id list plus a click-intent override, neither of which applies
      // here.
      for (let i = elements.length - 1; i >= 0; i--) {
        if (elements[i].getBoundingClientRect().top <= THRESHOLD_PX) {
          return elements[i].id || null;
        }
      }
      return null; // above the first heading — the top of the page
    }

    function report() {
      const anchor = currentAnchor();
      // The shell persists this to disk, so don't tell it what it already
      // knows. `undefined` on the first pass means "nothing posted yet", which
      // is distinct from a posted `null`.
      if (anchor === lastPosted) return;
      lastPosted = anchor;
      postAnchorChange(lens, anchor);
    }

    function onScroll() {
      window.cancelAnimationFrame(rafId);
      rafId = window.requestAnimationFrame(() => {
        clearTimeout(settleTimer);
        settleTimer = setTimeout(report, SETTLE_MS);
      });
    }

    // Report once on arrival so switching lenses records where that lens
    // starts, without waiting for a scroll that may never come.
    settleTimer = setTimeout(report, SETTLE_MS);
    window.addEventListener("scroll", onScroll, { passive: true });

    return () => {
      window.removeEventListener("scroll", onScroll);
      clearTimeout(settleTimer);
      // Guard: jsdom with fake timers can leave cancelAnimationFrame undefined.
      if (typeof window.cancelAnimationFrame === "function") {
        window.cancelAnimationFrame(rafId);
      }
    };
  }, [pathname, embedded]);
}
