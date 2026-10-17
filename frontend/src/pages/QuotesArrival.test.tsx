import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { act, render } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { QuotesArrival, arrivalAnchor, dropRevealFromAddress, lastQuotesArrival, resetQuotesArrival } from "./QuotesArrival";
import { getQuotesSnapshot, initFromQuotes, resetStore, setViewMode } from "../contexts/QuotesContext";
import type { QuoteResponse } from "../utils/types";

vi.mock("../utils/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../utils/api")>()),
  putHidden: vi.fn(),
}));
const scrolled: string[] = [];
const scrollOpts: ({ block?: string; highlight?: boolean } | undefined)[] = [];
vi.mock("../hooks/useScrollToAnchor", () => ({
  useScrollToAnchor: () => (anchor: string, opts?: { block?: string; highlight?: boolean }) => {
    scrolled.push(anchor);
    scrollOpts.push(opts);
  },
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
  resetQuotesArrival();
  scrolled.length = 0;
  scrollOpts.length = 0;
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
    // It lands on the quote the link named, and flashes it.
    expect(scrolled).toEqual(["q-p1-10"]);
    expect(scrollOpts).toEqual([{ block: "center", highlight: true }]);
  });

  it("changes nothing for a quote already in view, and only scrolls", async () => {
    arriveAt("/report/quotes/?reveal=q-p1-10#theme-4");
    await act(async () => {
      initFromQuotes([quote()], true);
    });
    expect(lastQuotesArrival?.changed).toEqual([]);
    expect(scrolled).toEqual(["q-p1-10"]);
  });

  it("keeps the quote un-hidden when the lens's second load still says hidden", async () => {
    // Each island fetches /quotes as it mounts; one answered before the un-hide reached the server
    // brings the hide back. The reveal holds through the visit's first loads (review, 17 Oct 2026).
    arriveAt("/report/quotes/?reveal=q-p1-10#section-3");
    await act(async () => {
      initFromQuotes([quote({ is_hidden: true })], true);
    });
    expect(getQuotesSnapshot().hidden["q-p1-10"]).toBeUndefined();
    await act(async () => {
      initFromQuotes([quote({ is_hidden: true })], true);
    });
    expect(getQuotesSnapshot().hidden["q-p1-10"]).toBeUndefined();
    expect(scrolled).toEqual(["q-p1-10"]); // scrolled once, not per load
  });

  it("scrolls after a wait when the quotes are slow, and still reveals when they come", async () => {
    vi.useFakeTimers();
    try {
      arriveAt("/report/quotes/?reveal=q-p1-10#section-3");
      await act(async () => {
        vi.advanceTimersByTime(5000);
      });
      expect(scrolled).toEqual(["section-3"]);
      expect(scrollOpts).toEqual([{ block: "start", highlight: true }]);
      await act(async () => {
        initFromQuotes([quote({ is_hidden: true })], true);
      });
      expect(getQuotesSnapshot().hidden["q-p1-10"]).toBeUndefined();
      expect(scrolled).toEqual(["section-3"]);
    } finally {
      vi.useRealTimers();
    }
  });

  it("says so when the quote to reveal is not in the report", async () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    arriveAt("/report/quotes/?reveal=q-p9-1#section-3");
    await act(async () => {
      initFromQuotes([quote()], true);
    });
    expect(warn).toHaveBeenCalledWith(expect.stringContaining("not in this report"), "q-p9-1");
    // Not in the report: the group's heading is where it lands, and what flashes.
    expect(scrolled).toEqual(["section-3"]);
    expect(scrollOpts).toEqual([{ block: "start", highlight: true }]);
    warn.mockRestore();
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

describe("dropRevealFromAddress", () => {
  // Back to the lens, or a reload, must not un-hide again a quote hidden since (review, 17 Oct 2026).
  afterEach(() => {
    window.history.replaceState(null, "", "/");
  });

  it("takes reveal off the browser router's query, keeping the anchor", () => {
    window.history.replaceState(null, "", "/report/quotes/?reveal=q-p1-10#section-3");
    dropRevealFromAddress();
    expect(window.location.pathname + window.location.search + window.location.hash).toBe("/report/quotes/#section-3");
  });

  it("takes it off the query inside an export's hash", () => {
    window.history.replaceState(null, "", "/report.html#/report/quotes/?reveal=q-p1-10#theme-1");
    dropRevealFromAddress();
    expect(window.location.hash).toBe("#/report/quotes/#theme-1");
  });

  it("leaves an address without one alone", () => {
    window.history.replaceState(null, "", "/report/quotes/#section-3");
    dropRevealFromAddress();
    expect(window.location.pathname + window.location.hash).toBe("/report/quotes/#section-3");
  });

  it("is done once the quote has landed", async () => {
    window.history.replaceState(null, "", "/report/quotes/?reveal=q-p1-10#section-3");
    arriveAt("/report/quotes/?reveal=q-p1-10#section-3");
    await act(async () => {
      initFromQuotes([quote({ is_hidden: true })], true);
    });
    expect(window.location.search).toBe("");
    expect(window.location.hash).toBe("#section-3");
  });
});
