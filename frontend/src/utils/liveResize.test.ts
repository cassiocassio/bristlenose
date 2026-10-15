import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  SETTLE_MS,
  isLiveResizing,
  noteResize,
  resetLiveResize,
  setLiveResize,
  subscribeLiveResize,
} from "./liveResize";

beforeEach(() => {
  vi.useFakeTimers();
  resetLiveResize();
});
afterEach(() => {
  vi.useRealTimers();
});

describe("liveResize", () => {
  it("in a browser, a resize is live until no size change has come for SETTLE_MS", () => {
    const seen: boolean[] = [];
    subscribeLiveResize(() => seen.push(isLiveResizing()));
    noteResize();
    expect(isLiveResizing()).toBe(true);
    vi.advanceTimersByTime(SETTLE_MS - 10);
    noteResize(); // still wiggling: the end moves out
    vi.advanceTimersByTime(SETTLE_MS - 10);
    expect(isLiveResizing()).toBe(true);
    vi.advanceTimersByTime(20);
    expect(isLiveResizing()).toBe(false);
    expect(seen).toEqual([true, false]); // one start, one end — not one per event
  });

  it("while native says live, its exact start and end decide, and size changes do not", () => {
    setLiveResize(true);
    expect(isLiveResizing()).toBe(true);
    noteResize();
    vi.advanceTimersByTime(SETTLE_MS * 5);
    expect(isLiveResizing()).toBe(true); // no debounce guessing while native says live
    setLiveResize(false);
    expect(isLiveResizing()).toBe(false); // exact end, no trailing wait
  });

  it("after native's live resize ends, other resizes still get the debounce", () => {
    // A web view resized by its column toggling is no NSWindow live resize: without the debounce
    // the board would recompose every frame (code review, 15 Oct 2026).
    setLiveResize(true);
    setLiveResize(false);
    noteResize();
    expect(isLiveResizing()).toBe(true);
    vi.advanceTimersByTime(SETTLE_MS + 1);
    expect(isLiveResizing()).toBe(false);
  });
});
