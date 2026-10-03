import { renderHook, act } from "@testing-library/react";
import type {
  QuoteResponse,
  SectionResponse,
  TagResponse,
  ThemeResponse,
} from "../utils/types";
import {
  initFromQuotes,
  initHeadingEdits,
  resetStore,
  toggleStar,
  hideQuotes,
  unhideQuotes,
  HIDE_DURATION,
  commitEdit,
  commitHeadingEdit,
  addTag,
  removeTag,
  deleteBadge,
  restoreBadges,
  acceptProposedTag,
  denyProposedTag,
  setSearchQuery,
  setViewMode,
  setTagFilter,
  useQuotesStore,
  starActionIsUnstar,
  addSearchToken,
  removeSearchToken,
  setSearchTokenMode,
  clearSearchTokens,
  filterStateOf,
  getQuotesSnapshot,
  getVisibleQuotes,
  setSearchPeople,
  useQuoteCounts,
} from "./QuotesContext";
import { personToken, tagToken } from "../utils/searchTokens";
import { EMPTY_TAG_FILTER } from "../utils/filter";
import { _resetExportCache } from "../utils/exportData";

// ── Mocks ────────────────────────────────────────────────────────────────

vi.mock("../utils/api", () => ({
  putHidden: vi.fn(),
  putStarred: vi.fn(),
  putEdits: vi.fn(),
  putTags: vi.fn(),
  putDeletedBadges: vi.fn(),
  acceptProposal: vi.fn().mockResolvedValue(undefined),
  denyProposal: vi.fn().mockResolvedValue(undefined),
}));

import {
  putHidden,
  putStarred,
  putEdits,
  putTags,
  putDeletedBadges,
  acceptProposal,
  denyProposal,
} from "../utils/api";

const mockPutHidden = vi.mocked(putHidden);
const mockPutStarred = vi.mocked(putStarred);
const mockPutEdits = vi.mocked(putEdits);
const mockPutTags = vi.mocked(putTags);
const mockPutDeletedBadges = vi.mocked(putDeletedBadges);
const mockAcceptProposal = vi.mocked(acceptProposal);
const mockDenyProposal = vi.mocked(denyProposal);

// ── Helpers ──────────────────────────────────────────────────────────────

function makeQuote(overrides: Partial<QuoteResponse> = {}): QuoteResponse {
  return {
    dom_id: "q-P1-120",
    text: "I found the login confusing",
    verbatim_excerpt: "the login confusing",
    participant_id: "P1",
    session_id: "s1",
    speaker_name: "Participant 1",
    start_timecode: 120,
    end_timecode: 125,
    sentiment: "negative",
    intensity: 3,
    researcher_context: null,
    quote_type: "section",
    topic_label: "Login",
    is_starred: false,
    is_hidden: false,
    edited_text: null,
    tags: [],
    deleted_badges: [],
    proposed_tags: [],
    segment_index: 0,
    ...overrides,
  };
}

const TAG_FRUSTRATION: TagResponse = {
  name: "Frustration",
  codebook_group: "Emotions",
  colour_set: "emo",
  colour_index: 0,
};

beforeEach(() => {
  resetStore();
  vi.clearAllMocks();
});

// ── Tests ────────────────────────────────────────────────────────────────

describe("starActionIsUnstar", () => {
  it("is false when nothing is selected or focused", () => {
    expect(starActionIsUnstar(new Set(), null, {})).toBe(false);
  });

  it("mirrors the focused quote's state when nothing is selected", () => {
    expect(starActionIsUnstar(new Set(), "q-1", { "q-1": true })).toBe(true);
    expect(starActionIsUnstar(new Set(), "q-1", {})).toBe(false);
  });

  it("selection wins over focus", () => {
    // Focused quote is starred, but selected quote is not → would star.
    const starred = { "q-focus": true };
    expect(starActionIsUnstar(new Set(["q-sel"]), "q-focus", starred)).toBe(false);
  });

  it("is true only when every selected quote is starred (unstar-all)", () => {
    const all = { "q-1": true, "q-2": true };
    expect(starActionIsUnstar(new Set(["q-1", "q-2"]), null, all)).toBe(true);
    // One unstarred in the selection → star-all direction.
    const mixed = { "q-1": true };
    expect(starActionIsUnstar(new Set(["q-1", "q-2"]), null, mixed)).toBe(false);
  });
});

describe("QuotesStore", () => {
  describe("initFromQuotes", () => {
    it("populates state from quote responses", () => {
      const q = makeQuote({
        is_starred: true,
        is_hidden: true,
        edited_text: "edited",
        tags: [TAG_FRUSTRATION],
        deleted_badges: ["negative"],
        proposed_tags: [
          {
            id: 1,
            tag_name: "Trust",
            group_name: "UX",
            colour_set: "ux",
            colour_index: 2,
            confidence: 0.8,
            rationale: "reason",
          },
        ],
      });
      initFromQuotes([q]);
      const { result } = renderHook(() => useQuotesStore());
      expect(result.current.starred).toEqual({ "q-P1-120": true });
      expect(result.current.hidden).toEqual({ "q-P1-120": true });
      expect(result.current.edits).toEqual({ "q-P1-120": "edited" });
      expect(result.current.tags["q-P1-120"]).toHaveLength(1);
      expect(result.current.tags["q-P1-120"][0].name).toBe("Frustration");
      expect(result.current.deletedBadges).toEqual({ "q-P1-120": ["negative"] });
      expect(result.current.proposedTags["q-P1-120"]).toHaveLength(1);
    });

    it("merges non-overlapping quotes from two calls (default merge mode)", () => {
      const q1 = makeQuote({ dom_id: "q-P1-100", is_starred: true });
      const q2 = makeQuote({ dom_id: "q-P2-200", is_hidden: true });
      initFromQuotes([q1]);
      initFromQuotes([q2]);
      const { result } = renderHook(() => useQuotesStore());
      expect(result.current.starred).toEqual({ "q-P1-100": true });
      expect(result.current.hidden).toEqual({ "q-P2-200": true });
    });

    it("replace mode clears existing state before populating", () => {
      const q1 = makeQuote({ dom_id: "q-P1-100", is_starred: true });
      const q2 = makeQuote({ dom_id: "q-P2-200", is_hidden: true });
      initFromQuotes([q1]);
      initFromQuotes([q2], true);
      const { result } = renderHook(() => useQuotesStore());
      // q1's starred state was cleared by replace
      expect(result.current.starred).toEqual({});
      expect(result.current.hidden).toEqual({ "q-P2-200": true });
    });

    it("replace keeps what the researcher is looking at: search, tokens, starred-only, tag filter", () => {
      // A refetch is never the researcher's doing (a run or an AutoCode
      // catch-up finishing), so it must not clear their search.
      const q1 = makeQuote({ dom_id: "q-P1-100" });
      initFromQuotes([q1]);
      const filter = { ...EMPTY_TAG_FILTER, unchecked: ["pricing"] };
      act(() => {
        setSearchQuery("delivery");
        addSearchToken(personToken("p1", { full_name: "Ann Lee", short_name: "Ann" }));
        setViewMode("starred");
        setTagFilter(filter);
      });
      initFromQuotes([makeQuote({ dom_id: "q-P2-200" })], true);
      const s = getQuotesSnapshot();
      expect(s.searchQuery).toBe("delivery");
      expect(s.searchTokens.map((t) => t.kind === "person" && t.code)).toEqual(["p1"]);
      expect(s.viewMode).toBe("starred");
      expect(s.tagFilter).toEqual(filter);
      expect(s.quotes.map((q) => q.dom_id)).toEqual(["q-P2-200"]); // the data was replaced
    });

    it("a speaker code typed with a space becomes a said-by token, named from the quotes", () => {
      initFromQuotes([
        makeQuote({ dom_id: "a", participant_id: "p3", speaker_name: "Priya" }),
        makeQuote({ dom_id: "b", participant_id: "m1", speaker_name: "m1" }),
      ]);
      act(() => setSearchQuery("p3"));
      expect(getQuotesSnapshot().searchTokens).toEqual([]); // no space yet
      act(() => setSearchQuery("P3 late"));
      const s = getQuotesSnapshot();
      expect(s.searchQuery).toBe("late");
      expect(s.searchTokens).toEqual([{ kind: "person", code: "p3", names: ["Priya"], mode: "said" }]);

      act(() => setSearchQuery("m1 p3 "));
      expect(getQuotesSnapshot().searchTokens.map((t) => t.kind === "person" && t.code)).toEqual(["p3", "m1"]);
      act(() => setSearchQuery("p9 ")); // nobody with quotes is p9: it stays text
      expect(getQuotesSnapshot().searchQuery).toBe("p9 ");
    });

    it("a code whose every quote is hidden stays text", () => {
      initFromQuotes([makeQuote({ dom_id: "a", participant_id: "p5", is_hidden: true })]);
      act(() => setSearchQuery("p5 "));
      expect(getQuotesSnapshot().searchTokens).toEqual([]);
      expect(getQuotesSnapshot().searchQuery).toBe("p5 ");
    });

    it("a typed code names the person from the people list when one has been fetched, as a click does", () => {
      initFromQuotes([makeQuote({ dom_id: "a", participant_id: "p3", speaker_name: "Priya" })]);
      setSearchPeople({ p3: { full_name: "Priya Shah", short_name: "Priya" } });
      act(() => setSearchQuery("p3 "));
      expect(getQuotesSnapshot().searchTokens).toEqual([
        { kind: "person", code: "p3", names: ["Priya Shah", "Priya"], mode: "said" },
      ]);
    });

    it("skips falsy values (no spurious keys for unstarred/unhidden quotes)", () => {
      const q = makeQuote();
      initFromQuotes([q]);
      const { result } = renderHook(() => useQuotesStore());
      expect(Object.keys(result.current.starred)).toHaveLength(0);
      expect(Object.keys(result.current.hidden)).toHaveLength(0);
      expect(Object.keys(result.current.edits)).toHaveLength(0);
      expect(Object.keys(result.current.tags)).toHaveLength(0);
    });
  });

  describe("toggleStar", () => {
    it("stars a quote and calls putStarred", () => {
      initFromQuotes([makeQuote()]);
      toggleStar("q-P1-120", true);
      const { result } = renderHook(() => useQuotesStore());
      expect(result.current.starred["q-P1-120"]).toBe(true);
      expect(mockPutStarred).toHaveBeenCalledWith({ "q-P1-120": true });
    });

    it("unstars a quote", () => {
      initFromQuotes([makeQuote({ is_starred: true })]);
      toggleStar("q-P1-120", false);
      const { result } = renderHook(() => useQuotesStore());
      expect(result.current.starred["q-P1-120"]).toBeUndefined();
      expect(mockPutStarred).toHaveBeenCalledWith({});
    });
  });

  // These two contracts used to be pinned against `toggleHide`, which had no
  // production callers left once both paths moved to the bulk functions — an
  // exported helper whose only callers are tests. Re-homed rather than deleted
  // with it, and the deferral below is a contract the old shape could not
  // express, because `toggleHide` wrote synchronously.
  describe("hideQuotes / unhideQuotes", () => {
    it("writes nothing until the collapse window has passed", () => {
      vi.useFakeTimers();
      try {
        initFromQuotes([makeQuote()]);
        hideQuotes(["q-P1-120"]);
        expect(mockPutHidden).not.toHaveBeenCalled();

        vi.advanceTimersByTime(HIDE_DURATION + 50);
        const { result } = renderHook(() => useQuotesStore());
        expect(result.current.hidden["q-P1-120"]).toBe(true);
        expect(mockPutHidden).toHaveBeenCalledTimes(1);
        expect(mockPutHidden).toHaveBeenCalledWith({ "q-P1-120": true });
      } finally {
        vi.useRealTimers();
      }
    });

    it("restores immediately, in one write", () => {
      initFromQuotes([makeQuote({ is_hidden: true })]);
      unhideQuotes(["q-P1-120"]);
      const { result } = renderHook(() => useQuotesStore());
      expect(result.current.hidden["q-P1-120"]).toBeUndefined();
      expect(mockPutHidden).toHaveBeenCalledTimes(1);
      expect(mockPutHidden).toHaveBeenCalledWith({});
    });

    it("restores a whole group in one write, not one per quote", () => {
      const ids = ["q-a", "q-b", "q-c"];
      initFromQuotes(ids.map((id) => makeQuote({ dom_id: id, is_hidden: true })));
      unhideQuotes(ids);
      const { result } = renderHook(() => useQuotesStore());
      expect(result.current.hidden).toEqual({});
      expect(mockPutHidden).toHaveBeenCalledTimes(1);
    });
  });

  describe("commitEdit", () => {
    it("stores edited text and calls putEdits", () => {
      initFromQuotes([makeQuote()]);
      commitEdit("q-P1-120", "new text");
      const { result } = renderHook(() => useQuotesStore());
      expect(result.current.edits["q-P1-120"]).toBe("new text");
      expect(mockPutEdits).toHaveBeenCalledWith({ "q-P1-120": "new text" });
    });
  });

  describe("addTag / removeTag", () => {
    it("adds a tag and calls putTags with names only", () => {
      initFromQuotes([makeQuote()]);
      addTag("q-P1-120", TAG_FRUSTRATION);
      const { result } = renderHook(() => useQuotesStore());
      expect(result.current.tags["q-P1-120"]).toHaveLength(1);
      expect(result.current.tags["q-P1-120"][0].name).toBe("Frustration");
      expect(mockPutTags).toHaveBeenCalledWith({ "q-P1-120": ["Frustration"] });
    });

    it("removes a tag and calls putTags", () => {
      initFromQuotes([makeQuote({ tags: [TAG_FRUSTRATION] })]);
      removeTag("q-P1-120", "Frustration");
      const { result } = renderHook(() => useQuotesStore());
      expect(result.current.tags["q-P1-120"]).toBeUndefined();
      expect(mockPutTags).toHaveBeenCalledWith({});
    });

    it("does not add a duplicate tag (exact name match)", () => {
      initFromQuotes([makeQuote({ tags: [TAG_FRUSTRATION] })]);
      addTag("q-P1-120", { ...TAG_FRUSTRATION });
      const { result } = renderHook(() => useQuotesStore());
      expect(result.current.tags["q-P1-120"]).toHaveLength(1);
      // putTags should not be called for the duplicate.
      expect(mockPutTags).not.toHaveBeenCalled();
    });

    it("does not add a duplicate tag (case-insensitive)", () => {
      initFromQuotes([makeQuote({ tags: [TAG_FRUSTRATION] })]);
      addTag("q-P1-120", {
        name: "frustration", // lowercase vs "Frustration"
        codebook_group: "Emotions",
        colour_set: "emo",
        colour_index: 0,
      });
      const { result } = renderHook(() => useQuotesStore());
      expect(result.current.tags["q-P1-120"]).toHaveLength(1);
      expect(mockPutTags).not.toHaveBeenCalled();
    });
  });

  describe("deleteBadge / restoreBadges", () => {
    it("deletes a badge and calls putDeletedBadges", () => {
      initFromQuotes([makeQuote()]);
      deleteBadge("q-P1-120", "negative");
      const { result } = renderHook(() => useQuotesStore());
      expect(result.current.deletedBadges["q-P1-120"]).toEqual(["negative"]);
      expect(mockPutDeletedBadges).toHaveBeenCalledWith({
        "q-P1-120": ["negative"],
      });
    });

    it("restores all badges and calls putDeletedBadges", () => {
      initFromQuotes([makeQuote({ deleted_badges: ["negative"] })]);
      restoreBadges("q-P1-120");
      const { result } = renderHook(() => useQuotesStore());
      expect(result.current.deletedBadges["q-P1-120"]).toBeUndefined();
      expect(mockPutDeletedBadges).toHaveBeenCalledWith({});
    });
  });

  describe("acceptProposedTag", () => {
    it("removes proposal, adds tag, and calls acceptProposal", () => {
      const q = makeQuote({
        proposed_tags: [
          {
            id: 42,
            tag_name: "Trust",
            group_name: "UX",
            colour_set: "ux",
            colour_index: 2,
            confidence: 0.8,
            rationale: "reason",
          },
        ],
      });
      initFromQuotes([q]);
      const tag: TagResponse = {
        name: "Trust",
        codebook_group: "UX",
        colour_set: "ux",
        colour_index: 2,
      };
      acceptProposedTag("q-P1-120", 42, tag);
      const { result } = renderHook(() => useQuotesStore());
      expect(result.current.proposedTags["q-P1-120"]).toBeUndefined();
      expect(result.current.tags["q-P1-120"]).toHaveLength(1);
      expect(result.current.tags["q-P1-120"][0].name).toBe("Trust");
      expect(mockAcceptProposal).toHaveBeenCalledWith(42);
    });
  });

  describe("denyProposedTag", () => {
    it("removes proposal and calls denyProposal", () => {
      const q = makeQuote({
        proposed_tags: [
          {
            id: 42,
            tag_name: "Trust",
            group_name: "UX",
            colour_set: "ux",
            colour_index: 2,
            confidence: 0.8,
            rationale: "reason",
          },
        ],
      });
      initFromQuotes([q]);
      denyProposedTag("q-P1-120", 42);
      const { result } = renderHook(() => useQuotesStore());
      expect(result.current.proposedTags["q-P1-120"]).toBeUndefined();
      expect(mockDenyProposal).toHaveBeenCalledWith(42);
    });
  });

  describe("proposal triage in export mode", () => {
    const withProposal = () =>
      makeQuote({
        proposed_tags: [
          {
            id: 42,
            tag_name: "Trust",
            group_name: "UX",
            colour_set: "ux",
            colour_index: 2,
            confidence: 0.8,
            rationale: "reason",
          },
        ],
      });

    beforeEach(() => {
      (window as unknown as Record<string, unknown>).BRISTLENOSE_EXPORT = {
        version: 1,
        exported_at: "2026-08-15T00:00:00Z",
        health: {},
        endpoints: {},
      };
      _resetExportCache();
    });

    afterEach(() => {
      delete (window as unknown as Record<string, unknown>).BRISTLENOSE_EXPORT;
      _resetExportCache();
    });

    it("denyProposedTag is inert — the proposal stays and no call is made", () => {
      initFromQuotes([withProposal()]);
      denyProposedTag("q-P1-120", 42);
      const { result } = renderHook(() => useQuotesStore());
      // The visible half matters most: without the guard the proposal vanished
      // optimistically and came back on reload.
      expect(result.current.proposedTags["q-P1-120"]).toHaveLength(1);
      expect(mockDenyProposal).not.toHaveBeenCalled();
    });

    it("acceptProposedTag is inert — no tag is added and no call is made", () => {
      initFromQuotes([withProposal()]);
      acceptProposedTag("q-P1-120", 42, {
        name: "Trust",
        codebook_group: "UX",
        colour_set: "ux",
        colour_index: 2,
      });
      const { result } = renderHook(() => useQuotesStore());
      expect(result.current.proposedTags["q-P1-120"]).toHaveLength(1);
      expect(result.current.tags["q-P1-120"] ?? []).toHaveLength(0);
      expect(mockAcceptProposal).not.toHaveBeenCalled();
    });
  });

  describe("initFromQuotes — quotes field", () => {
    it("stores the raw quotes array", () => {
      const q1 = makeQuote({ dom_id: "q-P1-100" });
      const q2 = makeQuote({ dom_id: "q-P2-200" });
      initFromQuotes([q1, q2]);
      const { result } = renderHook(() => useQuotesStore());
      expect(result.current.quotes).toHaveLength(2);
      expect(result.current.quotes[0].dom_id).toBe("q-P1-100");
    });

    it("merges quotes from two init calls", () => {
      initFromQuotes([makeQuote({ dom_id: "q-P1-100" })]);
      initFromQuotes([makeQuote({ dom_id: "q-P2-200" })]);
      const { result } = renderHook(() => useQuotesStore());
      expect(result.current.quotes).toHaveLength(2);
    });

    // Regression: both islands (QuoteSections + QuoteThemes) call
    // initFromQuotes with the *full* set on mount. A plain concat made
    // store.quotes contain every quote twice, doubling every tag count in
    // the sidebar. The merge must dedup by dom_id.
    it("does not duplicate quotes when the full set is init'd twice", () => {
      const fullSet = [
        makeQuote({ dom_id: "q-P1-100" }),
        makeQuote({ dom_id: "q-P2-200" }),
        makeQuote({ dom_id: "q-P3-300" }),
      ];
      initFromQuotes(fullSet); // QuoteSections mount
      initFromQuotes(fullSet); // QuoteThemes mount — same full set
      const { result } = renderHook(() => useQuotesStore());
      expect(result.current.quotes).toHaveLength(3);
      expect(result.current.quotes.map((q) => q.dom_id)).toEqual([
        "q-P1-100",
        "q-P2-200",
        "q-P3-300",
      ]);
    });

    it("tag counts are not doubled when the full set is init'd twice", () => {
      const tagged = (dom_id: string) => makeQuote({ dom_id, tags: [TAG_FRUSTRATION] });
      const fullSet = [tagged("q-P1-100"), tagged("q-P2-200")];
      initFromQuotes(fullSet);
      initFromQuotes(fullSet);
      const { result } = renderHook(() => useQuotesStore());
      // Mirror the sidebar's count logic: one tally per (non-hidden) quote.
      const counts: Record<string, number> = {};
      for (const q of result.current.quotes) {
        if (result.current.hidden[q.dom_id]) continue;
        for (const t of result.current.tags[q.dom_id] ?? q.tags) {
          counts[t.name.toLowerCase()] = (counts[t.name.toLowerCase()] || 0) + 1;
        }
      }
      expect(counts["frustration"]).toBe(2);
    });

    it("replace mode resets quotes to only the new set", () => {
      initFromQuotes([makeQuote({ dom_id: "q-P1-100" })]);
      initFromQuotes([makeQuote({ dom_id: "q-P2-200" })], true);
      const { result } = renderHook(() => useQuotesStore());
      expect(result.current.quotes).toHaveLength(1);
      expect(result.current.quotes[0].dom_id).toBe("q-P2-200");
    });
  });

  describe("setSearchQuery", () => {
    it("updates the search query", () => {
      const { result } = renderHook(() => useQuotesStore());
      act(() => setSearchQuery("usability"));
      expect(result.current.searchQuery).toBe("usability");
    });

    it("does not make an API call", () => {
      setSearchQuery("test");
      expect(mockPutStarred).not.toHaveBeenCalled();
      expect(mockPutHidden).not.toHaveBeenCalled();
    });
  });

  describe("setViewMode", () => {
    it("switches to starred mode", () => {
      const { result } = renderHook(() => useQuotesStore());
      act(() => setViewMode("starred"));
      expect(result.current.viewMode).toBe("starred");
    });

    it("switches back to all mode", () => {
      const { result } = renderHook(() => useQuotesStore());
      act(() => setViewMode("starred"));
      act(() => setViewMode("all"));
      expect(result.current.viewMode).toBe("all");
    });
  });

  describe("setTagFilter", () => {
    it("updates the tag filter state", () => {
      const { result } = renderHook(() => useQuotesStore());
      const filter = { unchecked: ["UX"], noTagsUnchecked: true, clearAll: false };
      act(() => setTagFilter(filter));
      expect(result.current.tagFilter).toEqual(filter);
    });

    it("defaults to empty tag filter", () => {
      const { result } = renderHook(() => useQuotesStore());
      expect(result.current.tagFilter).toEqual(EMPTY_TAG_FILTER);
    });
  });

  describe("resetStore", () => {
    it("clears all state", () => {
      initFromQuotes([makeQuote({ is_starred: true, is_hidden: true })]);
      resetStore();
      const { result } = renderHook(() => useQuotesStore());
      expect(result.current.starred).toEqual({});
      expect(result.current.hidden).toEqual({});
    });
  });

  describe("subscriber notifications", () => {
    it("notifies subscribers on state change", () => {
      const { result } = renderHook(() => useQuotesStore());
      // The hook itself subscribes; test that mutations cause re-render.
      expect(result.current.starred).toEqual({});
      act(() => {
        toggleStar("q-P1-120", true);
      });
      expect(result.current.starred["q-P1-120"]).toBe(true);
    });
  });

  describe("cross-island scenario", () => {
    it("mutations are visible across independent hook instances", () => {
      // Simulates two islands reading from the same store.
      const hook1 = renderHook(() => useQuotesStore());
      const hook2 = renderHook(() => useQuotesStore());

      act(() => {
        initFromQuotes([makeQuote({ dom_id: "q-section-1" })]);
        initFromQuotes([makeQuote({ dom_id: "q-theme-1" })]);
      });

      // Star from "island 1"
      act(() => {
        toggleStar("q-section-1", true);
      });

      // Visible in both hooks
      expect(hook1.result.current.starred["q-section-1"]).toBe(true);
      expect(hook2.result.current.starred["q-section-1"]).toBe(true);
    });
  });

  describe("heading edits (Phase 2 — section identity)", () => {
    function makeSection(overrides: Partial<SectionResponse> = {}): SectionResponse {
      return {
        cluster_id: 5,
        screen_label: "Dashboard",
        description: "",
        display_order: 1,
        edited_label: null,
        edited_description: null,
        is_new: false,
        quotes: [],
        ...overrides,
      };
    }
    function makeTheme(overrides: Partial<ThemeResponse> = {}): ThemeResponse {
      return {
        theme_id: 7,
        theme_label: "Trust",
        description: "",
        edited_label: null,
        edited_description: null,
        is_new: false,
        quotes: [],
        ...overrides,
      };
    }

    it("seeds renames into the edits map keyed by durable id", () => {
      const { result } = renderHook(() => useQuotesStore());
      act(() => {
        initHeadingEdits(
          [makeSection({ cluster_id: 5, edited_label: "Home screen" })],
          [makeTheme({ theme_id: 7, edited_description: "A note" })],
        );
      });
      expect(result.current.edits["section-cluster-5:title"]).toBe("Home screen");
      expect(result.current.edits["theme-group-7:desc"]).toBe("A note");
      // Un-renamed fields are not seeded.
      expect(result.current.edits["section-cluster-5:desc"]).toBeUndefined();
    });

    it("commitHeadingEdit sends the FULL merged map so a quote edit is not wiped", () => {
      // The regression guard: PUT /edits is a full-replace, so heading + quote
      // edits must ride together or one wipes the other.
      initFromQuotes([makeQuote({ dom_id: "q-P1-100", edited_text: "kept quote edit" })]);
      act(() => {
        commitHeadingEdit("section-cluster-5:title", "Home screen");
      });
      const lastPayload = mockPutEdits.mock.calls[mockPutEdits.mock.calls.length - 1]?.[0];
      expect(lastPayload).toMatchObject({
        "q-P1-100": "kept quote edit",
        "section-cluster-5:title": "Home screen",
      });
    });

    it("a subsequent quote edit preserves the heading edit in the same payload", () => {
      initHeadingEdits([makeSection({ cluster_id: 5, edited_label: "Home screen" })], []);
      initFromQuotes([makeQuote({ dom_id: "q-P1-100" })]);
      act(() => {
        commitEdit("q-P1-100", "new quote text");
      });
      const lastPayload = mockPutEdits.mock.calls[mockPutEdits.mock.calls.length - 1]?.[0];
      expect(lastPayload).toMatchObject({
        "q-P1-100": "new quote text",
        "section-cluster-5:title": "Home screen",
      });
    });
  });
});

// ── Search tokens ────────────────────────────────────────────────────────

describe("search tokens", () => {
  const quotes = [
    makeQuote({ dom_id: "a", participant_id: "p1", text: "Tom was right about the price" }),
    makeQuote({ dom_id: "b", participant_id: "p2", text: "the price went up", tags: [TAG_FRUSTRATION] }),
    makeQuote({ dom_id: "c", participant_id: "p2", text: "fine" }),
  ];
  const tom = personToken("p2", { full_name: "Tom Fletcher", short_name: "Tom" });
  const tokens = () => getQuotesSnapshot().searchTokens;
  const visible = () => getVisibleQuotes(getQuotesSnapshot()).map((q) => q.dom_id);

  beforeEach(() => initFromQuotes(quotes));

  it("starts with none", () => {
    expect(tokens()).toEqual([]);
  });

  it("adds a token once: choosing the same person again changes nothing", () => {
    act(() => addSearchToken(tom));
    act(() => addSearchToken({ ...tom, mode: "not" }));
    expect(tokens()).toEqual([tom]);
  });

  it("narrows the visible quotes, which is what exports and counts read", () => {
    act(() => addSearchToken(tom));
    expect(visible()).toEqual(["b", "c"]);
    const { result } = renderHook(() => useQuoteCounts());
    expect(result.current.total).toBe(2);
  });

  it("ANDs tokens with each other and with the typed text", () => {
    act(() => addSearchToken(tom));
    act(() => addSearchToken(tagToken(TAG_FRUSTRATION)));
    expect(visible()).toEqual(["b"]);
    act(() => setSearchQuery("fine"));
    expect(visible()).toEqual([]);
  });

  it("changes a token's meaning in place", () => {
    act(() => addSearchToken(tom));
    act(() => setSearchTokenMode(tom, "mentions"));
    expect(tokens()[0].mode).toBe("mentions");
    expect(visible()).toEqual(["a"]);
    act(() => setSearchTokenMode(tom, "not"));
    expect(visible()).toEqual(["a"]);
  });

  it("refuses a meaning the token can't take", () => {
    act(() => addSearchToken(tom));
    act(() => setSearchTokenMode(tom, "tagged"));
    expect(tokens()[0].mode).toBe("said");
    const p9 = personToken("p9");
    act(() => addSearchToken(p9));
    act(() => setSearchTokenMode(p9, "mentions")); // no name to look for
    expect(tokens()[1].mode).toBe("said");
  });

  it("acts on the token it was given, even after another was removed", () => {
    const trust = tagToken({ name: "Trust" });
    act(() => addSearchToken(trust));
    act(() => addSearchToken(tom));
    act(() => removeSearchToken(trust));
    act(() => setSearchTokenMode(trust, "not")); // a menu still open on the removed token
    expect(tokens()).toEqual([tom]); // tom is untouched
  });

  it("finds what the researcher has just written in a quote", () => {
    act(() => commitEdit("c", "Tom said so"));
    act(() => addSearchToken({ ...tom, mode: "mentions" }));
    expect(visible()).toEqual(["a", "c"]);
    act(() => clearSearchTokens());
    act(() => setSearchQuery("said"));
    expect(visible()).toEqual(["c"]);
  });

  it("removes one token, ignores one that isn't there, and clears them all", () => {
    act(() => addSearchToken(tom));
    act(() => addSearchToken(tagToken(TAG_FRUSTRATION)));
    act(() => removeSearchToken(personToken("p9")));
    expect(tokens()).toHaveLength(2);
    act(() => removeSearchToken(tom));
    expect(tokens().map((t) => t.kind)).toEqual(["tag"]);
    act(() => clearSearchTokens());
    expect(tokens()).toEqual([]);
    expect(visible()).toEqual(["a", "b", "c"]);
  });
});

describe("filterStateOf", () => {
  beforeEach(() => initFromQuotes([makeQuote({ dom_id: "a" })]));

  it("returns the same object while nothing it reads has changed", () => {
    const first = filterStateOf(getQuotesSnapshot());
    act(() => deleteBadge("a", "negative")); // badges are not a filter
    expect(filterStateOf(getQuotesSnapshot())).toBe(first);
  });

  it("returns a new object when a quote's text is edited, because search reads it", () => {
    const first = filterStateOf(getQuotesSnapshot());
    act(() => commitEdit("a", "new words"));
    expect(filterStateOf(getQuotesSnapshot())).not.toBe(first);
  });

  it("returns a new object when a filter changes, tokens included", () => {
    const first = filterStateOf(getQuotesSnapshot());
    act(() => addSearchToken(personToken("P1")));
    const second = filterStateOf(getQuotesSnapshot());
    expect(second).not.toBe(first);
    expect(second.searchTokens).toHaveLength(1);
    act(() => setSearchQuery("login"));
    expect(filterStateOf(getQuotesSnapshot())).not.toBe(second);
  });
});
