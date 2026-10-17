import { describe, expect, it, vi, beforeEach } from "vitest";
import { act, render } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { QuotesArrival, arrivalAnchor, lastQuotesArrival } from "./QuotesArrival";
import { getQuotesSnapshot, initFromQuotes, resetStore, setViewMode } from "../contexts/QuotesContext";
import type { QuoteResponse } from "../utils/types";

vi.mock("../utils/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../utils/api")>()),
  putHidden: vi.fn(),
}));
const scrolled: string[] = [];
vi.mock("../hooks/useScrollToAnchor", () => ({
  useScrollToAnchor: () => (anchor: string) => scrolled.push(anchor),
}));

function quote(overrides: Partial<QuoteResponse> = {}): QuoteResponse {
  return {
    dom_id: "q-p1-10", text: "The delivery took three weeks", verbatim_excerpt: "", participant_id: "p1",
    session_id: "s1", speaker_name: "Alice", start_timecode: 10, end_timecode: 20, sentiment: "frustration",
    intensity: 2, researcher_context: null, quote_type: "experience", topic_label: "Delivery",
    is_starred: false, is_hidden: false, edited_text: null, tags: [], deleted_badges: [], proposed_tags: [],
    segment_index: 0, ...overrides,
  };
}

function arriveAt(entry: string) {
  return render(
    <MemoryRouter initialEntries={[entry]}>
      <QuotesArrival />
    </MemoryRouter>,
  );
}

beforeEach(() => {
  resetStore();
  scrolled.length = 0;
});

describe("arrivalAnchor", () => {
  it("takes a group's anchor or a list's, and nothing else", () => {
    expect(arrivalAnchor("#section-3")).toBe("section-3");
    expect(arrivalAnchor("#theme-12")).toBe("theme-12");
    expect(arrivalAnchor("#themes")).toBe("themes");
    expect(arrivalAnchor("#t-39")).toBeNull();
    expect(arrivalAnchor("#q-p1-10")).toBeNull();
    expect(arrivalAnchor("")).toBeNull();
  });
});

describe("QuotesArrival", () => {
  it("waits for this visit's quotes, then un-hides the quote, widens the view and scrolls", async () => {
    // What the store holds from an earlier visit: the quote hidden, starred-only on.
    initFromQuotes([quote({ is_hidden: true })], true);
    setViewMode("starred");
    arriveAt("/report/quotes/?reveal=q-p1-10#section-3");
    // Nothing yet: the store may be another visit's.
    expect(getQuotesSnapshot().hidden["q-p1-10"]).toBe(true);
    expect(scrolled).toEqual([]);

    // The lens loads this visit's quotes.
    await act(async () => {
      initFromQuotes([quote({ is_hidden: true })], true);
    });
    const after = getQuotesSnapshot();
    expect(after.hidden["q-p1-10"]).toBeUndefined();
    expect(after.viewMode).toBe("all");
    expect(lastQuotesArrival).toEqual({ reveal: "q-p1-10", anchor: "section-3", changed: ["hidden", "starredOnly"] });
    expect(scrolled).toEqual(["section-3"]);
  });

  it("changes nothing for a quote already in view, and only scrolls", async () => {
    arriveAt("/report/quotes/?reveal=q-p1-10#theme-4");
    await act(async () => {
      initFromQuotes([quote()], true);
    });
    expect(lastQuotesArrival?.changed).toEqual([]);
    expect(scrolled).toEqual(["theme-4"]);
  });

  it("does nothing without a group anchor", async () => {
    arriveAt("/report/quotes/?reveal=q-p1-10");
    await act(async () => {
      initFromQuotes([quote({ is_hidden: true })], true);
    });
    expect(getQuotesSnapshot().hidden["q-p1-10"]).toBe(true);
    expect(scrolled).toEqual([]);
  });
});
