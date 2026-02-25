import { filterQuotes, isQuoteVisible, EMPTY_TAG_FILTER } from "./filter";
import type { FilterState } from "./filter";
import type { QuoteResponse, TagResponse } from "./types";

// ── Helpers ─────────────────────────────────────────────────────────────

function makeQuote(overrides: Partial<QuoteResponse> = {}): QuoteResponse {
  return {
    dom_id: "q-p1-1",
    text: "This is a test quote about usability",
    verbatim_excerpt: "test quote",
    participant_id: "p1",
    session_id: "s1",
    speaker_name: "Alice",
    start_timecode: 10,
    end_timecode: 20,
    sentiment: "frustration",
    intensity: 2,
    researcher_context: null,
    quote_type: "experience",
    topic_label: "Usability",
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

function makeTag(name: string): TagResponse {
  return { name, codebook_group: "General", colour_set: "ux", colour_index: 0 };
}

function baseFilter(overrides: Partial<FilterState> = {}): FilterState {
  return {
    searchQuery: "",
    viewMode: "all",
    tagFilter: EMPTY_TAG_FILTER,
    hidden: {},
    starred: {},
    tags: {},
    ...overrides,
  };
}

// ── Tests ───────────────────────────────────────────────────────────────

describe("isQuoteVisible", () => {
  // ── Hidden quotes ───────────────────────────────────────────────

  it("excludes hidden quotes", () => {
    const q = makeQuote({ dom_id: "q-p1-1" });
    const f = baseFilter({ hidden: { "q-p1-1": true } });
    expect(isQuoteVisible(q, f)).toBe(false);
  });

  it("includes non-hidden quotes", () => {
    const q = makeQuote();
    expect(isQuoteVisible(q, baseFilter())).toBe(true);
  });

  // ── View mode ───────────────────────────────────────────────────

  it("shows all quotes in 'all' mode", () => {
    const q = makeQuote();
    expect(isQuoteVisible(q, baseFilter({ viewMode: "all" }))).toBe(true);
  });

  it("shows starred quotes in 'starred' mode", () => {
    const q = makeQuote({ dom_id: "q-p1-1" });
    const f = baseFilter({ viewMode: "starred", starred: { "q-p1-1": true } });
    expect(isQuoteVisible(q, f)).toBe(true);
  });

  it("hides non-starred quotes in 'starred' mode", () => {
    const q = makeQuote({ dom_id: "q-p1-1" });
    const f = baseFilter({ viewMode: "starred" });
    expect(isQuoteVisible(q, f)).toBe(false);
  });

  // ── Tag filter ──────────────────────────────────────────────────

  it("shows all quotes when no tag filter is active", () => {
    const q = makeQuote();
    expect(isQuoteVisible(q, baseFilter())).toBe(true);
  });

  it("hides quotes when clearAll is true", () => {
    const q = makeQuote();
    const f = baseFilter({
      tagFilter: { unchecked: [], noTagsUnchecked: false, clearAll: true },
    });
    expect(isQuoteVisible(q, f)).toBe(false);
  });

  it("hides quotes with no tags when noTagsUnchecked is true", () => {
    const q = makeQuote({ tags: [] });
    const f = baseFilter({
      tagFilter: { unchecked: [], noTagsUnchecked: true, clearAll: false },
    });
    expect(isQuoteVisible(q, f)).toBe(false);
  });

  it("shows quotes with no tags when noTagsUnchecked is false", () => {
    const q = makeQuote({ tags: [] });
    const f = baseFilter({
      tagFilter: { unchecked: ["UX"], noTagsUnchecked: false, clearAll: false },
    });
    expect(isQuoteVisible(q, f)).toBe(true);
  });

  it("hides quotes when all their tags are unchecked", () => {
    const q = makeQuote({ dom_id: "q-p1-1", tags: [makeTag("UX")] });
    const f = baseFilter({
      tagFilter: { unchecked: ["UX"], noTagsUnchecked: false, clearAll: false },
    });
    expect(isQuoteVisible(q, f)).toBe(false);
  });

  it("shows quotes when at least one tag is checked", () => {
    const q = makeQuote({
      dom_id: "q-p1-1",
      tags: [makeTag("UX"), makeTag("Trust")],
    });
    const f = baseFilter({
      tagFilter: { unchecked: ["UX"], noTagsUnchecked: false, clearAll: false },
    });
    expect(isQuoteVisible(q, f)).toBe(true);
  });

  it("tag filter is case-insensitive", () => {
    const q = makeQuote({ dom_id: "q-p1-1", tags: [makeTag("Usability")] });
    const f = baseFilter({
      tagFilter: { unchecked: ["usability"], noTagsUnchecked: false, clearAll: false },
    });
    expect(isQuoteVisible(q, f)).toBe(false);
  });

  it("uses store tags over server tags", () => {
    const q = makeQuote({ dom_id: "q-p1-1", tags: [makeTag("UX")] });
    const f = baseFilter({
      tags: { "q-p1-1": [makeTag("Trust")] },
      tagFilter: { unchecked: ["UX"], noTagsUnchecked: false, clearAll: false },
    });
    // Store has "Trust", not "UX", so the quote is visible
    expect(isQuoteVisible(q, f)).toBe(true);
  });

  // ── Search ──────────────────────────────────────────────────────

  it("ignores search queries shorter than 3 chars", () => {
    const q = makeQuote({ text: "Hello" });
    const f = baseFilter({ searchQuery: "He" });
    expect(isQuoteVisible(q, f)).toBe(true);
  });

  it("matches search query against quote text", () => {
    const q = makeQuote({ text: "This is about usability testing" });
    const f = baseFilter({ searchQuery: "usability" });
    expect(isQuoteVisible(q, f)).toBe(true);
  });

  it("hides quotes that don't match search", () => {
    const q = makeQuote({ text: "Something else entirely" });
    const f = baseFilter({ searchQuery: "usability" });
    expect(isQuoteVisible(q, f)).toBe(false);
  });

  it("search is case-insensitive", () => {
    const q = makeQuote({ text: "Usability is important" });
    const f = baseFilter({ searchQuery: "usability" });
    expect(isQuoteVisible(q, f)).toBe(true);
  });

  it("matches search against speaker name", () => {
    const q = makeQuote({ speaker_name: "Alice" });
    const f = baseFilter({ searchQuery: "alice" });
    expect(isQuoteVisible(q, f)).toBe(true);
  });

  it("matches search against tag names", () => {
    const q = makeQuote({ dom_id: "q-p1-1", tags: [makeTag("Navigation")] });
    const f = baseFilter({ searchQuery: "navigation" });
    expect(isQuoteVisible(q, f)).toBe(true);
  });

  it("matches search against sentiment", () => {
    const q = makeQuote({ sentiment: "frustration" });
    const f = baseFilter({ searchQuery: "frustration" });
    expect(isQuoteVisible(q, f)).toBe(true);
  });

  it("prefers edited_text over text for search", () => {
    const q = makeQuote({ text: "original text", edited_text: "edited version" });
    expect(isQuoteVisible(q, baseFilter({ searchQuery: "edited" }))).toBe(true);
    expect(isQuoteVisible(q, baseFilter({ searchQuery: "original" }))).toBe(false);
  });

  it("matches search against store tags", () => {
    const q = makeQuote({ dom_id: "q-p1-1", tags: [] });
    const f = baseFilter({
      searchQuery: "navigation",
      tags: { "q-p1-1": [makeTag("Navigation")] },
    });
    expect(isQuoteVisible(q, f)).toBe(true);
  });

  // ── Combined filters ────────────────────────────────────────────

  it("all filters combine (AND logic)", () => {
    const q = makeQuote({
      dom_id: "q-p1-1",
      text: "usability test",
      tags: [makeTag("UX")],
    });
    const f = baseFilter({
      searchQuery: "usability",
      viewMode: "starred",
      starred: { "q-p1-1": true },
      tagFilter: { unchecked: [], noTagsUnchecked: false, clearAll: false },
    });
    expect(isQuoteVisible(q, f)).toBe(true);
  });

  it("fails if any filter rejects", () => {
    const q = makeQuote({
      dom_id: "q-p1-1",
      text: "usability test",
    });
    // Starred mode but quote is not starred
    const f = baseFilter({
      searchQuery: "usability",
      viewMode: "starred",
    });
    expect(isQuoteVisible(q, f)).toBe(false);
  });
});

describe("filterQuotes", () => {
  it("filters an array of quotes", () => {
    const quotes = [
      makeQuote({ dom_id: "q-p1-1", text: "usability test" }),
      makeQuote({ dom_id: "q-p1-2", text: "something else" }),
      makeQuote({ dom_id: "q-p1-3", text: "usability rocks" }),
    ];
    const f = baseFilter({ searchQuery: "usability" });
    const result = filterQuotes(quotes, f);
    expect(result).toHaveLength(2);
    expect(result.map((q) => q.dom_id)).toEqual(["q-p1-1", "q-p1-3"]);
  });

  it("returns empty array when all filtered out", () => {
    const quotes = [makeQuote({ dom_id: "q-p1-1" })];
    const f = baseFilter({ hidden: { "q-p1-1": true } });
    expect(filterQuotes(quotes, f)).toEqual([]);
  });

  it("returns all quotes when no filters active", () => {
    const quotes = [makeQuote({ dom_id: "q-p1-1" }), makeQuote({ dom_id: "q-p1-2" })];
    expect(filterQuotes(quotes, baseFilter())).toHaveLength(2);
  });
});
