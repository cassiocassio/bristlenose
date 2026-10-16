/**
 * scrollToLand — smooth-scroll an element into view, and make sure it lands.
 *
 * The quote cards are `content-visibility: auto` with a 250px placeholder
 * height (`theme/organisms/blockquote.css`), so a smooth scroll aims at a
 * position worked out from placeholders, and the target moves as the cards it
 * passes are laid out at their real heights. The scroll ends a few cards off
 * the heading, and a second click lands because the cards are measured by
 * then. So: scroll, wait for the page to stop, and scroll again until two
 * stops agree. The second pass crosses only cards the first one laid out, and
 * when the first pass landed it moves nothing.
 *
 * Settling is judged by a quiet spell in `scroll` events rather than
 * `scrollend`, which older WebKit lacks, and the target is measured only after
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

export function scrollToLand(el: Element, block: ScrollLogicalPosition = "start"): void {
  cancelPending?.(); // a newer jump replaces an older one's correction
  let passes = 0;
  let lastTop: number | null = null;
  let timer: ReturnType<typeof setTimeout> | undefined;

  const stop = () => {
    clearTimeout(timer);
    window.removeEventListener("scroll", onScroll);
    for (const type of USER_INPUT) window.removeEventListener(type, stop);
    if (cancelPending === stop) cancelPending = null;
  };

  const settled = () => {
    if (!el.isConnected) return stop();
    const top = el.getBoundingClientRect().top;
    if ((lastTop !== null && Math.abs(top - lastTop) <= TOLERANCE_PX) || passes >= MAX_PASSES) {
      return stop();
    }
    lastTop = top;
    pass();
  };

  function onScroll() {
    clearTimeout(timer);
    timer = setTimeout(settled, SETTLE_MS);
  }

  const pass = () => {
    passes++;
    el.scrollIntoView({ behavior: "smooth", block });
    // A pass that moves nothing fires no scroll event.
    clearTimeout(timer);
    timer = setTimeout(settled, SETTLE_MS);
  };

  window.addEventListener("scroll", onScroll, { passive: true });
  for (const type of USER_INPUT) window.addEventListener(type, stop, { passive: true });
  cancelPending = stop;
  pass();
}
