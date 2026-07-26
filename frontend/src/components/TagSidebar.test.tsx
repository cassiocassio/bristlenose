/**
 * TagSidebar — buildVisibleFrameworks (item 1 + 6 of the codebook state model).
 *
 * Covers the two researcher-noticeable invariants:
 *   • a DISABLED codebook disappears from the sidebar ("off means off", §5)
 *   • the floor (hand-made project codebook) is titled by project and can NEVER be
 *     disabled away — it has no framework id, so it survives any disabled set (§2)
 */

import { describe, expect, it } from "vitest";

import { buildVisibleFrameworks } from "./TagSidebar";
import type {
  CodebookGroupResponse,
  CodebookResponse,
  CodebookTagResponse,
} from "../utils/types";

const t = (k: string) => k;

function tag(name: string): CodebookTagResponse {
  return { id: 1, name, count: 3, colour_index: 0 };
}

function group(
  name: string,
  framework_id: string | null,
): CodebookGroupResponse {
  return {
    id: 1,
    name,
    subtitle: "",
    colour_set: "",
    order: 0,
    tags: [tag(`${name}-tag`)],
    total_quotes: 3,
    is_default: false,
    framework_id,
  };
}

/** floor group (framework_id=null) + two framework codebooks. */
function makeCodebook(): CodebookResponse {
  return {
    groups: [
      group("Behaviour", null), // floor
      group("Laws of UX", "garrett"),
      group("Signals", "uxr"),
    ],
    ungrouped: [],
    all_tag_names: [],
  };
}

const FLOOR = "project-ikea2 tags";

describe("buildVisibleFrameworks", () => {
  it("titles the floor by project and keeps every codebook when none disabled", () => {
    const fws = buildVisibleFrameworks(makeCodebook(), t, FLOOR, new Set());
    const floor = fws.find((f) => f.id === "_user");
    expect(floor?.title).toBe(FLOOR);
    expect(fws.map((f) => f.id).sort()).toEqual(["_user", "garrett", "uxr"]);
  });

  it("drops a disabled codebook entirely (not muted-but-listed)", () => {
    const fws = buildVisibleFrameworks(
      makeCodebook(),
      t,
      FLOOR,
      new Set(["garrett"]),
    );
    expect(fws.map((f) => f.id)).not.toContain("garrett");
    expect(fws.map((f) => f.id).sort()).toEqual(["_user", "uxr"]);
  });

  it("never disables the floor away, even if its group ids collide", () => {
    // The floor's synthetic id is "_user"/"_ungrouped" — never a real framework id,
    // so it survives any disabled set. Guards the researcher never losing their own
    // deliberate tags.
    const fws = buildVisibleFrameworks(
      makeCodebook(),
      t,
      FLOOR,
      new Set(["garrett", "uxr", "_user"]), // even if "_user" leaked in…
    );
    // …the framework codebooks go, the floor stays.
    const floor = fws.find((f) => f.id === "_user");
    expect(floor?.title).toBe(FLOOR);
  });

  it("names the floor from ungrouped tags when there is no null-framework group", () => {
    const cb: CodebookResponse = {
      groups: [group("Laws of UX", "garrett")],
      ungrouped: [tag("loose-tag")],
      all_tag_names: [],
    };
    const fws = buildVisibleFrameworks(cb, t, FLOOR, new Set());
    const floor = fws.find((f) => f.id === "_ungrouped");
    expect(floor?.title).toBe(FLOOR);
  });
});
