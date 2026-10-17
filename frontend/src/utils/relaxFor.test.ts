import { describe, expect, it } from "vitest";
import { EMPTY_TAG_FILTER, isQuoteVisible, relaxFor, type FilterState } from "./filter";
import { personToken } from "./searchTokens";
import type { QuoteResponse, TagResponse } from "./types";

function quote(overrides: Partial<QuoteResponse> = {}): QuoteResponse {
  return {
    dom_id: "q-p1-1", text: "The delivery took three weeks for a kettle", verbatim_excerpt: "",
    participant_id: "p1", session_id: "s1", speaker_name: "Alice", start_timecode: 10, end_timecode: 20,
    sentiment: "frustration", intensity: 2, researcher_context: null, quote_type: "experience",
    topic_label: "Delivery", is_starred: false, is_hidden: false, edited_text: null, tags: [],
    deleted_badges: [], proposed_tags: [], segment_index: 0, ...overrides,
  };
}
const tag = (name: string): TagResponse => ({ name, codebook_group: "General", colour_set: "ux", colour_index: 0 });
function filters(overrides: Partial<FilterState> = {}): FilterState {
  return { searchQuery: "", searchTokens: [], viewMode: "all", tagFilter: EMPTY_TAG_FILTER, hidden: {}, starred: {},
    tags: {}, edits: {}, ...overrides };
}
const kinds = (q: QuoteResponse, f: FilterState, all: string[] = []) => relaxFor(q, f, all).map((r) => r.kind);

describe("relaxFor", () => {
  it("changes nothing for a quote already in view", () => {
    expect(relaxFor(quote(), filters(), [])).toEqual([]);
  });

  it("names each thing keeping the quote out of view, in isQuoteVisible's order", () => {
    const q = quote({ tags: [tag("delivery")] });
    const f = filters({
      hidden: { "q-p1-1": true }, viewMode: "starred", searchQuery: "zebra",
      tagFilter: { unchecked: ["delivery"], noTagsUnchecked: false, clearAll: false },
      searchTokens: [personToken("p2")],
    });
    expect(kinds(q, f)).toEqual(["hidden", "starredOnly", "tagFilter", "searchText", "token"]);
  });

  it("ticks one of the quote's own tags again, leaving the others off", () => {
    const q = quote({ tags: [tag("Delivery"), tag("price")] });
    const f = filters({ tagFilter: { unchecked: ["delivery", "price", "trust"], noTagsUnchecked: false, clearAll: false } });
    const [r] = relaxFor(q, f, []);
    expect(r).toEqual({ kind: "tagFilter", next: { unchecked: ["price", "trust"], noTagsUnchecked: false, clearAll: false } });
  });

  it("ticks (No tags) again for an untagged quote", () => {
    const f = filters({ tagFilter: { unchecked: [], noTagsUnchecked: true, clearAll: false } });
    expect(relaxFor(quote(), f, [])).toEqual([{ kind: "tagFilter", next: { unchecked: [], noTagsUnchecked: false, clearAll: false } }]);
  });

  it("after Clear, ticks only the quote's first tag", () => {
    const q = quote({ tags: [tag("delivery")] });
    const f = filters({ tagFilter: { unchecked: [], noTagsUnchecked: false, clearAll: true } });
    expect(relaxFor(q, f, ["delivery", "price", "trust"])).toEqual([
      { kind: "tagFilter", next: { clearAll: false, unchecked: ["price", "trust"], noTagsUnchecked: true } },
    ]);
  });

  it("drops only the tokens the quote fails", () => {
    const own = personToken("p1");
    const other = personToken("p2");
    const r = relaxFor(quote(), filters({ searchTokens: [own, other] }), []);
    expect(r).toEqual([{ kind: "token", token: other }]);
  });

  it("each change, applied, brings the quote into view", () => {
    const q = quote({ tags: [tag("delivery")] });
    let f = filters({
      viewMode: "starred", searchQuery: "zebra",
      tagFilter: { unchecked: ["delivery"], noTagsUnchecked: false, clearAll: false },
      searchTokens: [personToken("p2")],
    });
    for (const r of relaxFor(q, f, ["delivery"])) {
      if (r.kind === "starredOnly") f = { ...f, viewMode: "all" };
      if (r.kind === "tagFilter") f = { ...f, tagFilter: r.next };
      if (r.kind === "searchText") f = { ...f, searchQuery: "" };
      if (r.kind === "token") f = { ...f, searchTokens: f.searchTokens.filter((t) => t !== r.token) };
    }
    expect(isQuoteVisible(q, f)).toBe(true);
  });

  it("agrees with isQuoteVisible on every combination of the five checks", () => {
    const q = quote({ tags: [tag("delivery")] });
    for (let mask = 0; mask < 32; mask++) {
      const f = filters({
        hidden: mask & 1 ? { "q-p1-1": true } : {},
        viewMode: mask & 2 ? "starred" : "all",
        tagFilter: mask & 4 ? { unchecked: ["delivery"], noTagsUnchecked: false, clearAll: false } : EMPTY_TAG_FILTER,
        searchQuery: mask & 8 ? "zebra" : "",
        searchTokens: mask & 16 ? [personToken("p2")] : [],
      });
      expect(relaxFor(q, f, []).length === 0).toBe(isQuoteVisible(q, f));
    }
  });
});
