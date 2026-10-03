/**
 * TypeScript side of the search MATCHING contract.
 *
 * Reads `tests/fixtures/search-match-contract.json`, which the Python/SQLite
 * search core must also assert when it lands (docs/design-search.md D1), so a
 * query finds the same quotes on every surface. Imported, not read through
 * node:fs — `tsc -b` has no Node types here (see sharedFormatContract.test.ts).
 */

import { describe, expect, it } from "vitest";
import contractJson from "../../../tests/fixtures/search-match-contract.json";
import { isActiveQuery, markRanges, matchesAll, parseQuery } from "./searchMatch";

interface MatchCase {
  why: string;
  text: string;
  query: string;
  match: boolean;
  marked: string[];
}

const contract = contractJson as unknown as {
  active: [string, boolean, string][];
  match: MatchCase[];
  known_limits: MatchCase[];
};

function marked(text: string, query: string): string[] {
  return markRanges(text, parseQuery(query)).map(([s, e]) => text.slice(s, e));
}

describe("search matching contract", () => {
  it.each(contract.active)("isActiveQuery(%j) is %s (%s)", (query, expected) => {
    expect(isActiveQuery(query)).toBe(expected);
  });

  describe.each([
    ["rules", contract.match],
    ["known limits", contract.known_limits],
  ] as const)("%s", (_group, cases) => {
    it.each(cases.map((c) => [c.why, c] as const))("%s", (_why, c) => {
      expect(matchesAll([c.text], parseQuery(c.query))).toBe(c.match);
      expect(marked(c.text, c.query)).toEqual(c.marked);
    });
  });

  it("covers every rule in the spec at least once", () => {
    // A guard against the fixture shrinking: these are the §3 rules.
    const whys = contract.match.map((c) => c.why).join(" | ");
    for (const rule of ["any order", "phrase", "START", "accents", "Chinese", "whitespace"]) {
      expect(whys).toContain(rule);
    }
  });
});

describe("parseQuery", () => {
  it("splits words and keeps a quoted phrase whole", () => {
    expect(parseQuery('more "than the" shelf')).toEqual([
      { kind: "word", text: "more", anywhere: false },
      { kind: "phrase", text: "than the", anywhere: false },
      { kind: "word", text: "shelf", anywhere: false },
    ]);
  });

  it("folds terms the same way it folds text", () => {
    expect(parseQuery("JOSÉ").map((t) => t.text)).toEqual(["jose"]);
  });

  it("marks Chinese and Japanese terms as matching anywhere", () => {
    expect(parseQuery("東京 tokyo").map((t) => t.anywhere)).toEqual([true, false]);
  });

  it("ignores an empty pair of quotes", () => {
    expect(parseQuery('"" shelf')).toEqual([{ kind: "word", text: "shelf", anywhere: false }]);
  });
});

describe("matchesAll across fields", () => {
  it("lets each word match a different field", () => {
    const fields = ["the delivery was £45", "Tom Fletcher"];
    expect(matchesAll(fields, parseQuery("tom delivery"))).toBe(true);
    expect(matchesAll(fields, parseQuery("tom assembly"))).toBe(false);
  });
});
