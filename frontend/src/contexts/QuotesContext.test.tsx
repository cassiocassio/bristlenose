import { renderHook, act } from "@testing-library/react";
import type { QuoteResponse, TagResponse } from "../utils/types";
import {
  initFromQuotes,
  resetStore,
  toggleStar,
  toggleHide,
  commitEdit,
  addTag,
  removeTag,
  deleteBadge,
  restoreBadges,
  acceptProposedTag,
  denyProposedTag,
  useQuotesStore,
} from "./QuotesContext";

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

  describe("toggleHide", () => {
    it("hides a quote and calls putHidden", () => {
      initFromQuotes([makeQuote()]);
      toggleHide("q-P1-120", true);
      const { result } = renderHook(() => useQuotesStore());
      expect(result.current.hidden["q-P1-120"]).toBe(true);
      expect(mockPutHidden).toHaveBeenCalledWith({ "q-P1-120": true });
    });

    it("unhides a quote", () => {
      initFromQuotes([makeQuote({ is_hidden: true })]);
      toggleHide("q-P1-120", false);
      const { result } = renderHook(() => useQuotesStore());
      expect(result.current.hidden["q-P1-120"]).toBeUndefined();
      expect(mockPutHidden).toHaveBeenCalledWith({});
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
});
