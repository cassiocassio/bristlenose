/**
 * TypeScript side of the cross-language URL-safety contract.
 *
 * Reads the same `tests/fixtures/safe-url-contract.json` as
 * `tests/test_safe_url_contract.py`. Imported rather than read through node:fs
 * — `npm run build` runs `tsc -b` over the test files with no @types/node in
 * scope, so a `readFileSync` here type-checks under Vitest and then fails the
 * build. Reaching outside frontend/ is already house practice; see
 * sharedFormatContract.test.ts, which says the same thing.
 */

import { describe, expect, it } from "vitest";
import contract from "../../../tests/fixtures/safe-url-contract.json";
import { ALLOWED_SCHEMES, isSafeUrl, safeUrlOrNull } from "./safeUrl";

interface Case {
  url: string;
  safe: boolean;
  why: string;
}

const cases = contract.cases as Case[];

describe("safe-url contract", () => {
  it("has cases to assert", () => {
    expect(cases.length).toBeGreaterThan(10);
  });

  for (const c of cases) {
    it(`${c.safe ? "allows" : "refuses"}: ${c.why}`, () => {
      expect(isSafeUrl(c.url)).toBe(c.safe);
    });
  }

  it("returns null rather than a string for anything unsafe", () => {
    // A caller that forgets to check the bool must still not get a URL.
    for (const c of cases.filter((x) => !x.safe)) {
      expect(safeUrlOrNull(c.url)).toBeNull();
    }
  });

  it("keeps the allowlist to three schemes", () => {
    // If this grows, the Python and Swift sides grow with it.
    expect([...ALLOWED_SCHEMES].sort()).toEqual([
      "http:",
      "https:",
      "mailto:",
    ]);
  });

  it("refuses non-strings", () => {
    for (const v of [null, undefined, 0, [], {}, true]) {
      expect(isSafeUrl(v as unknown as string)).toBe(false);
    }
  });
});
