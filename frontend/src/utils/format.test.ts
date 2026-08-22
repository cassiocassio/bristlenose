import { describe, expect, it } from "vitest";
import { formatDurationHuman, formatCompactDate } from "./format";

describe("formatDurationHuman", () => {
  // ── The shared table ────────────────────────────────────────────────
  // These cases are lifted from DurationFormatTests.swift, which pins the
  // Swift mirror to Python's `_format_duration_human`. Same inputs, same
  // expected strings — so if any surface drifts, one of the two suites goes
  // red. Change a value here only in lockstep with the Swift table.
  it.each([
    [66_180, "18h 23m"], // the window subtitle's worked example
    [3_600, "1h"], //        whole hours drop the minute part
    [3_661, "1h 1m"],
    [3_780, "1h 3m"], //     the case the sidebar used to render "1h 03"
    [240, "4m"],
    [60, "1m"],
    [1_591, "26m"], //       the grid case that used to read "26:31"
    [59, "<1m"], //          honest about sub-minute, never "0m"
    [30, "<1m"],
  ])("formats %i seconds as %s", (seconds, expected) => {
    expect(formatDurationHuman(seconds)).toBe(expected);
  });

  // ── The one deliberate divergence from Swift/Python ──────────────────
  // Swift and Python return "0m" here because they format aggregate totals,
  // where zero is a real answer. This formats a per-row cell, where zero
  // means unknown — 8% of the local trial-run corpus. Rendering "0m" would
  // assert a measurement nobody made. See the note on the function.
  it("returns em-dash for 0 seconds, NOT the Swift/Python 0m", () => {
    expect(formatDurationHuman(0)).toBe("\u2014");
  });

  it("returns em-dash for negative seconds", () => {
    expect(formatDurationHuman(-10)).toBe("\u2014");
  });

  // Truncation, not rounding — matches Python's floor division so a session
  // one second short of the next minute never reads as having reached it.
  it("truncates fractional seconds rather than rounding up", () => {
    expect(formatDurationHuman(119.9)).toBe("1m");
    expect(formatDurationHuman(3_599.9)).toBe("59m");
  });

  // The whole point of the change: no output may look like a clock time.
  it("never emits a colon (the ambiguity this format exists to remove)", () => {
    for (const s of [1, 59, 60, 1_591, 3_600, 3_780, 16_139, 66_180]) {
      expect(formatDurationHuman(s)).not.toContain(":");
    }
  });
});

describe("formatCompactDate", () => {
  it("returns em-dash for null", () => {
    expect(formatCompactDate(null)).toBe("\u2014");
  });

  it("returns em-dash for invalid date string", () => {
    expect(formatCompactDate("not-a-date")).toBe("\u2014");
  });

  it("formats as day + month abbreviation", () => {
    expect(formatCompactDate("2026-02-12T10:00:00")).toBe("12 Feb");
  });

  it("includes day of week when includeDay is true", () => {
    // 2026-02-12 is a Thursday
    expect(formatCompactDate("2026-02-12T10:00:00", true)).toBe("Thu 12 Feb");
  });

  it("handles single-digit day without leading zero", () => {
    expect(formatCompactDate("2026-03-05T10:00:00")).toBe("5 Mar");
  });

  it("formats December correctly", () => {
    expect(formatCompactDate("2025-12-25T10:00:00")).toBe("25 Dec");
  });

  it("includes correct day of week", () => {
    // 2026-02-15 is a Sunday
    expect(formatCompactDate("2026-02-15T10:00:00", true)).toBe("Sun 15 Feb");
  });
});
