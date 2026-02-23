/**
 * Lazy transcript cache — fetches full transcript on first expand,
 * caches per-session, returns segments by index or timecode.
 */

import { useCallback, useRef } from "react";
import { getTranscript } from "../utils/api";
import type { TranscriptSegmentResponse } from "../utils/types";

/** Segments indexed by segment_index for O(1) lookup. */
type SegmentIndex = Map<number, TranscriptSegmentResponse>;

/** Full ordered segment list for timecode-based lookup. */
type SessionData = {
  byIndex: SegmentIndex;
  ordered: TranscriptSegmentResponse[];
};

interface TranscriptCache {
  /** Get a segment by session and segment index. Fetches transcript if not cached. */
  getSegment: (
    sessionId: string,
    segmentIndex: number,
  ) => Promise<TranscriptSegmentResponse | null>;
  /** Get multiple segments by index range. Returns in order. */
  getSegmentRange: (
    sessionId: string,
    fromIndex: number,
    toIndex: number,
  ) => Promise<TranscriptSegmentResponse[]>;
  /**
   * Find the segment containing a timecode, then return N segments
   * above and/or below it. Used when segment_index is -1.
   */
  getContextByTimecode: (
    sessionId: string,
    startSeconds: number,
    above: number,
    below: number,
  ) => Promise<{ above: TranscriptSegmentResponse[]; below: TranscriptSegmentResponse[] }>;
}

export function useTranscriptCache(): TranscriptCache {
  const cache = useRef<Map<string, SessionData>>(new Map());
  /** Track in-flight fetches to avoid duplicate requests. */
  const pending = useRef<Map<string, Promise<SessionData>>>(new Map());

  const ensureSession = useCallback(
    async (sessionId: string): Promise<SessionData> => {
      const existing = cache.current.get(sessionId);
      if (existing) return existing;

      // Deduplicate concurrent fetches for the same session.
      const inflight = pending.current.get(sessionId);
      if (inflight) return inflight;

      const promise = getTranscript(sessionId).then((resp) => {
        const byIndex: SegmentIndex = new Map();
        for (const seg of resp.segments) {
          if (seg.segment_index >= 0) {
            byIndex.set(seg.segment_index, seg);
          }
        }
        const data: SessionData = { byIndex, ordered: resp.segments };
        cache.current.set(sessionId, data);
        pending.current.delete(sessionId);
        return data;
      });
      pending.current.set(sessionId, promise);
      return promise;
    },
    [],
  );

  const getSegment = useCallback(
    async (
      sessionId: string,
      segmentIndex: number,
    ): Promise<TranscriptSegmentResponse | null> => {
      if (segmentIndex < 0) return null;
      const data = await ensureSession(sessionId);
      return data.byIndex.get(segmentIndex) ?? null;
    },
    [ensureSession],
  );

  const getSegmentRange = useCallback(
    async (
      sessionId: string,
      fromIndex: number,
      toIndex: number,
    ): Promise<TranscriptSegmentResponse[]> => {
      if (fromIndex < 0 && toIndex < 0) return [];
      const data = await ensureSession(sessionId);
      const result: TranscriptSegmentResponse[] = [];
      for (let i = Math.max(0, fromIndex); i <= toIndex; i++) {
        const seg = data.byIndex.get(i);
        if (seg) result.push(seg);
      }
      return result;
    },
    [ensureSession],
  );

  const getContextByTimecode = useCallback(
    async (
      sessionId: string,
      startSeconds: number,
      above: number,
      below: number,
    ): Promise<{ above: TranscriptSegmentResponse[]; below: TranscriptSegmentResponse[] }> => {
      const data = await ensureSession(sessionId);
      const segs = data.ordered;
      if (segs.length === 0) return { above: [], below: [] };

      // Find the segment whose time range contains startSeconds.
      // Segments are ordered by start_time. Find the last segment
      // whose start_time <= startSeconds.
      let matchIdx = 0;
      for (let i = 0; i < segs.length; i++) {
        if (segs[i].start_time <= startSeconds) {
          matchIdx = i;
        } else {
          break;
        }
      }

      const aboveSegs: TranscriptSegmentResponse[] = [];
      for (let i = Math.max(0, matchIdx - above); i < matchIdx; i++) {
        aboveSegs.push(segs[i]);
      }

      const belowSegs: TranscriptSegmentResponse[] = [];
      for (let i = matchIdx + 1; i <= Math.min(segs.length - 1, matchIdx + below); i++) {
        belowSegs.push(segs[i]);
      }

      return { above: aboveSegs, below: belowSegs };
    },
    [ensureSession],
  );

  return { getSegment, getSegmentRange, getContextByTimecode };
}
