import { describe, it, expect, beforeEach } from "vitest";
import { buildLeanQuotesText } from "../exportActions";
import { initFromQuotes, getQuotesSnapshot, resetStore } from "../../contexts/QuotesContext";
import type { QuoteResponse } from "../types";

function makeQuote(overrides: Partial<QuoteResponse> = {}): QuoteResponse {
  return {
    dom_id: "q-p1-1",
    text: "I was confused by the dashboard",
    verbatim_excerpt: "confused",
    participant_id: "p1",
    session_id: "s1",
    speaker_name: "Alice",
    start_timecode: 70,
    end_timecode: 80,
    sentiment: "frustration",
    intensity: 2,
    researcher_context: null,
    quote_type: "experience",
    topic_label: "Dashboard",
    is_starred: false,
    is_hidden: false,
    edited_text: null,
    tags: [],
    deleted_badges: [],
    proposed_tags: [],
    segment_index: 0,
    ...overrides,
  };
}

beforeEach(() => {
  resetStore();
});

describe("buildLeanQuotesText", () => {
  it("includes the display name by default (quote · code · name · timecode)", () => {
    initFromQuotes([makeQuote()]);
    const out = buildLeanQuotesText(getQuotesSnapshot(), ["q-p1-1"], false);
    expect(out).toBe("I was confused by the dashboard\tp1\tAlice\t1:10");
  });

  // PII boundary: anonymise must drop the display-name column entirely, while
  // keeping the participant code. A silent regression here leaks names into
  // every Miro/Slides paste — exactly the kind of failure unit tests exist for.
  it("drops the display name when anonymise=true, keeping the code", () => {
    initFromQuotes([makeQuote({ speaker_name: "Alice" })]);
    const out = buildLeanQuotesText(getQuotesSnapshot(), ["q-p1-1"], true);
    expect(out).toBe("I was confused by the dashboard\tp1\t1:10");
    expect(out).not.toContain("Alice");
  });

  it("never emits a name even when several quotes share one anonymised export", () => {
    initFromQuotes([
      makeQuote({ dom_id: "q-p1-1", speaker_name: "Alice", text: "one" }),
      makeQuote({ dom_id: "q-p2-1", participant_id: "p2", speaker_name: "Bob", text: "two" }),
    ]);
    const out = buildLeanQuotesText(getQuotesSnapshot(), ["q-p1-1", "q-p2-1"], true);
    expect(out).not.toContain("Alice");
    expect(out).not.toContain("Bob");
    expect(out.split("\n")).toHaveLength(2);
  });
});
