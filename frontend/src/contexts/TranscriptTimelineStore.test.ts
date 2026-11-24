import { describe, it, expect, beforeEach, vi } from "vitest";
import {
  applyTimelineMenuAction,
  getTranscriptTimeline,
  mostLanes,
  offeredLanes,
  onTimelineWillChange,
  resetTranscriptTimelineStore,
  setTimelineAvailable,
  setTimelineLanes,
  setTimelineOn,
  shownLanes,
  toggleTimeline,
} from "./TranscriptTimelineStore";
import contractJson from "../../../tests/fixtures/report-prefs-contract.json";

beforeEach(() => resetTranscriptTimelineStore());

describe("TranscriptTimelineStore", () => {
  it("starts on the chain at the Standard detail", () => {
    expect(getTranscriptTimeline()).toEqual({ on: false, lanes: 3, available: false, most: 5, sections: true, team: true });
  });

  it("draws the reader's detail down to what the session has, and keeps the choice for the next", () => {
    setTimelineLanes(5);
    setTimelineAvailable(true, { most: 3, sections: true, team: true });
    expect(shownLanes(getTranscriptTimeline())).toBe(3);
    expect(getTranscriptTimeline().lanes).toBe(5);
    expect(JSON.parse(localStorage.getItem("bn-transcript-timeline")!)).toMatchObject({ lanes: 5 });
    setTimelineAvailable(true, { most: 5, sections: true, team: true });
    expect(shownLanes(getTranscriptTimeline())).toBe(5);
    setTimelineAvailable(false, { most: 2, sections: false, team: false }); // leaving forgets the session's lanes
    expect(getTranscriptTimeline()).toMatchObject({ most: 5, sections: true, team: true });
  });

  it("reads the most detail from the quotes, and offers a choice only when there is one", () => {
    expect(mostLanes([])).toBe(2);
    expect(mostLanes([{ theme: null }])).toBe(3);
    expect(mostLanes([{ theme: null }, { theme: "Trust" }])).toBe(5);
    expect(offeredLanes(5)).toEqual([2, 3, 5]);
    expect(offeredLanes(3)).toEqual([2, 3]);
    expect(offeredLanes(2)).toEqual([]);
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

  it("hands a change to the Mac app as a report preference that fits its value limit", () => {
    // R89 extension, decision #182 (9 Nov 2026): the timeline is a reading mode, so the Mac app
    // keeps it past a relaunch. A bare localStorage write would be forgotten on quit.
    const w = window as unknown as Record<string, unknown>;
    const postMessage = vi.fn();
    w.webkit = { messageHandlers: { navigation: { postMessage } } };
    try {
      setTimelineLanes(5);
      expect(postMessage).toHaveBeenCalledWith({
        type: "report-pref",
        key: "bn-transcript-timeline",
        value: JSON.stringify({ on: true, lanes: 5 }),
      });
      const value = postMessage.mock.calls[0][0].value as string;
      expect(value.length).toBeLessThanOrEqual(contractJson.max_value_length);
      // Availability is not the viewer's choice and posts nothing.
      postMessage.mockClear();
      setTimelineAvailable(true);
      expect(postMessage).not.toHaveBeenCalled();
    } finally {
      delete w.webkit;
    }
  });

  it("falls back to the chain when storage holds nonsense", async () => {
    localStorage.setItem("bn-transcript-timeline", "{\"on\":\"yes\",\"lanes\":7}");
    vi.resetModules();
    const fresh = await import("./TranscriptTimelineStore");
    expect(fresh.getTranscriptTimeline()).toEqual({ on: false, lanes: 3, available: false, most: 5, sections: true, team: true });
  });
});
