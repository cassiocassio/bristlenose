/**
 * Guard: the single-file export build must not contain the dev specimen pages.
 *
 * PickerSpecimen carries a fixture (people's names), as the style guide's
 * sections do, and the export is the file
 * a researcher hands to a client. vite.export.config.ts aliases the two
 * specimen tab modules to a stub; this builds the real export config in memory
 * and fails if any specimen module is reachable from the export entry, or if a
 * fixture name leaks.
 */
import { build, type InlineConfig } from "vite";
import type { RolldownOutput } from "rolldown";
import { describe, expect, it } from "vitest";

async function buildExport(): Promise<RolldownOutput> {
  const config: InlineConfig = {
    configFile: "vite.export.config.ts", // relative to the vitest root (frontend/),
    logLevel: "silent",
    build: { write: false },
  };
  const result = await build(config);
  return (Array.isArray(result) ? result[0] : result) as RolldownOutput;
}

describe("export bundle", () => {
  it("contains no specimen module and no fixture names", { timeout: 120_000 }, async () => {
    const out = await buildExport();
    const chunks = out.output.filter((o) => o.type === "chunk");
    expect(chunks.length).toBeGreaterThan(0);

    const ids = chunks.flatMap((c) => ("moduleIds" in c ? c.moduleIds : []));
    // Prove the check can see modules at all (a vacuous pass is no guard).
    expect(ids.some((id) => id.endsWith("router.tsx"))).toBe(true);
    expect(ids.filter((id) => /Specimen|StyleGuide|styleGuide|KeylineLab|keylineLab/.test(id))).toEqual([]);

    const code = chunks.map((c) => ("code" in c ? c.code : "")).join("\n");
    for (const needle of ["Marcus Bell", "Kerri Ng", "Amara Nwosu"]) {
      expect(code).not.toContain(needle);
    }
  });
});
