/**
 * The plural contract, held to CLDR itself.
 *
 * `tests/fixtures/cldr-plural-contract.json` is what the Python and Swift
 * plural rules are tested against (`tests/test_plural_category_parity.py`,
 * `PluralCategoryContractTests.swift`). But a contract the two sides agree
 * with can still be wrong: both were transcribed by hand, and so was the
 * fixture. Brazilian Portuguese said "other" at 0 in all three until 23 Oct
 * 2026 (#117), though CLDR puts 0 with 1 there, as in French.
 *
 * `Intl.PluralRules` is ICU's CLDR data, and it is also what i18next uses to
 * pick this frontend's own plural forms. So this file asserts the fixture
 * against an authority, and against what the web report actually renders.
 */

import { describe, expect, it } from "vitest";
// Imported, not read with node:fs: `tsc -b` type-checks tests with no
// @types/node in scope (see sharedFormatContract.test.ts).
import contract from "../../../tests/fixtures/cldr-plural-contract.json";

const counts: number[] = contract.counts;
const categories: Record<string, string[]> = contract.categories;

describe("the plural contract matches CLDR", () => {
  it("names at least the locales it was built for", () => {
    // An empty fixture would pass every case below.
    expect(Object.keys(categories).length).toBeGreaterThan(20);
    expect(counts).toContain(0);
  });

  for (const [locale, expected] of Object.entries(categories)) {
    it(`${locale} agrees with Intl.PluralRules at every count`, () => {
      const rules = new Intl.PluralRules(locale);
      const actual = counts.map((n) => rules.select(n));
      expect(actual).toEqual(expected);
    });
  }
});
