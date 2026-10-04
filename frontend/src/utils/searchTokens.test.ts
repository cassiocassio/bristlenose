import { describe, expect, it } from "vitest";
import { syntheticProject } from "./searchSynthetic";
import {
  canMention,
  personToken,
  sameSubject,
  tagToken,
  takeCodeTokens,
  tokenHighlightTerms,
  tokenMatches,
  type PersonMode,
  type SearchToken,
  type TagMode,
} from "./searchTokens";
import type { QuoteResponse, TagResponse } from "./types";

const T = (name: string): TagResponse => ({ name, codebook_group: "g", colour_set: "ux", colour_index: 0 });

function Q(code: string, text: string, tags: TagResponse[] = [], extra: Partial<QuoteResponse> = {}): QuoteResponse {
  return {
    dom_id: `${code}-${text.slice(0, 12)}`,
    text,
    verbatim_excerpt: text,
    participant_id: code,
    session_id: "s1",
    speaker_name: code,
    start_timecode: 0,
    end_timecode: 1,
    sentiment: null,
    intensity: 1,
    researcher_context: null,
    quote_type: "screen_specific",
    topic_label: "",
    is_starred: false,
    is_hidden: false,
    edited_text: null,
    tags,
    deleted_badges: [],
    proposed_tags: [],
    segment_index: 0,
    ...extra,
  };
}

const tom = personToken("p2", { full_name: "Tom Fletcher", short_name: "Tom" });
const as = (t: SearchToken, mode: PersonMode | TagMode) => ({ ...t, mode }) as SearchToken;

describe("person tokens", () => {
  const byTom = Q("p2", "the delivery was £45");
  const aboutTom = Q("p1", "Tom said it was cheaper online");
  const neither = Q("p1", "I measured twice");

  it("said by: only the person's own quotes", () => {
    expect([byTom, aboutTom, neither].map((q) => tokenMatches(q, tom))).toEqual([true, false, false]);
  });

  it("not: everyone else's", () => {
    const not = as(tom, "not");
    expect([byTom, aboutTom, neither].map((q) => tokenMatches(q, not))).toEqual([false, true, true]);
  });

  it("mentions: quotes whose text names them", () => {
    const m = as(tom, "mentions");
    expect([byTom, aboutTom, neither].map((q) => tokenMatches(q, m))).toEqual([false, true, false]);
  });

  it("mentions matches whole words: Tom's yes, Tomorrow no", () => {
    const m = as(tom, "mentions");
    expect(tokenMatches(Q("p1", "that was Tom's idea"), m)).toBe(true);
    expect(tokenMatches(Q("p1", "Tomorrow I'll check"), m)).toBe(false);
  });

  it("mentions finds the full name and the short one, accents folded", () => {
    const jose = as(personToken("p4", { full_name: "José Núñez", short_name: "José" }), "mentions");
    expect(tokenMatches(Q("p1", "I asked Jose about it"), jose)).toBe(true);
    expect(tokenMatches(Q("p1", "Mr Nunez agreed"), jose)).toBe(false); // surname alone is not a listed name
    expect(tokenMatches(Q("p1", "José Núñez agreed"), jose)).toBe(true);
  });

  it("mentions reads the researcher's edit, not the original", () => {
    const m = as(tom, "mentions");
    expect(tokenMatches(Q("p1", "he said so", [], { edited_text: "Tom said so" }), m)).toBe(true);
    expect(tokenMatches(Q("p1", "Tom said so", [], { edited_text: "he said so" }), m)).toBe(false);
    // An edit made this session lives in the store and wins over both.
    const q = Q("p1", "Tom said so");
    expect(tokenMatches(q, m, undefined, { [q.dom_id]: "he said so" })).toBe(false);
    expect(tokenMatches(Q("p1", "he said so"), m, undefined, { "p1-he said so": "Tom said so" })).toBe(true);
  });

  it("mentions a Latin name followed or surrounded by Chinese or Japanese", () => {
    const m = as(tom, "mentions");
    expect(tokenMatches(Q("p1", "Tomさんが言った"), m)).toBe(true);
    expect(tokenMatches(Q("p1", "我和Tom说过"), m)).toBe(true);
  });

  it("does not mention a different Korean name that shares the first syllables", () => {
    const kim = as(personToken("p8", { full_name: "김민지", short_name: "" }), "mentions");
    expect(tokenMatches(Q("p1", "김민직이 왔다"), kim)).toBe(false);
  });

  it("mentions a Korean name with a particle after it, and a Japanese name mid-sentence", () => {
    const kim = as(personToken("p8", { full_name: "김민지", short_name: "" }), "mentions");
    expect(tokenMatches(Q("p1", "김민지가 먼저 말했어요"), kim)).toBe(true);
    const hanako = as(personToken("p6", { full_name: "山田 花子", short_name: "花子" }), "mentions");
    expect(tokenMatches(Q("p1", "花子さんが言いました"), hanako)).toBe(true);
  });
});

describe("tag tokens", () => {
  const hc = tagToken(T("hidden costs"));
  const tagged = Q("p1", "the total jumped", [T("Hidden Costs")]);
  const saysIt = Q("p1", "there were hidden costs everywhere");
  const neither = Q("p1", "fine");

  it("tagged: carries the tag, any case", () => {
    expect([tagged, saysIt, neither].map((q) => tokenMatches(q, hc))).toEqual([true, false, false]);
  });

  it("not tagged: everything that doesn't", () => {
    expect([tagged, saysIt, neither].map((q) => tokenMatches(q, as(hc, "not")))).toEqual([false, true, true]);
  });

  it("text contains: the words, whether or not anyone coded them", () => {
    expect([tagged, saysIt, neither].map((q) => tokenMatches(q, as(hc, "contains")))).toEqual([
      false,
      true,
      false,
    ]);
  });

  it("text contains matches whole words: price, not pricey", () => {
    const price = as(tagToken(T("price")), "contains");
    expect(tokenMatches(Q("p1", "the price went up"), price)).toBe(true);
    expect(tokenMatches(Q("p1", "a bit pricey"), price)).toBe(false);
  });

  it("tagged reads the store's tag edits over what the server sent", () => {
    const edits = { [tagged.dom_id]: [] as TagResponse[], [neither.dom_id]: [T("hidden costs")] };
    expect(tokenMatches(tagged, hc, edits)).toBe(false);
    expect(tokenMatches(neither, hc, edits)).toBe(true);
  });
});

describe("building tokens", () => {
  it("collects a person's names once, without the bare code", () => {
    expect(personToken("p3", { full_name: "Priya Shah", short_name: "Priya" }, "Priya")).toEqual({
      kind: "person",
      code: "p3",
      names: ["Priya Shah", "Priya"],
      mode: "said",
    });
    expect(personToken("p7", undefined, "p7").names).toEqual([]);
  });

  it("can't offer 'mentions' for a person known only by code", () => {
    expect(canMention(personToken("p7"))).toBe(false);
    expect(canMention(tom)).toBe(true);
  });

  it("knows two tokens name the same subject whatever their meaning", () => {
    expect(sameSubject(tom, as(tom, "not"))).toBe(true);
    expect(sameSubject(tagToken(T("Trust")), tagToken(T("trust")))).toBe(true);
    expect(sameSubject(tom, tagToken(T("p2")))).toBe(false);
  });

  it("highlights only for the meanings that look in the text", () => {
    expect(tokenHighlightTerms(tom)).toEqual([]);
    expect(tokenHighlightTerms(as(tom, "not"))).toEqual([]);
    expect(tokenHighlightTerms(as(tom, "mentions")).map((t) => t.text)).toEqual(["tom fletcher", "tom"]);
    expect(tokenHighlightTerms(as(tagToken(T("Trust")), "contains")).map((t) => t.text)).toEqual(["trust"]);
  });
});

// ── Invariants over a synthetic project ─────────────────────────────────

describe("token invariants on a synthetic project", () => {
  const project = syntheticProject({ seed: 5, sessions: 40, quotesPerSession: 8, extraTags: 10 });
  const count = (token: SearchToken) => project.quotes.filter((q) => tokenMatches(q, token)).length;
  const total = project.quotes.length;

  it.each(["p1", "p3", "p6", "p8"])("said-by and not split %s's project exactly", (code) => {
    const t = personToken(code, project.people[code]);
    expect(count(t)).toBeGreaterThan(0);
    expect(count(t) + count(as(t, "not"))).toBe(total);
  });

  it.each(["hidden costs", "delivery time", "trust"])("tagged and not tagged split %j exactly", (name) => {
    const t = tagToken(T(name));
    expect(count(t)).toBeGreaterThan(0);
    expect(count(t) + count(as(t, "not"))).toBe(total);
  });

  it("text contains agrees with an independently written whole-word check", () => {
    for (const name of ["delivery", "price", "checkout"]) {
      const re = new RegExp(`(^|[^\\p{L}\\p{N}])${name}(?![\\p{L}\\p{N}])`, "iu");
      const expected = project.quotes.filter((q) => re.test(q.text)).length;
      expect(count(as(tagToken(T(name)), "contains"))).toBe(expected);
      expect(expected).toBeGreaterThan(0);
    }
  });

  it("mentions agrees with an independently written whole-word check of each name", () => {
    let found = 0;
    for (const [code, person] of Object.entries(project.people)) {
      const names = [person.full_name, person.short_name].filter(Boolean);
      const res = names.map((n) => new RegExp(`(^|[^\\p{L}\\p{N}])${n}(?![\\p{L}\\p{N}])`, "iu"));
      const expected = project.quotes.filter((q) => res.some((re) => re.test(q.text))).length;
      expect(count(as(personToken(code, person), "mentions"))).toBe(expected);
      found += expected;
    }
    // Not vacuous: the generator names people, and "Priya" must not match "Priyanka".
    expect(found).toBeGreaterThan(0);
    expect(count(as(personToken("p3", project.people.p3), "mentions"))).toBeGreaterThan(0);
  });
});

describe("takeCodeTokens: a code typed at the start becomes a token once a space follows", () => {
  const codes = ["p3", "m1", "m11"];
  const codeOf = (w: string) => codes.find((c) => c === w.toLowerCase()) ?? null;
  const take = (q: string) => takeCodeTokens(q, codeOf);

  it("takes a code and its space, case-insensitively", () => {
    expect(take("p3 ")).toEqual({ query: "", codes: ["p3"] });
    expect(take("P3 ")).toEqual({ query: "", codes: ["p3"] });
    expect(take("p3 late")).toEqual({ query: "late", codes: ["p3"] });
    expect(take(" p3 late")).toEqual({ query: "late", codes: ["p3"] });
  });

  it("only at the start, as Mail's tokens-first field: later in the text a code is text", () => {
    // Not an m1 token plus the run "the motorway", which nobody typed.
    expect(take("the M1 motorway")).toEqual({ query: "the M1 motorway", codes: [] });
    expect(take("late p3 ")).toEqual({ query: "late p3 ", codes: [] });
    expect(take("p3 late m1 ")).toEqual({ query: "late m1 ", codes: ["p3"] });
  });

  it("waits for the space: m1 may be the start of m11", () => {
    expect(take("m1")).toEqual({ query: "m1", codes: [] });
    expect(take("late m1")).toEqual({ query: "late m1", codes: [] });
    expect(take("m11 ")).toEqual({ query: "", codes: ["m11"] });
  });

  it("leaves words that are not codes, and codes inside a quoted phrase", () => {
    expect(take("p33 ")).toEqual({ query: "p33 ", codes: [] });
    expect(take("pricing ")).toEqual({ query: "pricing ", codes: [] });
    expect(take('"p3 said" ')).toEqual({ query: '"p3 said" ', codes: [] });
    expect(take("“p3 said” p3 ")).toEqual({ query: "“p3 said” p3 ", codes: [] });
  });

  it("takes several, each once, and returns the query untouched when none", () => {
    expect(take("p3 m1 p3 late")).toEqual({ query: "late", codes: ["p3", "m1"] });
    const q = "  spaced   out ";
    expect(take(q).query).toBe(q);
  });
});

