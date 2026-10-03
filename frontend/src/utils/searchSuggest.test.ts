import { describe, expect, it } from "vitest";
import { suggest, type SearchPerson, type Suggestion } from "./searchSuggest";
import { syntheticProject } from "./searchSynthetic";
import type { QuoteResponse, TagResponse } from "./types";

// ── A small project whose every count can be checked by reading it ──────

const T = (name: string): TagResponse => ({
  name,
  codebook_group: "g",
  colour_set: "ux",
  colour_index: 0,
});

let n = 0;
function Q(code: string, speaker: string, text: string, tags: TagResponse[] = [], id?: string): QuoteResponse {
  return {
    dom_id: id ?? `q-${code}-${n++}`,
    text,
    verbatim_excerpt: text,
    participant_id: code,
    session_id: "s1",
    speaker_name: speaker,
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
  };
}

const quotes: QuoteResponse[] = [
  Q("p1", "Amira", "printed the receipt twice"),
  Q("p1", "Amira", "I trust them", [T("trust")], "hidden"),
  Q("p2", "Tom", "the delivery was £45", [T("hidden costs")]),
  Q("p2", "Tom", "assembly was extra", [T("delivery time")]),
  Q("p2", "Tom", "delivery time said Tuesday", [T("delivery time"), T("delivery")]),
  Q("p3", "Priya", "measured the alcove twice", [T("measurement")], "q-p3-first"),
  Q("p3", "Priya", "is it next day?"),
  ...Array.from({ length: 5 }, (_, i) =>
    Q("p30", "Paula", "the cost went up", i < 2 ? [T("price surprise")] : []),
  ),
  Q("p4", "José", "no sabía si la entrega costaba más"),
  Q("p5", "Алёна", "ещё раз"),
  Q("p6", "花子", "配送料が最後に分かって驚きました"),
  Q("p7", "p7", "fine"),
];

const people: Record<string, SearchPerson> = {
  m1: { full_name: "Sam Ortiz", short_name: "Sam" }, // moderator, no quotes
  p1: { full_name: "Amira Haddad", short_name: "Amira" },
  p2: { full_name: "Tom Fletcher", short_name: "Tom" },
  p3: { full_name: "Priya Shah", short_name: "Priya" },
  p30: { full_name: "Paula Reyes", short_name: "Paula" },
  p4: { full_name: "José Núñez", short_name: "José" },
  p5: { full_name: "Алёна Смирнова", short_name: "Алёна" },
  p6: { full_name: "山田 花子", short_name: "花子" },
  // p7 has a code and nothing else
};

const source = { quotes, people, isVisible: (q: QuoteResponse) => q.dom_id !== "hidden" };
const ids = (rows: Suggestion[]) => rows.map((r) => r.id);
const count = (rows: Suggestion[], id: string) => rows.find((r) => r.id === id)?.count;

describe("suggest — rows and counts", () => {
  it("offers free text, then a person, then a tag, each with what choosing it would show", () => {
    const rows = suggest("pri", source);
    expect(ids(rows)).toEqual(["text", "person:p3", "tag:price surprise"]);
    // "printed" (p1), Priya's two quotes by speaker name, Paula's two tagged "price surprise".
    expect(count(rows, "text")).toBe(5);
    expect(count(rows, "person:p3")).toBe(2);
    expect(count(rows, "tag:price surprise")).toBe(2);
  });

  it("names a person by their short name", () => {
    const row = suggest("shah", source).find((r) => r.kind === "person");
    expect(row).toMatchObject({ code: "p3", name: "Priya" });
  });

  it("puts an exact code first, ahead of a code with more quotes", () => {
    expect(ids(suggest("p3", source))).toEqual(["text", "person:p3", "person:p30"]);
  });

  it("keeps a free-text row with 0 when nothing matches, so ↩ still does what it says", () => {
    expect(suggest("p3", source)[0]).toEqual({ kind: "text", id: "text", query: "p3", count: 0 });
  });

  it("puts an exact tag first, ahead of a tag with more quotes", () => {
    expect(ids(suggest("delivery", source)).filter((id) => id.startsWith("tag:"))).toEqual([
      "tag:delivery",
      "tag:delivery time",
    ]);
  });

  it("caps each group at three, by count", () => {
    // Eight people start with "p"; the three with most quotes are offered.
    const people = suggest("p", source).filter((r) => r.kind === "person");
    expect(ids(people)).toEqual(["person:p30", "person:p2", "person:p3"]);
  });

  it("breaks a tie in count by code, in natural order (p4 before p30)", () => {
    const people = suggest("p", source, { cap: 10 }).filter((r) => r.kind === "person");
    expect(ids(people)).toEqual([
      "person:p30", "person:p2", "person:p3",
      "person:p1", "person:p4", "person:p5", "person:p6", "person:p7",
    ]);
  });

  it("offers no free-text row below two characters, but still recognises", () => {
    expect(suggest("p", source).some((r) => r.kind === "text")).toBe(false);
  });

  it("lets each word match a different field, and offers no person for a mixed query", () => {
    // Tom's three quotes: two say delivery, one is tagged "delivery time".
    expect(suggest("tom delivery", source)).toEqual([
      { kind: "text", id: "text", query: "tom delivery", count: 3 },
    ]);
  });

  it("never offers someone with no visible quotes", () => {
    expect(suggest("sam", source).filter((r) => r.kind === "person")).toEqual([]);
  });

  it("counts only what the researcher can see, and drops tags that only hidden quotes carry", () => {
    expect(ids(suggest("trust", source))).toEqual(["text"]);
    expect(count(suggest("amira", source), "person:p1")).toBe(1);
  });

  it("folds accents and scripts in names", () => {
    expect(ids(suggest("jose", source))).toContain("person:p4");
    expect(ids(suggest("алена", source))).toContain("person:p5");
  });

  it("recognises one Chinese or Japanese character, anywhere in a name", () => {
    const rows = suggest("花", source);
    expect(ids(rows)).toEqual(["text", "person:p6"]);
    expect(count(rows, "text")).toBe(1);
  });

  it("offers a code-only person with no name", () => {
    expect(suggest("p7", source).find((r) => r.kind === "person")).toMatchObject({
      code: "p7",
      name: null,
    });
  });

  it("leaves out people and tags already present as tokens", () => {
    const rows = suggest("pri", source, { excludeCodes: ["p3"], excludeTags: ["Price Surprise"] });
    expect(ids(rows)).toEqual(["text"]);
  });

  it("reads the store's tag edits over what the server sent", () => {
    const tags = { "q-p3-first": [T("priority")] };
    const rows = suggest("prio", { ...source, tags });
    expect(ids(rows)).toContain("tag:priority");
    expect(ids(suggest("measure", { ...source, tags }))).not.toContain("tag:measurement");
  });

  it("returns nothing for an empty query", () => {
    expect(suggest("", source)).toEqual([]);
    expect(suggest("   ", source)).toEqual([]);
  });
});

// ── Invariants over a synthetic project ─────────────────────────────────

describe("suggest — invariants on a synthetic project", () => {
  const project = syntheticProject({ seed: 7, sessions: 40, quotesPerSession: 8, extraTags: 30 });
  const src = { quotes: project.quotes, people: project.people };
  const QUERIES = ["p", "pri", "priya", "del", "delivery time", "price", "a", "花", "ал", "jos", "theme 1", "김", "zzq"];

  it("is deterministic for a seed, and varies with it", () => {
    const again = syntheticProject({ seed: 7, sessions: 40, quotesPerSession: 8, extraTags: 30 });
    expect(again).toEqual(project);
    expect(syntheticProject({ seed: 8, sessions: 40, quotesPerSession: 8 }).quotes).not.toEqual(
      project.quotes,
    );
  });

  it.each(QUERIES)("%j: groups in order, capped, unique, and never a zero-count recognition", (q) => {
    const rows = suggest(q, src);
    const order = { text: 0, person: 1, tag: 2 };
    const kinds = rows.map((r) => order[r.kind]);
    expect(kinds).toEqual([...kinds].sort());
    expect(new Set(ids(rows)).size).toBe(rows.length);
    expect(rows.filter((r) => r.kind === "person").length).toBeLessThanOrEqual(3);
    expect(rows.filter((r) => r.kind === "tag").length).toBeLessThanOrEqual(3);
    for (const r of rows) if (r.kind !== "text") expect(r.count).toBeGreaterThan(0);
  });

  it.each(QUERIES)("%j: every count agrees with an independent recount", (q) => {
    for (const r of suggest(q, src)) {
      if (r.kind === "person") {
        expect(r.count).toBe(project.quotes.filter((x) => x.participant_id === r.code).length);
      } else if (r.kind === "tag") {
        const name = r.tag.name.toLowerCase();
        expect(r.count).toBe(
          project.quotes.filter((x) => x.tags.some((t) => t.name.toLowerCase() === name)).length,
        );
      }
    }
  });

  // An oracle written a different way from searchMatch: a regex per word over
  // accent-stripped text. Only for queries whose words are plain ASCII, where
  // the two definitions must agree.
  function naiveCount(q: string): number {
    const strip = (x: string) => x.normalize("NFD").replace(/\p{M}/gu, "");
    const words = q.toLowerCase().split(/\s+/).filter(Boolean);
    const res = words.map((w) => new RegExp(`(^|[^\\p{L}\\p{N}])${w}`, "iu"));
    return project.quotes.filter((x) => {
      const fields = [x.text, x.speaker_name, ...x.tags.map((t) => t.name), x.sentiment ?? ""].map(strip);
      return res.every((re) => fields.some((f) => re.test(f)));
    }).length;
  }

  it.each(["delivery", "pri", "the delivery", "conf", "theme 1", "zzq"])(
    "%j: the free-text count agrees with an independently written matcher",
    (q) => {
      const text = suggest(q, src).find((r) => r.kind === "text");
      expect(text?.count).toBe(naiveCount(q));
    },
  );

  it("the oracle is not vacuous", () => {
    expect(naiveCount("delivery")).toBeGreaterThan(0);
    expect(naiveCount("zzq")).toBe(0);
  });

  it("never grows the free-text count by adding a word", () => {
    const text = (q: string) => suggest(q, src).find((r) => r.kind === "text")?.count ?? 0;
    expect(text("delivery bit")).toBeLessThanOrEqual(text("delivery"));
    expect(text("the delivery")).toBeLessThanOrEqual(text("delivery"));
  });

  it("finds the people the cast was built to exercise", () => {
    expect(ids(suggest("priya", src))[1]).toBe("person:p3"); // exact first, over Priyanka (p10)
    expect(ids(suggest("pri", src))).toEqual(expect.arrayContaining(["person:p3", "person:p10"]));
    expect(ids(suggest("ал", src))).toContain("person:p6");
    expect(ids(suggest("김", src))).toContain("person:p8");
  });
});

// ── Scale ───────────────────────────────────────────────────────────────

describe("suggest — scale", () => {
  it("answers each keystroke on 10,000 quotes and 300 tags well inside a frame budget", () => {
    // Generous bound: this catches a disaster (a quadratic loop, a cache that
    // never hits), not a regression of a few milliseconds on a busy CI runner.
    const big = syntheticProject({ seed: 1, sessions: 400, quotesPerSession: 25, extraTags: 290 });
    expect(big.quotes).toHaveLength(10_000);
    const src = { quotes: big.quotes, people: big.people };
    suggest("warm", src); // fills the fold cache, as the first keystroke would
    // Best of three per query, so one garbage-collection pause can't fail it.
    // Measured 3 Oct 2026 on an M-series Mac: 2–9 ms per keystroke warm.
    const bestOf3 = (q: string) =>
      Math.min(
        ...[0, 1, 2].map(() => {
          const t0 = performance.now();
          suggest(q, src);
          return performance.now() - t0;
        }),
      );
    const times = ["d", "de", "del", "deli", "deliv", "delivery", "delivery t", "p", "pri", "theme 2"].map(bestOf3);
    expect(Math.max(...times)).toBeLessThan(250);
  });
});
