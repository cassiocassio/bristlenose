/**
 * The search bridge, web side, against the shared contract fixture
 * (`tests/fixtures/search-bridge-contract.json`, docs/design-search.md §7).
 * Swift decodes the same `wire` payloads (BridgeSearchContractTests.swift), so
 * a shape change here without the other side fails one of the two suites.
 */

import { beforeEach, describe, expect, it, vi } from "vitest";

import contractJson from "../../../tests/fixtures/search-bridge-contract.json";
import {
  _setNativeSearchPeople,
  applyNativeSearchAction,
  nativeSuggestions,
} from "../components/NativeSearchSync";
import {
  addSearchToken,
  getQuotesSnapshot,
  initFromQuotes,
  resetStore,
  setSearchQuery,
} from "../contexts/QuotesContext";
import { suggestionsToWire, tokensToWire } from "./searchBridge";
import type { Suggestion } from "./searchSuggest";
import type { SearchToken } from "./searchTokens";
import type { QuoteResponse, TagResponse } from "./types";

const contract = contractJson as unknown as {
  web_to_native: {
    search_suggestions: Array<{
      name: string;
      input: { query: string; suggestions: Suggestion[] };
      wire: unknown;
    }>;
    quotes_filter_tokens: Array<{ name: string; input: SearchToken[]; wire: unknown }>;
  };
  native_to_web: {
    project: { people: Record<string, { full_name: string; short_name: string }>; quote_tags: string[] };
    cases: Array<{
      name: string;
      action: string;
      payload: unknown;
      before: { query: string; tokens: SearchToken[] };
      effect: { query: string; tokens: SearchToken[] };
    }>;
  };
};

function tag(name: string): TagResponse {
  return { name, codebook_group: "", colour_set: "", colour_index: 0 } as TagResponse;
}

function quote(n: number, participant: string, speaker: string, tags: TagResponse[]): QuoteResponse {
  return {
    dom_id: `q-${participant}-${n}`, text: `Quote ${n} about zoning and pricing`, verbatim_excerpt: "",
    participant_id: participant, session_id: "s1", speaker_name: speaker, start_timecode: n,
    end_timecode: n + 5, sentiment: null, intensity: 1, researcher_context: null,
    quote_type: "general_context", topic_label: "", is_starred: false, is_hidden: false,
    edited_text: null, tags, deleted_badges: [], proposed_tags: [], segment_index: -1,
  };
}

describe("web → native: the payloads match the contract", () => {
  for (const c of contract.web_to_native.search_suggestions) {
    it(`search-suggestions: ${c.name}`, () => {
      expect(suggestionsToWire(c.input.query, c.input.suggestions)).toEqual(c.wire);
    });
  }
  for (const c of contract.web_to_native.quotes_filter_tokens) {
    it(`quotes-filter tokens: ${c.name}`, () => {
      expect(tokensToWire(c.input)).toEqual(c.wire);
    });
  }

  it("typed offsets are UTF-16 code units, so they land on the typed letters", () => {
    const wire = contract.web_to_native.search_suggestions[0].wire as {
      rows: Array<{ label: string; typed: Array<[number, number]> }>;
    };
    const person = wire.rows[1];
    const [[start, end]] = person.typed;
    expect(person.label.slice(start, end)).toBe("Zo");
  });
});

describe("native → web: actions change the store as the contract says", () => {
  beforeEach(() => {
    resetStore();
    vi.restoreAllMocks();
    const { people, quote_tags } = contract.native_to_web.project;
    _setNativeSearchPeople(people);
    initFromQuotes(
      [
        quote(1, "p3", "Zoë", [tag(quote_tags[0])]),
        quote(2, "p4", "Sam", [tag(quote_tags[1])]),
      ],
      true,
    );
  });

  for (const c of contract.native_to_web.cases) {
    it(c.name, () => {
      setSearchQuery(c.before.query);
      for (const token of c.before.tokens) addSearchToken(token);

      expect(applyNativeSearchAction(c.action, c.payload)).toBe(true);

      const after = getQuotesSnapshot();
      expect(after.searchQuery).toBe(c.effect.query);
      expect(after.searchTokens).toEqual(c.effect.tokens);
    });
  }

  it("leaves actions it does not own to the caller's switch", () => {
    expect(applyNativeSearchAction("toggleLeftPanel", undefined)).toBe(false);
  });

  it("survives payloads that are missing or the wrong shape", () => {
    for (const action of ["applySearchSuggestion", "setSearchTokenMode", "removeSearchToken"]) {
      for (const payload of [undefined, null, 7, "x", [], { id: 3 }, { subject: "p3" }, { subject: { kind: "person" } }]) {
        expect(() => applyNativeSearchAction(action, payload)).not.toThrow();
      }
    }
    expect(getQuotesSnapshot().searchTokens).toEqual([]);
  });
});

describe("what the native menu is sent", () => {
  beforeEach(() => {
    resetStore();
    _setNativeSearchPeople({ p3: { full_name: "Zoë Ng", short_name: "Zoë" } });
    initFromQuotes(
      [
        quote(1, "p3", "Zoë", [tag("Zoning")]),
        quote(2, "p3", "Zoë", []),
        quote(3, "p4", "Sam", [tag("Pricing")]),
      ],
      true,
    );
  });

  it("offers the person and the tag the query recognises, with counts", () => {
    setSearchQuery("zo");
    const { rows } = nativeSuggestions(getQuotesSnapshot());
    const byId = Object.fromEntries(rows.map((r) => [r.id, r]));
    expect(byId["person:p3"]).toMatchObject({ kind: "person", code: "p3", count: 2 });
    expect(byId["tag:zoning"]).toMatchObject({ kind: "tag", label: "Zoning", count: 1 });
  });

  it("stops offering a person or tag once it is a token", () => {
    setSearchQuery("zo");
    applyNativeSearchAction("applySearchSuggestion", { id: "person:p3" });
    setSearchQuery("zo");
    const ids = nativeSuggestions(getQuotesSnapshot()).rows.map((r) => r.id);
    expect(ids).not.toContain("person:p3");
    expect(ids).toContain("tag:zoning");
  });

  it("an empty query sends an empty menu, which closes the native one", () => {
    expect(nativeSuggestions(getQuotesSnapshot())).toEqual({ query: "", rows: [] });
  });
});
