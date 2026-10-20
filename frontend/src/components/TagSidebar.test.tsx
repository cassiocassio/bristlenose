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

import { act, fireEvent, render, renderHook, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { TagSidebar, buildVisibleFrameworks, mergePendingTags } from "./TagSidebar";
import type {
  CodebookGroupResponse,
  CodebookResponse,
  CodebookTagResponse,
} from "../utils/types";
import {
  getQuotesSnapshot,
  initFromQuotes,
  resetStore,
  setTagFilter,
} from "../contexts/QuotesContext";
import {
  anySidebarOpen,
  enterSoloMode,
  requestSoloTag,
  resetSidebarStore,
  toggleTagGroupHidden,
  useSidebarStore,
} from "../contexts/SidebarStore";

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
    patchHiddenTagGroups: vi.fn(() => Promise.resolve()),
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

  it("its search box folds accents and matches word starts, as toolbar search does", async () => {
    const names = ["Zoë's notes", "Søren", "Hidden costs", "Trust", "Pricing", "Delivery", "Returns", "Stock", "Support"];
    vi.mocked(getCodebook).mockResolvedValue(withDefaultGroup(names.map(tag)));
    render(<TagSidebar />);
    const box = await waitFor(() => {
      const el = document.querySelector<HTMLInputElement>(".tag-search-input");
      expect(el).toBeTruthy();
      return el!;
    });

    fireEvent.change(box, { target: { value: "zoe" } });
    expect(screen.queryByText("Zoë's notes")).toBeTruthy();
    expect(screen.queryByText("Trust")).toBeNull();

    fireEvent.change(box, { target: { value: "soren" } });
    expect(screen.queryByText("Søren")).toBeTruthy();

    fireEvent.change(box, { target: { value: "cost" } });
    expect(screen.queryByText("Hidden costs")).toBeTruthy();
    // A word matches from its start: "ost" is inside "costs", not a word.
    fireEvent.change(box, { target: { value: "ost" } });
    expect(screen.queryByText("Hidden costs")).toBeNull();
  });

  // The codebook lens's histogram asks for a solo from outside the Quotes lens.
  // It must land exactly where a click on this sidebar's own bar would.
  it("acts on a solo requested from another lens as a click on its own bar would", async () => {
    vi.mocked(getCodebook).mockResolvedValue(withDefaultGroup(["Trust", "Pricing"].map(tag)));
    requestSoloTag("Trust");
    expect(anySidebarOpen()).toBe(true);

    const { container } = render(<TagSidebar />);

    await waitFor(() => expect(container.querySelector(".tag-solo-active")).toBeTruthy());
    const f = getQuotesSnapshot().tagFilter;
    expect(f.unchecked).toContain("Pricing");
    expect(f.unchecked).toContain("Sentiment-tag");
    expect(f.unchecked).not.toContain("Trust");
    expect(f.noTagsUnchecked).toBe(true);
  });

  it("keeps a solo on when it is requested again, rather than toggling it off", async () => {
    const names = ["Trust", "Pricing"];
    vi.mocked(getCodebook).mockResolvedValue(withDefaultGroup(names.map(tag)));
    enterSoloMode("Trust", [...names, "Sentiment-tag"], getQuotesSnapshot().tagFilter, setTagFilter);
    const soloed = getQuotesSnapshot().tagFilter;
    requestSoloTag("Trust");

    const { container } = render(<TagSidebar />);

    // The request is acted on once the codebook is in; a toggle would have
    // restored the empty pre-solo filter by then.
    await waitFor(() => expect(screen.getByText("Pricing")).toBeTruthy());
    expect(getQuotesSnapshot().tagFilter).toBe(soloed);
    expect(container.querySelector(".tag-solo-active")).toBeTruthy();
  });

  // R93: every mount re-read the hidden groups and replaced the set wholesale,
  // so an eye clicked while that read was in flight — or just before the
  // sidebar remounted, its PUT not yet landed — snapped back.
  it("keeps an eye toggled while the hidden-groups read is in flight", async () => {
    let answer!: (groups: string[]) => void;
    vi.mocked(getHiddenTagGroups).mockReturnValueOnce(new Promise((res) => { answer = res; }));
    const store = renderHook(() => useSidebarStore());
    render(<TagSidebar />);
    await waitFor(() => expect(getHiddenTagGroups).toHaveBeenCalled());
    act(() => toggleTagGroupHidden("Behaviour"));
    await act(async () => {
      answer([]); // the server's set from before the click
      await Promise.resolve();
    });
    expect(store.result.current.hiddenTagGroups.has("Behaviour")).toBe(true);
  });

  it("keeps an eye toggled before the sidebar remounts", async () => {
    const store = renderHook(() => useSidebarStore());
    const first = render(<TagSidebar />);
    await waitFor(() => expect(getHiddenTagGroups).toHaveBeenCalledTimes(1));
    await act(async () => { await Promise.resolve(); });
    first.unmount();
    act(() => toggleTagGroupHidden("Behaviour"));
    render(<TagSidebar />); // the PUT has not landed: a re-read would say []
    await act(async () => { await Promise.resolve(); });
    expect(store.result.current.hiddenTagGroups.has("Behaviour")).toBe(true);
  });
});
