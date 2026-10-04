/**
 * The loader's glob names namespaces explicitly; one left out resolves as
 * missing in every non-English locale, with no error. Pin the four the SPA
 * requests (`LAZY_NAMESPACES` in ./index).
 */

import { describe, expect, it } from "vitest";
import { loadLocaleResources } from "./localeLoader";

describe("loadLocaleResources", () => {
  it("loads every namespace the SPA requests", async () => {
    const got = await loadLocaleResources("fr", ["common", "settings", "enums", "desktop"]);
    expect(Object.keys(got).sort()).toEqual(["common", "desktop", "enums", "settings"]);
    expect(Object.keys(got.common).length).toBeGreaterThan(0);
  });

  it("returns nothing for a file that does not exist, rather than throwing", async () => {
    // zh-Hant-HK is a thin override fork with no enums.json.
    const got = await loadLocaleResources("zh-Hant-HK", ["enums"]);
    expect(got).toEqual({});
  });
});
