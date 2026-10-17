import { describe, it, expect } from "vitest";
import { readingWindow, sectionAt } from "./TranscriptTimeline";

// jsdom lays nothing out (every rect is zero), so each paragraph is given its own rect.
function body(rows: { top: number; height: number; t0: number; t1: number }[]): HTMLElement {
  const host = document.createElement("section");
  for (const r of rows) {
    const el = document.createElement("div");
    el.className = "transcript-segment";
    el.dataset.startSeconds = String(r.t0);
    el.dataset.endSeconds = String(r.t1);
    el.getBoundingClientRect = () => ({ top: r.top, bottom: r.top + r.height, height: r.height, left: 0, right: 0, width: 100, x: 0, y: r.top, toJSON: () => ({}) }) as DOMRect;
    host.appendChild(el);
  }
  return host;
}

describe("readingWindow", () => {
  const rows = [
    { top: -100, height: 100, t0: 0, t1: 10 },   // above the header, gone
    { top: 0, height: 100, t0: 10, t1: 30 },     // half under the header (bottom at 50)
    { top: 100, height: 100, t0: 30, t1: 40 },
    { top: 200, height: 100, t0: 40, t1: 60 },   // half below the window's bottom (250)
    { top: 300, height: 100, t0: 60, t1: 70 },   // below, not seen
  ];

  it("spans the paragraphs between the header and the window's bottom, interpolated within the end ones", () => {
    expect(readingWindow(body(rows), 50, 250)).toEqual([20, 50]);
  });

  it("is null before anything is laid out, and skips the impossible rects Safari reports mid-scroll", () => {
    expect(readingWindow(body([]), 50, 250)).toBeNull();
    const glitched = body([{ top: 120, height: -40, t0: 5, t1: 9 }, ...rows.slice(2)]);
    expect(readingWindow(glitched, 50, 250)).toEqual([30, 50]);
  });
});

describe("sectionAt", () => {
  const flags = [{ t0: 10 }, { t0: 46 }];
  it("raises the last flag at or before the window's start, with half a second's grace", () => {
    expect(sectionAt(flags, 5)).toBe(-1);
    expect(sectionAt(flags, 9.6)).toBe(0);
    expect(sectionAt(flags, 45.6)).toBe(1);
    expect(sectionAt(flags, 999)).toBe(1);
  });
});
