/**
 * The review's re-cut rule against the contract the server's `recut_target` also
 * reads (tests/fixtures/recut-contract.json, tests/test_recut_contract.py), through the
 * dialog's own readings of the stored lines and the sliders.
 */
import { describe, expect, it } from "vitest";
import contractJson from "../../../tests/fixtures/recut-contract.json";
import { outcomeZone, snapLines, storedLinesOf } from "./recut";
import type { ProposedTagResponse } from "./types";

interface Case {
  name: string;
  status: ProposedTagResponse["status"];
  decided_by: ProposedTagResponse["decided_by"];
  confidence: number;
  stored: [number | null, number | null] | null;
  lines: [number, number];
  expected: string;
}

const contract = contractJson as unknown as { defaults: { lower: number; upper: number }; cases: Case[] };

describe("the re-cut contract", () => {
  it.each(contract.cases.map((c) => [c.name, c] as const))("%s", (_name, c) => {
    const stored = storedLinesOf(
      { applied_lower_threshold: c.stored?.[0] ?? null, applied_upper_threshold: c.stored?.[1] ?? null },
      contract.defaults,
    );
    const p = { status: c.status, decided_by: c.decided_by, confidence: c.confidence } as ProposedTagResponse;
    expect(outcomeZone(p, stored, snapLines(c.lines[0], c.lines[1]))).toBe(c.expected);
  });
});
