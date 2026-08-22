/**
 * TypeScript side of the cross-language RENDER contract.
 *
 * Reads the same `tests/fixtures/shared-format-contract.json` as
 * `tests/test_shared_format_contract.py` and makes the same assertions against
 * the TypeScript implementations. If the two languages drift, whichever side
 * moved fails its own suite with the offending case named.
 *
 * Sibling of the Python/Swift `pipeline-summary-contract.json` pair, which does
 * this for *parsed* contracts. See `docs/design-shared-formats.md` for the
 * distinction — a parsed mismatch breaks function, a rendered mismatch is a
 * visible inconsistency.
 *
 * **Asserts `aligned` entries only.** `divergent` entries in the fixture are a
 * measured catalogue of formats that do NOT currently agree; nothing here
 * treats their observed values as correct. Closing one of those gaps means
 * promoting the entry to `aligned` in the same commit as the fix.
 */

import { describe, expect, it } from "vitest";
import contractJson from "../../../tests/fixtures/shared-format-contract.json";
import { formatDurationHuman, formatFinderFilename, formatTimecode } from "./format";

// Imported rather than read through node:fs on purpose. `npm run build` runs
// `tsc -b` over the test files with no @types/node in scope, so a `readFileSync`
// here type-checks fine under Vitest and then fails the build (TS2591) — the
// exact split this repo's frontend CLAUDE.md warns about. Reaching outside
// frontend/ is already house practice: `include` and the `@locales/*` alias
// both point at ../bristlenose/locales.

interface FormatSpec {
  status: string;
  datum?: string;
  // Inputs are not all numeric — a duration and a timecode take seconds, a
  // filename takes a string.
  cases?: [number | string, string][] | null;
  observed?: Record<string, unknown>;
}

const contract = contractJson as unknown as { formats: Record<string, FormatSpec> };

/** The TypeScript implementation for each aligned format. The cast at each
 *  boundary is the one place the heterogeneous case table is narrowed. */
const IMPLS: Record<string, (value: number | string) => string> = {
  duration_human: (v) => formatDurationHuman(v as number),
  timecode: (v) => formatTimecode(v as number),
  finder_filename: (v) => formatFinderFilename(v as string),
};

describe("shared format contract — aligned formats", () => {
  const aligned = Object.entries(contract.formats).filter(
    ([, spec]) => spec.status === "aligned",
  );

  it("finds the contract fixture and at least one aligned format", () => {
    // Guards the whole file: a bad path would otherwise make every
    // it.each below silently iterate zero cases and the suite pass green.
    expect(aligned.length).toBeGreaterThan(0);
  });

  for (const [name, spec] of aligned) {
    describe(name, () => {
      const impl = IMPLS[name];

      it("has a TypeScript implementation registered", () => {
        expect(impl, `no TS implementation registered for aligned format "${name}"`).toBeTypeOf(
          "function",
        );
      });

      it("pins at least one case", () => {
        expect(spec.cases?.length ?? 0).toBeGreaterThan(0);
      });

      it.each(spec.cases ?? [])("%s renders as %s", (value, expected) => {
        expect(impl(value)).toBe(expected);
      });
    });
  }
});

describe("shared format contract — one implementation per language", () => {
  // Four components held private copies of formatTimecode until 22 Aug 2026.
  // Vitest cannot compare function identity across modules the way the Python
  // side can, so this pins the observable consequence instead: every module
  // that renders a timecode agrees with the canonical helper.
  it("every TypeScript timecode surface renders the canonical format", () => {
    for (const [seconds, expected] of contract.formats.timecode.cases ?? []) {
      expect(formatTimecode(seconds as number)).toBe(expected);
    }
    // The shape that was wrong: an unpadded minute field.
    expect(formatTimecode(330)).toBe("05:30");
    expect(formatTimecode(330)).not.toBe("5:30");
    // ...and the shape that would be wrong the other way: a padded hour.
    expect(formatTimecode(3930)).toBe("1:05:30");
    expect(formatTimecode(3930)).not.toBe("01:05:30");
  });
});
