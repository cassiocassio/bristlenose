/**
 * Quote sequence detection for signal cards.
 *
 * Detects "runs" of consecutive quotes from the same speaker in the same
 * session — narrative sequences that should be visually grouped rather than
 * shown as independent observations.
 *
 * See docs/design-quote-sequences.md for rationale and threshold derivation.
 */

/** Position of a quote within a detected sequence. */
export type SequencePosition = "solo" | "first" | "middle" | "last";

/** Sequence metadata for a single quote, used by QuoteBlock for rendering. */
export interface SequenceMeta {
  position: SequencePosition;
  /** Total number of quotes in this sequence (1 for solo). */
  sequenceLength: number;
}

/**
 * Empirical threshold: 77% of consecutive quote pairs from the IKEA usability
 * study fall within 15–20s; 17.5s splits the plateau.
 */
export const SEQUENCE_GAP_SECONDS = 17.5;

/** Minimum quotes to form a displayable sequence. */
const MIN_SEQUENCE_LENGTH = 2;

/**
 * Detect quote sequences in a signal card's quote list.
 *
 * Expects quotes pre-sorted by `(pid, startSeconds)` — the backend already
 * provides this order. Returns a parallel array of `SequenceMeta`, one per
 * input quote.
 *
 * Two consecutive quotes form a continuation when:
 * - Same `pid` AND same `sessionId`
 * - Both have `startSeconds > 0` (timecoded)
 * - Time gap ≤ SEQUENCE_GAP_SECONDS
 *
 * Quotes with `startSeconds === 0` (non-timecoded) never form sequences —
 * ordinal-based detection is deferred to a future release.
 */
export function detectSequences(
  quotes: ReadonlyArray<{
    pid: string;
    sessionId: string;
    startSeconds: number;
  }>,
): SequenceMeta[] {
  const n = quotes.length;
  if (n === 0) return [];

  // Step 1: Build a boolean array of "continues from previous" flags.
  const continues: boolean[] = new Array(n).fill(false);
  for (let i = 1; i < n; i++) {
    const prev = quotes[i - 1];
    const curr = quotes[i];
    if (
      curr.pid === prev.pid &&
      curr.sessionId === prev.sessionId &&
      prev.startSeconds > 0 &&
      curr.startSeconds > 0 &&
      curr.startSeconds - prev.startSeconds <= SEQUENCE_GAP_SECONDS
    ) {
      continues[i] = true;
    }
  }

  // Step 2: Walk the continues array to find run boundaries.
  // A run starts where continues[i] is false and continues[i+1] is true.
  const result: SequenceMeta[] = new Array(n);

  let runStart = 0;
  while (runStart < n) {
    // Find the end of this run.
    let runEnd = runStart;
    while (runEnd + 1 < n && continues[runEnd + 1]) {
      runEnd++;
    }

    const runLen = runEnd - runStart + 1;

    if (runLen < MIN_SEQUENCE_LENGTH) {
      // Not long enough — mark all as solo.
      for (let i = runStart; i <= runEnd; i++) {
        result[i] = { position: "solo", sequenceLength: 1 };
      }
    } else {
      // Real sequence.
      for (let i = runStart; i <= runEnd; i++) {
        let position: SequencePosition;
        if (i === runStart) position = "first";
        else if (i === runEnd) position = "last";
        else position = "middle";
        result[i] = { position, sequenceLength: runLen };
      }
    }

    runStart = runEnd + 1;
  }

  return result;
}
