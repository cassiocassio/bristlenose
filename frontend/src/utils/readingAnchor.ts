/**
 * Keeping the reader's place when an open transcript re-reads itself.
 *
 * During a first analysis a session's quotes arrive after its transcript, and
 * the whole report at the end of the run (docs/design-progressive-lenses.md):
 * the transcript page re-reads, and highlights, margin notes and paragraph
 * splits can move the lines under the reader. The anchor is the first
 * paragraph not hidden under the sticky header — its start time, which
 * survives a re-read, and its distance from the top of the window. After the
 * re-read the page scrolls by however far that paragraph moved.
 */

export interface ReadingAnchor {
  /** `data-start-seconds` of the paragraph, as drawn. */
  start: string;
  /** Which of the paragraphs sharing that start (the halves of a split). */
  nth: number;
  /** Its top, in viewport coordinates, when captured. */
  top: number;
  /** The window's scroll then: scrolling of the reader's own between capture
   *  and restore (momentum, the player following playback) is kept. */
  scrollY: number;
}

const TEXT_ENTRY = new Set(["text", "search", "email", "url", "tel", "password", "number"]);

function paragraphs(body: HTMLElement): HTMLElement[] {
  return Array.from(body.querySelectorAll<HTMLElement>(".transcript-segment"));
}

/** The first paragraph whose bottom is below `threshold` (the sticky header's
 *  bottom edge), or null when the transcript has none. */
export function captureReadingAnchor(body: HTMLElement, threshold: number): ReadingAnchor | null {
  const seen = new Map<string, number>();
  let first: ReadingAnchor | null = null;
  for (const el of paragraphs(body)) {
    const start = el.dataset.startSeconds ?? "";
    const nth = seen.get(start) ?? 0;
    seen.set(start, nth + 1);
    const rect = el.getBoundingClientRect();
    const anchor = { start, nth, top: rect.top, scrollY: window.scrollY };
    if (!first) first = anchor;
    if (rect.bottom > threshold) return anchor;
  }
  return first;
}

/** Scroll so the anchored paragraph is where it was. Falls back to the last
 *  paragraph starting at or before it (a paragraph the re-read rebuilt).
 *  Returns how far the page was scrolled. */
export function restoreReadingAnchor(body: HTMLElement, anchor: ReadingAnchor): number {
  const seen = new Map<string, number>();
  let match: HTMLElement | null = null;
  let before: HTMLElement | null = null;
  const at = Number(anchor.start);
  for (const el of paragraphs(body)) {
    const start = el.dataset.startSeconds ?? "";
    const nth = seen.get(start) ?? 0;
    seen.set(start, nth + 1);
    if (start === anchor.start && nth === anchor.nth) {
      match = el;
      break;
    }
    if (Number.isFinite(at) && Number(start) <= at) before = el;
  }
  const el = match ?? before;
  if (!el) return 0;
  // How far the paragraph moved, less how far the reader scrolled meanwhile.
  const delta = el.getBoundingClientRect().top - anchor.top + (window.scrollY - anchor.scrollY);
  if (delta !== 0) window.scrollBy(0, delta);
  return delta;
}

/** True while a re-read would get in the reader's way: text selected in the
 *  transcript (they may be copying it), or a text field with focus (the
 *  speaker picker's name, anywhere on the page). A caret alone is not busy: Return and
 *  Backspace act at once and re-read the transcript themselves. */
export function readerIsBusy(body: HTMLElement): boolean {
  const selection = window.getSelection();
  if (
    selection && !selection.isCollapsed && selection.anchorNode
    && body.contains(selection.anchorNode)
  ) {
    return true;
  }
  const active = document.activeElement;
  if (!active) return false;
  if (active.tagName === "TEXTAREA") return true;
  // Text entry only: a focused checkbox or button is not someone typing.
  return active instanceof HTMLInputElement && TEXT_ENTRY.has(active.type);
}
