import { describe, expect, it } from "vitest";
import {
  EMPTY_LIVE,
  liveAcceptedFor,
  liveTentative,
  mergedProposals,
  mergedTagMap,
  mergedTags,
  storeCarries,
  type LiveOverlay,
  type LiveTag,
} from "./liveTags";
import { filterQuotes, EMPTY_TAG_FILTER, type FilterState } from "./filter";
import { filterStateOf, type QuotesState } from "../contexts/QuotesContext";
import type { QuoteResponse, TagResponse } from "./types";

/** A landed tag of definition 100 + id. */
function liveTag(id: number, domId: string, name: string, shown: LiveTag["shown"]): LiveTag {
  return {
    id, dom_id: domId, tag_definition_id: 100 + id, tag_name: name, group_name: "G",
    colour_set: "ux", colour_index: 0, confidence: 0.8, rationale: "", shown,
  };
}

function overlay(tags: LiveTag[], extra: { held?: number[]; waiting?: string[] } = {}): LiveOverlay {
  const byQuote: Record<string, LiveTag[]> = {};
  for (const t of tags) (byQuote[t.dom_id] ??= []).push(t);
  return {
    byQuote,
    held: new Set([...tags.map((t) => t.id), ...(extra.held ?? [])]),
    waitingAccept: new Set(extra.waiting ?? []),
  };
}

const tag = (name: string, id?: number, source?: string): TagResponse =>
  ({ id, name, codebook_group: "G", colour_set: "ux", colour_index: 0, source });

describe("liveTags", () => {
  it("passes the store's own arrays through when nothing lands", () => {
    const tags = [tag("a", 5)];
    expect(mergedTags("q1", tags, EMPTY_LIVE)).toBe(tags);
    expect(mergedProposals("q1", [], tags, EMPTY_LIVE)).toEqual([]);
    const map = { q1: tags };
    expect(mergedTagMap(map, EMPTY_LIVE, () => [])).toBe(map);
  });

  it("adds a landed accepted tag once, even when the quote carries its definition too", () => {
    const live = overlay([liveTag(1, "q1", "Trust", "accepted")]);
    expect(mergedTags("q1", [], live).map((t) => t.id)).toEqual([101]);
    expect(mergedTags("q1", [tag("Trust", 101, "autocode")], live)).toHaveLength(1);
    // A tag typed since the last read has no id yet: matched by name.
    expect(mergedTags("q1", [tag("trust")], live).map((t) => t.name)).toEqual(["trust"]);
  });

  it("matches by definition, never by name: another codebook's same-named tag is another tag", () => {
    const live = overlay([liveTag(1, "q1", "Trust", "accepted")]);
    expect(mergedTags("q1", [tag("Trust", 999, "autocode")], live).map((t) => t.id)).toEqual([999, 101]);
    const tentative = overlay([liveTag(1, "q1", "Trust", "tentative")]);
    expect(mergedProposals("q1", [], [tag("Trust", 999, "autocode")], tentative).map((p) => p.id)).toEqual([1]);
  });

  it("holds back only the AutoCode-made tag of the definition the server accepted, until it lands", () => {
    const live = overlay([liveTag(1, "q1", "Trust", "tentative")], { waiting: ["q1|101"] });
    expect(mergedTags("q1", [tag("Trust", 101, "autocode"), tag("Other", 7, "human")], live).map((t) => t.id)).toEqual([7]);
    // …and the card shows it tentative meanwhile.
    expect(mergedProposals("q1", [], [tag("Other", 7, "human")], live).map((p) => p.id)).toEqual([1]);
  });

  it("never holds back a researcher's own tag, or another codebook's of the same name", () => {
    const live = overlay([liveTag(1, "q1", "Trust", "tentative")], { waiting: ["q1|101"] });
    const own = [tag("Trust", 101, "human"), tag("Trust", 999, "autocode")];
    expect(mergedTags("q1", own, live)).toBe(own);
  });

  it("draws a held proposal from the overlay only, never twice", () => {
    const live = overlay([liveTag(1, "q1", "Trust", "tentative")], { held: [2] });
    const store = [
      { id: 1, tag_name: "Trust", group_name: "G", colour_set: "ux", colour_index: 0, confidence: 0.8, rationale: "" },
      { id: 2, tag_name: "Doubt", group_name: "G", colour_set: "ux", colour_index: 0, confidence: 0.5, rationale: "" },
      { id: 3, tag_name: "Older", group_name: "G", colour_set: "ux", colour_index: 0, confidence: 0.5, rationale: "" },
    ];
    // 2 is held and not landed: not shown. 3 is not the playback's: shown as before.
    expect(mergedProposals("q1", store, [], live).map((p) => p.id)).toEqual([3, 1]);
  });

  it("drops a landed tentative tag whose definition the quote already carries", () => {
    const live = overlay([liveTag(1, "q1", "Trust", "tentative")]);
    expect(mergedProposals("q1", [], [tag("Trust", 101, "human")], live)).toEqual([]);
  });

  it("finds the live rows behind a card's controls, by the tag's row when it has one", () => {
    const live = overlay([liveTag(1, "q1", "Trust", "accepted"), liveTag(2, "q2", "Doubt", "tentative")]);
    expect(liveAcceptedFor("q1", "Trust", 101, live)?.id).toBe(1);
    expect(liveAcceptedFor("q1", "Trust", 999, live)).toBeNull();
    expect(liveAcceptedFor("q1", "trust", undefined, live)?.id).toBe(1);
    expect(storeCarries("q1", [tag("Trust", 101, "autocode")], liveTag(1, "q1", "Trust", "accepted"), live)).toBe(true);
    expect(storeCarries("q1", [tag("Trust", 999, "autocode")], liveTag(1, "q1", "Trust", "accepted"), live)).toBe(false);
    expect(liveTentative("q2", 2, live)?.id).toBe(2);
    expect(liveTentative("q2", 9, live)).toBeNull();
  });
});

describe("a filtered Quotes list takes new matches live (D10)", () => {
  const quote = (domId: string): QuoteResponse => ({ dom_id: domId, tags: [], proposed_tags: [] }) as unknown as QuoteResponse;

  it("counts a landed accepted tag in the filters", () => {
    const quotes = [quote("q1"), quote("q2")];
    const base = {
      searchQuery: "", searchTokens: [{ kind: "tag", name: "Trust", mode: "tagged" }],
      viewMode: "all", tagFilter: EMPTY_TAG_FILTER, hidden: {}, starred: {}, tags: {}, edits: {},
      live: EMPTY_LIVE,
    } as unknown as QuotesState;
    const before = filterQuotes(quotes, filterStateOf(base) as FilterState);
    const landed = { ...base, live: overlay([liveTag(1, "q2", "Trust", "accepted")]) };
    const after = filterQuotes(quotes, filterStateOf(landed) as FilterState);
    expect(after.length).toBeGreaterThan(before.length);
    expect(after.map((q) => q.dom_id)).toContain("q2");
  });
});
