/**
 * Which scope the transcript's picker opens on (design-people.md §K): the
 * speaker across the session, or one paragraph. Session is the default; a
 * researcher who switches to Paragraph keeps it for the run of paragraphs they
 * are fixing, and it goes back to Session when they leave the transcript.
 *
 * Module-level, like the other small stores: the transcript sets nothing until
 * someone switches, and its unmount clears it.
 */

let held: string | null = null;

/** Whether this session's transcript is on Paragraph. */
export function paragraphScopeFor(sessionId: string): boolean {
  return held === sessionId;
}

export function setParagraphScope(sessionId: string, paragraph: boolean): void {
  held = paragraph ? sessionId : null;
}

/** Back to Session: leaving the transcript, and between tests. */
export function resetParagraphScope(): void {
  held = null;
}
