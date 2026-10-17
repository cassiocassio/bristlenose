import { describe, it, expect, beforeEach, vi } from "vitest";
import {
  applyTimelineMenuAction,
  getTranscriptTimeline,
  onTimelineWillChange,
  resetTranscriptTimelineStore,
  setTimelineAvailable,
  setTimelineLanes,
  setTimelineOn,
  toggleTimeline,
} from "./TranscriptTimelineStore";

beforeEach(() => resetTranscriptTimelineStore());

describe("TranscriptTimelineStore", () => {
  it("starts on the chain at the Standard detail", () => {
    expect(getTranscriptTimeline()).toEqual({ on: false, lanes: 3, available: false });
  });

  it("remembers on and the detail for the viewer, but never availability", () => {
    toggleTimeline();
    setTimelineLanes(5);
    setTimelineAvailable(true);
    expect(JSON.parse(localStorage.getItem("bn-transcript-timeline")!)).toEqual({ on: true, lanes: 5 });
  });

  it("turns the timeline on when a detail is picked", () => {
    setTimelineLanes(2);
    expect(getTranscriptTimeline()).toMatchObject({ on: true, lanes: 2 });
  });

  it("tells the page just before the slot changes, while the old layout stands, and not for availability", () => {
    const seen: boolean[] = [];
    const off = onTimelineWillChange(() => seen.push(getTranscriptTimeline().on));
    setTimelineOn(true);
    setTimelineAvailable(true);
    setTimelineOn(true); // no change, no call
    off();
    setTimelineOn(false);
    expect(seen).toEqual([false]);
  });

  it("answers the Mac's View menu, and ignores what is not its own or a bad detail", () => {
    expect(applyTimelineMenuAction("toggleSessionTimeline")).toBe(true);
    expect(getTranscriptTimeline().on).toBe(true);
    expect(applyTimelineMenuAction("setSessionTimelineLanes", { lanes: 5 })).toBe(true);
    expect(getTranscriptTimeline().lanes).toBe(5);
    applyTimelineMenuAction("setSessionTimelineLanes", { lanes: 4 });
    expect(getTranscriptTimeline().lanes).toBe(5);
    expect(applyTimelineMenuAction("focusMode")).toBe(false);
  });

  it("falls back to the chain when storage holds nonsense", async () => {
    localStorage.setItem("bn-transcript-timeline", "{\"on\":\"yes\",\"lanes\":7}");
    vi.resetModules();
    const fresh = await import("./TranscriptTimelineStore");
    expect(fresh.getTranscriptTimeline()).toEqual({ on: false, lanes: 3, available: false });
  });
});
