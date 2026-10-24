/**
 * The event the transcript page re-reads on: a paragraph edit, or an undo or
 * redo of one, or of a quote act (tags, deleted badges, hidden quotes), since
 * the page draws its own copy of those. Its own module so the quotes store can
 * fire it without pulling the paragraph editor into first paint.
 */

/** Fired when a transcript write has landed, so an open transcript re-reads. */
export const TRANSCRIPT_WRITTEN_EVENT = "bn:transcript-written";

/** Tell an open transcript to read again. */
export function transcriptWritten(): void {
  window.dispatchEvent(new CustomEvent(TRANSCRIPT_WRITTEN_EVENT));
}
