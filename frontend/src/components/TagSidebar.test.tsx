/**
 * TagSidebar — buildVisibleFrameworks (item 1 + 6 of the codebook state model)
 * and mergePendingTags (a just-typed tag is reachable before any refetch).
 *
 * Covers the three researcher-noticeable invariants:
 *   • a DISABLED codebook disappears from the sidebar ("off means off", §5)
 *   • the floor (hand-made project codebook) is titled by project and can NEVER be
 *     disabled away — it has no framework id, so it survives any disabled set (§2)
 *   • a tag that exists on a quote is ALWAYS reachable in the tree, even when the
 *     codebook snapshot predates it
 */

import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { TagSidebar, buildVisibleFrameworks, mergePendingTags } from "./TagSidebar";
import type {
  CodebookGroupResponse,
  CodebookResponse,
  CodebookTagResponse,
} from "../utils/types";
import { initFromQuotes, resetStore } from "../contexts/QuotesContext";
import { resetSidebarStore } from "../contexts/SidebarStore";

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

// ── mergePendingTags ──────────────────────────────────────────────────────

/** Codebook shaped like the server's: one framework + the always-emitted
 *  `Uncategorised` default group, here still empty (the pre-tag snapshot). */
function withDefaultGroup(defaultTags: CodebookTagResponse[]): CodebookResponse {
  return {
    groups: [
      group("Sentiment", "sentiment"),
      {
        id: 2,
        name: "Uncategorised",
        subtitle: "Tags not yet assigned to any group",
        colour_set: "",
        order: 9999,
        tags: defaultTags,
        total_quotes: 0,
        is_default: true,
        framework_id: null,
      },
    ],
    ungrouped: [],
    all_tag_names: [],
  };
}

describe("mergePendingTags", () => {
  it("lands a just-typed tag in the floor's default group", () => {
    const merged = mergePendingTags(withDefaultGroup([]), ["fishfish"]);
    const floor = merged.groups.find((g) => g.is_default);
    expect(floor?.tags.map((t) => t.name)).toEqual(["fishfish"]);
  });

  it("returns the codebook untouched once the refetch carries the tag", () => {
    const cb = withDefaultGroup([tag("fishfish")]);
    expect(mergePendingTags(cb, ["fishfish"])).toBe(cb);
  });

  it("matches case-insensitively, so a recased tag is not duplicated", () => {
    const cb = withDefaultGroup([tag("FishFish")]);
    expect(mergePendingTags(cb, ["fishfish"])).toBe(cb);
  });

  it("never shadows a framework tag onto the floor", () => {
    const merged = mergePendingTags(withDefaultGroup([]), ["Sentiment-tag"]);
    expect(merged.groups.find((g) => g.is_default)?.tags).toEqual([]);
  });

  it("gives synthetic tags negative ids so React keys can't collide", () => {
    const merged = mergePendingTags(withDefaultGroup([]), ["a", "b"]);
    const ids = merged.groups.find((g) => g.is_default)!.tags.map((t) => t.id);
    expect(ids.every((id) => id < 0)).toBe(true);
    expect(new Set(ids).size).toBe(ids.length);
  });

  it("falls back to `ungrouped` when the DB has no default group", () => {
    const cb: CodebookResponse = {
      groups: [group("Laws of UX", "garrett")],
      ungrouped: [],
      all_tag_names: [],
    };
    const merged = mergePendingTags(cb, ["fishfish"]);
    expect(merged.ungrouped.map((t) => t.name)).toEqual(["fishfish"]);
    // …and the floor machinery still picks it up.
    const fws = buildVisibleFrameworks(merged, t, FLOOR, new Set());
    expect(fws.find((f) => f.id === "_ungrouped")?.title).toBe(FLOOR);
  });
});

// ── Wiring ────────────────────────────────────────────────────────────────
// One render test at the seam: the pure function above can be perfect and the
// component still never call it. That is exactly what shipped.

vi.mock("../utils/api", async (importOriginal) => {
  const actual = (await importOriginal()) as Record<string, unknown>;
  return {
    ...actual,
    getCodebook: vi.fn(),
    getHiddenTagGroups: vi.fn(),
    getFrameworkStates: vi.fn(),
    apiGet: vi.fn(),
  };
});

import {
  apiGet,
  getCodebook,
  getFrameworkStates,
  getHiddenTagGroups,
} from "../utils/api";

describe("TagSidebar", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    resetStore();
    resetSidebarStore();
    // The stale snapshot: `GET /codebook` emits `Uncategorised` unconditionally,
    // so before the fix the floor card rendered *empty* — a missing tag that
    // looked like an empty group.
    vi.mocked(getCodebook).mockResolvedValue(withDefaultGroup([]));
    vi.mocked(getHiddenTagGroups).mockResolvedValue([]);
    vi.mocked(getFrameworkStates).mockResolvedValue({});
    vi.mocked(apiGet).mockResolvedValue({ project_name: "ikea3" });
  });

  it("shows a tag that is on a quote but not yet in the fetched codebook", async () => {
    initFromQuotes([
      {
        dom_id: "q-p1-10",
        text: "hello",
        participant_id: "p1",
        speaker_name: "p1",
        start_timecode: 10,
        session_id: "s1",
        deleted_badges: [],
        proposed_tags: [],
        tags: [
          {
            name: "fishfish",
            codebook_group: "Uncategorised",
            colour_set: "",
            colour_index: 0,
            source: "human",
          },
        ],
      },
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
    ] as any);

    render(<TagSidebar />);

    await waitFor(() => expect(screen.getByText("Sentiment-tag")).toBeTruthy());
    expect(screen.getByText("fishfish")).toBeTruthy();
  });
});
