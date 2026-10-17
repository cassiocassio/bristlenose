/**
 * The flash on the thing a link landed on (docs/design-arrival-flash.md).
 *
 * Every destination calls `markArrived` on the element it scrolled to: the transcript paragraph,
 * the quote card or group heading, the screen's title in Screens, the asking in Discussion.
 * The look lives in one place, `theme/atoms/arrival.css`, driven by the `--bn-arrival-*` tokens.
 *
 * It is an attribute, not a class, because React owns these elements' `className` and a re-render
 * that changes it would wipe a class mid-flash (frontend/CLAUDE.md, "Mark transcript words and
 * segments with `data-*` attributes").
 */

const ATTR = "data-arrived";
const ANIMATION = "bn-arrival";

/** The clearing listener of each element's current flash, so a re-mark replaces it. */
const clearers = new WeakMap<Element, (e: Event) => void>();

/** Flash `el`, from the start if it is flashing already. */
export function markArrived(el: Element): void {
  const previous = clearers.get(el);
  if (previous) {
    el.removeEventListener("animationend", previous);
    el.removeEventListener("animationcancel", previous);
  }
  el.removeAttribute(ATTR);
  // A reflow between removing and setting restarts the animation.
  void (el as HTMLElement).offsetWidth;
  el.setAttribute(ATTR, "");
  // Clear it when its own flash ends, so moving the node (a keyed reorder) or showing it again
  // after a collapse cannot replay the flash. A flash cut short (the element lost its box: a
  // collapse, a hidden pane) ends in `animationcancel`, not `animationend`. Both bubble from
  // children (a badge's fade-in), so only this element's own `bn-arrival` counts.
  //
  // A restart cancels the old animation, and that `animationcancel` is delivered a frame later,
  // to this listener: so an event while a `bn-arrival` is still running on the element is the old
  // one's, not this one's end (WebKit and Chromium, probed 17 Oct 2026).
  const done = (e: Event) => {
    if (e.target !== el || (e as AnimationEvent).animationName !== ANIMATION) return;
    const running = (el as HTMLElement).getAnimations?.() ?? [];
    if (running.some((a) => (a as CSSAnimation).animationName === ANIMATION)) return;
    el.removeEventListener("animationend", done);
    el.removeEventListener("animationcancel", done);
    clearers.delete(el);
    el.removeAttribute(ATTR);
  };
  clearers.set(el, done);
  el.addEventListener("animationend", done);
  el.addEventListener("animationcancel", done);
}
