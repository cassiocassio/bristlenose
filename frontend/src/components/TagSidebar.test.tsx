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

  // The bars line up only if every row's number takes one width: the widest
  // count's, set once on the sidebar and read by every row (23 Nov 2026).
  it("sizes one count column for every row from the widest count it shows", async () => {
    vi.mocked(getCodebook).mockResolvedValue(
      withDefaultGroup([
        { ...tag("Trust"), tentative_count: 128 },
        { ...tag("Pricing"), tentative_count: 4 },
      ]),
    );
    const { container } = render(<TagSidebar />);
    await waitFor(() => expect(screen.getByText("Trust")).toBeTruthy());
    const root = container.firstElementChild as HTMLElement;
    expect(root.style.getPropertyValue("--bn-count-digits")).toBe("3");
    // Every row keeps the bar's track, even one with nothing to draw.
    const rows = container.querySelectorAll(".tag-row");
    expect(rows.length).toBeGreaterThan(0);
    rows.forEach((row) => expect(row.querySelector(".tag-bar-area > .tag-bar-track")).toBeTruthy());
  });
});

// ── The summary line, pinned before the AutoCode overview changes it ──────
// Phase 6 of docs/design-autocode-landing-plan.md rewrites this line (D17, D22).
// The audit's rule: pin what ships first, so every change to it is a named one
// and the parts no decision names (search, Used, solo, the search box) stay.

function quoteTagged(domId: string, name: string) {
  return {
    dom_id: domId,
    text: "hello",
    participant_id: "p1",
    speaker_name: "p1",
    start_timecode: 10,
    session_id: "s1",
    deleted_badges: [],
    proposed_tags: [],
    tags: [{ name, codebook_group: "Uncategorised", colour_set: "", colour_index: 0, source: "human" }],
  };
}

describe("TagSidebar summary line (as shipped)", () => {
  const NINE = ["Trust", "Pricing", "Delivery", "Returns", "Stock", "Support", "Range", "Quality", "Price"];

  beforeEach(() => {
    vi.clearAllMocks();
    resetStore();
    resetSidebarStore();
    vi.mocked(getHiddenTagGroups).mockResolvedValue([]);
    vi.mocked(getFrameworkStates).mockResolvedValue({});
    vi.mocked(apiGet).mockResolvedValue({ project_name: "ikea3" });
  });

  const line = () => document.querySelector(".tag-sidebar-subtitle")?.textContent ?? "";

  it("under search, counts the tags that match and the codebooks they are in", async () => {
    vi.mocked(getCodebook).mockResolvedValue(withDefaultGroup(NINE.map(tag)));
    render(<TagSidebar />);
    const box = await waitFor(() => {
      const el = document.querySelector<HTMLInputElement>(".tag-search-input");
      expect(el).toBeTruthy();
      return el!;
    });
    fireEvent.change(box, { target: { value: "pric" } });
    expect(line()).toBe("2 tags across 1 frameworks");
    fireEvent.change(box, { target: { value: "sentiment" } });
    expect(line()).toBe("1 tags across 1 frameworks");
  });

  it("under Used, counts the tags on quotes", async () => {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    initFromQuotes([quoteTagged("q-p1-10", "Trust")] as any);
    vi.mocked(getCodebook).mockResolvedValue(withDefaultGroup(["Trust", "Pricing"].map(tag)));
    render(<TagSidebar />);
    await waitFor(() => expect(screen.getByText("Pricing")).toBeTruthy());
    fireEvent.change(screen.getByTestId("bn-tag-show"), { target: { value: "used" } });
    expect(line()).toBe("1 tags across 1 frameworks");
  });

  it("is dimmed, not hidden, in solo mode", async () => {
    vi.mocked(getCodebook).mockResolvedValue(withDefaultGroup(["Trust", "Pricing"].map(tag)));
    requestSoloTag("Trust");
    const { container } = render(<TagSidebar />);
    await waitFor(() => expect(container.querySelector(".tag-solo-active")).toBeTruthy());
    expect(container.querySelector(".tag-solo-active .tag-sidebar-subtitle")).toBeTruthy();
  });

  it("shows the search box only above 8 tags, counted over every tag", async () => {
    // Seven of the floor's own plus Sentiment's one: 8, no box.
    vi.mocked(getCodebook).mockResolvedValue(withDefaultGroup(NINE.slice(0, 7).map(tag)));
    const first = render(<TagSidebar />);
    await waitFor(() => expect(screen.getByText("Trust")).toBeTruthy());
    expect(document.querySelector(".tag-search-input")).toBeNull();
    first.unmount();
    // One more: 9, the box.
    vi.mocked(getCodebook).mockResolvedValue(withDefaultGroup(NINE.slice(0, 8).map(tag)));
    render(<TagSidebar />);
    await waitFor(() => expect(document.querySelector(".tag-search-input")).toBeTruthy());
  });

  // Changed by D22 (Phase 6): before any run the line counts every tag but Sentiment's. It
  // read "3 tags across 2 frameworks" here until then.
  it("with no filter and no run, counts every tag but Sentiment's (D22)", async () => {
    vi.mocked(getCodebook).mockResolvedValue(withDefaultGroup(["Trust", "Pricing"].map(tag)));
    render(<TagSidebar />);
    await waitFor(() => expect(screen.getByText("Pricing")).toBeTruthy());
    expect(line()).toBe("2 tags");
  });
});

// ── D15: sentiment in the Sessions grid's order ───────────────────────────
// The codebook arrives in sentiment.yaml's order, each tag carrying the colour slot of
// its place there. The rows are listed in SENTIMENT_ORDER; each colour stays its own.

const YAML_ORDER = [
  "frustration", "confusion", "doubt", "surprise", "satisfaction", "delight", "confidence",
];

describe("TagSidebar sentiment order (D15)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    resetStore();
    resetSidebarStore();
    vi.mocked(getHiddenTagGroups).mockResolvedValue([]);
    vi.mocked(getFrameworkStates).mockResolvedValue({});
    vi.mocked(apiGet).mockResolvedValue({ project_name: "ikea3" });
    const sentiment: CodebookGroupResponse = {
      id: 1, name: "Sentiment", subtitle: "", colour_set: "sentiment", order: 0,
      tags: YAML_ORDER.map((name, i) => ({ id: 100 + i, name, count: 1, colour_index: i })),
      total_quotes: 7, is_default: false, framework_id: "sentiment",
    };
    // A researcher's own tags that happen to share sentiment names: their order is theirs.
    const own: CodebookGroupResponse = {
      id: 2, name: "Uncategorised", subtitle: "", colour_set: "", order: 9999,
      tags: ["satisfaction", "frustration", "Pricing"].map((name, i) => ({
        id: 200 + i, name, count: 0, colour_index: i,
      })),
      total_quotes: 0, is_default: true, framework_id: null,
    };
    vi.mocked(getCodebook).mockResolvedValue({ groups: [sentiment, own], ungrouped: [], all_tag_names: [] });
    initFromQuotes([
      {
        dom_id: "q-p1-10", text: "hello", participant_id: "p1", speaker_name: "p1",
        start_timecode: 10, session_id: "s1", deleted_badges: [], proposed_tags: [],
        tags: YAML_ORDER.map((name, i) => ({
          name, codebook_group: "Sentiment", colour_set: "sentiment", colour_index: i, source: "pipeline",
        })),
      },
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
    ] as any);
  });

  const rowsOf = (card: Element) =>
    [...card.querySelectorAll(".tag-row")].map((row) => ({
      name: row.querySelector("input")!.getAttribute("aria-label"),
      badge: row.querySelector(".badge")!.getAttribute("style") ?? "",
      bar: row.querySelector(".tag-bar-track")!.innerHTML,
    }));

  async function cards() {
    await waitFor(() => expect(screen.getByLabelText("Pricing")).toBeTruthy());
    return [...document.querySelectorAll(".tag-filter-group")];
  }

  it("lists the sentiment rows in the Sessions grid's order", async () => {
    render(<TagSidebar />);
    const [sentiment] = await cards();
    expect(rowsOf(sentiment).map((r) => r.name)).toEqual([
      "frustration", "confusion", "doubt", "surprise", "confidence", "delight", "satisfaction",
    ]);
  });

  it("keeps every other group's order, sentiment names or not", async () => {
    render(<TagSidebar />);
    const [, own] = await cards();
    expect(rowsOf(own).map((r) => r.name)).toEqual(["satisfaction", "frustration", "Pricing"]);
  });

  it("draws each sentiment in the colour it had in the yaml's order", async () => {
    // Before D15 the rows came in YAML_ORDER, slot i for row i; the slot travels with the
    // tag, so after the reorder each name keeps the same badge and bar.
    render(<TagSidebar />);
    const [sentiment] = await cards();
    const byName = new Map(rowsOf(sentiment).map((r) => [r.name, r]));
    YAML_ORDER.forEach((name, i) => {
      expect(byName.get(name)!.badge).toContain(`--bn-sentiment-${i + 1}-bg`);
      expect(byName.get(name)!.bar).toContain(`--bn-sentiment-${name}`);
    });
  });
});
