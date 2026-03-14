import { describe, expect, it } from "vitest";
import { formatCompactDuration, formatCompactDate } from "./format";

describe("formatCompactDuration", () => {
  it("returns em-dash for 0 seconds", () => {
    expect(formatCompactDuration(0)).toBe("\u2014");
  });

  it("returns em-dash for negative seconds", () => {
    expect(formatCompactDuration(-10)).toBe("\u2014");
  });

  it("formats minutes only (no hours)", () => {
    expect(formatCompactDuration(2820)).toBe("47m");
  });

  it("formats exactly 1 hour", () => {
    expect(formatCompactDuration(3600)).toBe("1h 00");
  });

  it("formats 1 hour 3 minutes with zero-padded minutes", () => {
    expect(formatCompactDuration(3780)).toBe("1h 03");
  });

  it("formats 2 hours 23 minutes", () => {
    expect(formatCompactDuration(8580)).toBe("2h 23");
  });

  it("formats 0 minutes (e.g. 30 seconds)", () => {
    expect(formatCompactDuration(30)).toBe("0m");
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
