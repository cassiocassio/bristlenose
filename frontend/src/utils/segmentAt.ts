/**
 * The transcript paragraph a moment belongs to: the one containing it, else the nearest starting
 * at or after it, else the last. Shared by the two ways a link lands in the transcript by time —
 * a `#t-` deep link and a click on the transcript's own timeline — so a quote that starts
 * mid-paragraph lands on a real paragraph either way. (Placing screens and questions in the gutter
 * has rules of its own: paragraphIndexAt, moderatorParagraphAt in TranscriptPage.) Segments are
 * in time order. -1 when there are none.
 */
export function segmentIndexAt(segments: readonly { start_time: number; end_time: number }[], target: number): number {
  if (segments.length === 0) return -1;
  let after = -1;
  for (let i = 0; i < segments.length; i++) {
    const seg = segments[i];
    if (seg.start_time <= target && target < seg.end_time) return i;
    if (seg.start_time >= target && after < 0) after = i;
  }
  return after >= 0 ? after : segments.length - 1;
}
