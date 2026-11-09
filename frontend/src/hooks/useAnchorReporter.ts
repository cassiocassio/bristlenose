/**
 * useAnchorReporter — tells the native shell where the reader is on the page,
 * so reopening a project can land there instead of at the top.
 *
 * The desktop app restores the **lens** a project was left on from
 * `projects.json` (`LensMemory` on the Swift side). This is the finer half: the
 * position *within* that lens. It reports an element id, never a pixel offset —
 * the content is mutable, and a stored offset into changed content lands
 * *somewhere* and looks deliberate, which is worse than landing at the top. An
 * element id either resolves or falls back honestly.
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
 * Which elements count as restorable positions, per lens: the element the
 * reader was on (decision #182, option B, 9 Nov 2026; `docs/design-workspace.md`
 * §P3b). Native applies them in `LensAnchor.swift`; the two tables name each
 * other and have to agree.
 *
 * - **quotes** — the quote card (`<blockquote id="q-…">`, `quote.dom_id`, which
 *   survives an edit, a star, a tag, a hide and a regrouping), with the group
 *   headings kept in the selector so a reader above the first card of a group
 *   reports the group. Sections and themes are the same UI object (both are
 *   `QuoteGroup`, both render `<h3 id={anchor}>`), so both count.
 * - **codebook** — the code row, `code-<tag id>` (`CodebookAuthoring.tsx`, own
 *   tags and framework rows alike). Library preview rows carry synthetic
 *   negative ids (`CodebookV2.tsx`) and are excluded: they are not the study's
 *   codes. The walk takes the last row in the DOM above the threshold, which on
 *   a page of side-by-side group columns can be the rightmost column at that
 *   height (accepted for v1). Until 9 Nov 2026 this was `[id^='codebook-fw-']`,
 *   an id the v2 lens never rendered: from 31 Aug the lens reported nothing and
 *   always restored to the top, and nothing failed.
 * - **signals** — the card, `signalDomId` (`utils/signalDedup.ts`). Cards on
 *   the places the page is not showing sit in `<section hidden>` and are
 *   skipped (below). On restore native only calls `window.scrollToAnchor`;
 *   it is the SPA's `useScrollToAnchor` that offers the card to the page
 *   (`bn:reveal-anchor`), and the Signals page shows its place and lands it.
 *   The id changes when a codebook or tag group is renamed, and the restore
 *   then lands at the top (accepted for v1).
 * - **sessions** — the transcript paragraph, `t-<whole seconds>`, posted as a
 *   place, `s1#t-66`, the SPA's own address form; bare `null` at the top of a
 *   transcript or on the grid, where native falls back to `SessionsRouteMemory`
 *   (the session alone). `t-<seconds>` is not unique (two halves of a split
 *   paragraph share a second) and `getElementById` takes the first: the same
 *   place, accepted.
 * - **project**, **discussion**, **screens** — absent on purpose: the top. The
 *   right lens is enough for Project and Screens; Discussion has no element ids
 *   and arrives by query (`?item=&turn=`), so a restore there is a feature of
 *   its own, not a row in this table.
 *
 * A DOM selector rather than a marker attribute: an attribute has to be
 * remembered at every new call site, and this codebase has already been bitten
 * by that (`SectionHeading` exists because a class you must remember to type
 * gets forgotten). The cost is the other way round: a selector dies silently
 * when the DOM it watches is replaced, which is exactly what happened to
 * Codebook. So each selector is pinned against the component that renders it
 * (`QuoteCard.test.tsx`, `CodebookV2Page.test.tsx`, `SignalsPage.test.tsx`,
 * `TranscriptPage.test.tsx`).
 */
export const ANCHOR_SELECTORS: Record<string, string> = {
  quotes: "h3[id^='section-'], h3[id^='theme-'], blockquote.quote-card[id^='q-']",
  codebook: ".tag-row[id^='code-']:not([id^='code--'])",
  signals: ".signal-card[id^='signal-']",
  sessions: ".transcript-segment[id^='t-']",
};

/** Distance from the viewport top at which an element counts as "the one you're at". */
const THRESHOLD_PX = 120;

/** Quiet period after scrolling stops before the position is reported. */
const SETTLE_MS = 400;

/** The lens a report pathname is on, or null if it isn't a lens route. */
function lensFor(pathname: string): string | null {
  const match = /^\/report\/([a-z]+)/.exec(pathname);
  return match ? match[1] : null;
}

/** The transcript a Sessions pathname shows, or null on the grid. */
function sessionFor(pathname: string): string | null {
  const match = /^\/report\/sessions\/(s\d+)/.exec(pathname);
  return match ? match[1] : null;
}

/**
 * Report the element the reader is at.
 *
 * @param pathname — the current route, which selects the lens.
 * @param embedded — whether we are inside the native shell.
 */
export function useAnchorReporter(pathname: string, embedded: boolean): void {
  useEffect(() => {
    if (!embedded) return;
    const lens = lensFor(pathname) ?? "";
    const selector = ANCHOR_SELECTORS[lens];
    // On Sessions the position is within a transcript; the grid has none.
    const session = lens === "sessions" ? sessionFor(pathname) : null;
    if (!selector || (lens === "sessions" && !session)) {
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
      // Bottom-to-top: the last element above the threshold is the one you are
      // reading under. Same walk as `useScrollSpy`, which does this for the
      // table of contents; kept separate because that hook's contract is an
      // ordered id list plus a click-intent override, neither of which applies
      // here.
      for (let i = elements.length - 1; i >= 0; i--) {
        const el = elements[i];
        if (el.closest("[hidden]")) continue;
        // Not on screen at all: a Signals card on a place the page is not
        // showing, or a quote card collapsing as it is hidden. Both measure
        // with a top of 0, so they would otherwise always win the walk.

        const rect = el.getBoundingClientRect();
        if (rect.height === 0) continue;

        if (rect.top <= THRESHOLD_PX) return el.id || null;
      }
      return null; // above the first element — the top of the page
    }

    function report() {
      const id = currentAnchor();
      // Sessions posts a place, so the session and the paragraph always travel
      // together: a paragraph id from one transcript never stands for another.
      const anchor = session && id ? `${session}#${id}` : id;
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
