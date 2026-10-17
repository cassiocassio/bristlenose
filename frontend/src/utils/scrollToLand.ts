/**
 * scrollToLand — smooth-scroll an element into view, and make sure it lands.
 *
 * Two things move a heading away from where `scrollIntoView` put it:
 *
 * - The quote cards are `content-visibility: auto` with a 250px placeholder
 *   height (`theme/organisms/blockquote.css`), so a smooth scroll aims at a
 *   position worked out from placeholders, and the target moves as the cards
 *   it passes are laid out at their real heights. The scroll ends a few cards
 *   off the heading, and a second click lands because the cards are measured
 *   by then.
 * - In the browser, a heading under the sticky toolbar is meant to stop below
 *   it by its `scroll-margin-top` (`theme/organisms/toolbar.css`). Safari was
 *   seen landing it flush with the top instead, behind the search field
 *   (16 Oct 2026); headless WebKit honoured the margin, so the engine is not
 *   to be trusted on it.
 *
 * So: scroll, wait for the page to stop, and measure. When the page is the
 * scroller and the block is "start", the heading belongs at its own
 * `scroll-margin-top` from the top of the window, and any difference is
 * scrolled by directly. Otherwise (a scrolling panel, another block) scroll
 * again until two stops agree; when the first pass landed, that moves nothing.
 *
 * Settling is judged by a quiet spell in `scroll` events rather than
 * `scrollend`, which older WebKit lacks. They are heard in the capture phase on
 * `document`, which catches a scrolling panel as well as the page (`scroll`
 * does not bubble from an element). The target is measured only after
 * the page has stopped: Safari's `getBoundingClientRect()` is unreliable while
 * a smooth scroll is running (frontend/CLAUDE.md, Testing).
 *
 * @module scrollToLand
 */

const SETTLE_MS = 150;
const MAX_PASSES = 3;
const TOLERANCE_PX = 2;
/** The researcher taking over the scroll ends the correction. */
const USER_INPUT = ["wheel", "touchmove", "keydown", "pointerdown"] as const;

let cancelPending: (() => void) | null = null;

/** True when no ancestor below the page scrolls, so the window is the scroller. */
function scrolledByPage(el: Element): boolean {
  for (let p = el.parentElement; p && p !== document.body; p = p.parentElement) {
    const overflow = getComputedStyle(p).overflowY;
    if ((overflow === "auto" || overflow === "scroll") && p.scrollHeight > p.clientHeight) return false;
  }
  return true;
}

/** True when the page has room to scroll `by` pixels (positive is down). */
function pageCanScroll(by: number): boolean {
  if (by < 0) return window.scrollY > 0;
  return window.scrollY + window.innerHeight < document.documentElement.scrollHeight - 1;
}

/** End any correction still in flight (tests call it between cases: a settle
 * timer that fires after jsdom tears the document down throws). */
export function cancelScrollToLand(): void {
  cancelPending?.();
}

export function scrollToLand(el: Element, block: ScrollLogicalPosition = "start"): void {
  cancelPending?.(); // a newer jump replaces an older one's correction
  let passes = 0;
  let lastTop: number | null = null;
  let timer: ReturnType<typeof setTimeout> | undefined;

  const stop = () => {
    clearTimeout(timer);
    document.removeEventListener("scroll", onScroll, true);
    for (const type of USER_INPUT) window.removeEventListener(type, stop);
    if (cancelPending === stop) cancelPending = null;
  };

  const wait = () => {
    // A scroll that moves nothing fires no scroll event.
    clearTimeout(timer);
    timer = setTimeout(settled, SETTLE_MS);
  };

  const settled = () => {
    if (!el.isConnected || passes >= MAX_PASSES) return stop();
    const top = el.getBoundingClientRect().top;
    if (block === "start" && scrolledByPage(el)) {
      const off = top - (parseFloat(getComputedStyle(el).scrollMarginTop) || 0);
      if (Math.abs(off) <= TOLERANCE_PX || !pageCanScroll(off)) return stop();
      passes++;
      window.scrollBy({ top: off, behavior: "smooth" });
      return wait();
    }
    if (lastTop !== null && Math.abs(top - lastTop) <= TOLERANCE_PX) return stop();
    lastTop = top;
    passes++;
    el.scrollIntoView({ behavior: "smooth", block });
    wait();
  };

  function onScroll() {
    clearTimeout(timer);
    timer = setTimeout(settled, SETTLE_MS);
  }

  document.addEventListener("scroll", onScroll, { capture: true, passive: true });
  for (const type of USER_INPUT) window.addEventListener(type, stop, { passive: true });
  cancelPending = stop;
  passes++;
  el.scrollIntoView({ behavior: "smooth", block });
  wait();
}
