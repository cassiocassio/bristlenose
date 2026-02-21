import { describe, expect, it } from "vitest";
import {
  detectSequences,
  SEQUENCE_GAP_SECONDS,
  type SequenceMeta,
} from "./sequences";

/** Helper: extract just the positions from the result array. */
function positions(metas: SequenceMeta[]): string[] {
  return metas.map((m) => m.position);
}

/** Helper: build a minimal quote object. */
function q(pid: string, sessionId: string, startSeconds: number) {
  return { pid, sessionId, startSeconds };
}

describe("detectSequences", () => {
  it("returns empty array for empty input", () => {
    expect(detectSequences([])).toEqual([]);
  });

  it("returns solo for a single quote", () => {
    const result = detectSequences([q("p1", "s1", 10)]);
    expect(positions(result)).toEqual(["solo"]);
    expect(result[0].sequenceLength).toBe(1);
  });

  it("detects a two-quote sequence", () => {
    const result = detectSequences([
      q("p1", "s1", 10),
      q("p1", "s1", 20), // 10s gap, within threshold
    ]);
    expect(positions(result)).toEqual(["first", "last"]);
    expect(result[0].sequenceLength).toBe(2);
    expect(result[1].sequenceLength).toBe(2);
  });

  it("breaks sequence across different sessions", () => {
    const result = detectSequences([
      q("p1", "s1", 10),
      q("p1", "s2", 15), // different session
    ]);
    expect(positions(result)).toEqual(["solo", "solo"]);
  });

  it("breaks sequence across different participants", () => {
    const result = detectSequences([
      q("p1", "s1", 10),
      q("p2", "s1", 15), // different pid
    ]);
    expect(positions(result)).toEqual(["solo", "solo"]);
  });

  it("detects a three-quote sequence with middle position", () => {
    const result = detectSequences([
      q("p1", "s1", 10),
      q("p1", "s1", 20),
      q("p1", "s1", 30),
    ]);
    expect(positions(result)).toEqual(["first", "middle", "last"]);
    expect(result[0].sequenceLength).toBe(3);
    expect(result[1].sequenceLength).toBe(3);
    expect(result[2].sequenceLength).toBe(3);
  });

  it("handles a run of 3 followed by 2 solos", () => {
    const result = detectSequences([
      q("p1", "s1", 10),
      q("p1", "s1", 20),
      q("p1", "s1", 30),
      q("p2", "s1", 40), // different pid → solo
      q("p2", "s1", 80), // 40s gap → solo
    ]);
    expect(positions(result)).toEqual([
      "first", "middle", "last", "solo", "solo",
    ]);
  });

  it("continues at exactly the threshold (≤ 17.5s)", () => {
    const result = detectSequences([
      q("p1", "s1", 10),
      q("p1", "s1", 10 + SEQUENCE_GAP_SECONDS), // exactly 17.5s
    ]);
    expect(positions(result)).toEqual(["first", "last"]);
  });

  it("breaks just above the threshold (> 17.5s)", () => {
    const result = detectSequences([
      q("p1", "s1", 10),
      q("p1", "s1", 10 + SEQUENCE_GAP_SECONDS + 0.1), // 17.6s
    ]);
    expect(positions(result)).toEqual(["solo", "solo"]);
  });

  it("detects two separate sequences from the same pid", () => {
    const result = detectSequences([
      q("p1", "s1", 10),
      q("p1", "s1", 20),  // gap 10s → continues
      q("p1", "s1", 300), // gap 280s → breaks
      q("p1", "s1", 310), // gap 10s → continues
    ]);
    expect(positions(result)).toEqual(["first", "last", "first", "last"]);
    expect(result[0].sequenceLength).toBe(2);
    expect(result[2].sequenceLength).toBe(2);
  });

  it("marks isolated quotes between sequences as solo", () => {
    const result = detectSequences([
      q("p1", "s1", 10),
      q("p1", "s1", 20),  // sequence of 2
      q("p1", "s1", 300), // isolated (gap too big both ways)
      q("p1", "s1", 500),
      q("p1", "s1", 510), // sequence of 2
    ]);
    expect(positions(result)).toEqual([
      "first", "last", "solo", "first", "last",
    ]);
  });

  it("treats zero-timecode quotes as solo (no detection)", () => {
    const result = detectSequences([
      q("p1", "s1", 0),
      q("p1", "s1", 0),
      q("p1", "s1", 0),
    ]);
    expect(positions(result)).toEqual(["solo", "solo", "solo"]);
  });
});
