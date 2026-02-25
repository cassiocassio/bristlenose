/**
 * Integration tests: Toolbar → QuotesStore → Quote Islands
 *
 * Verifies that toolbar actions (search, view mode, tag filter)
 * propagate through the store and affect which quotes are rendered
 * by QuoteSections and QuoteThemes.
 */

import { render, screen, waitFor, act } from "@testing-library/react";
import { QuoteSections } from "./QuoteSections";
import { QuoteThemes } from "./QuoteThemes";
import type { QuotesListResponse } from "../utils/types";
import {
  resetStore,
  setSearchQuery,
  setViewMode,
  setTagFilter,
  toggleStar,
} from "../contexts/QuotesContext";

vi.mock("../utils/api", () => ({
  getCodebook: vi.fn(),
  putHidden: vi.fn(),
  putStarred: vi.fn(),
  putEdits: vi.fn(),
  putTags: vi.fn(),
  putDeletedBadges: vi.fn(),
  acceptProposal: vi.fn(),
  denyProposal: vi.fn(),
  getModeratorQuestion: vi.fn(),
}));

import { getCodebook } from "../utils/api";
const mockGetCodebook = vi.mocked(getCodebook);

const MOCK_DATA: QuotesListResponse = {
  sections: [
    {
      cluster_id: 1,
      screen_label: "Onboarding",
      description: "First-time user experience",
      display_order: 1,
      quotes: [
        {
          dom_id: "q-P1-10",
          text: "The onboarding was really smooth",
          verbatim_excerpt: "really smooth",
          participant_id: "P1",
          session_id: "s1",
          speaker_name: "Alice",
          start_timecode: 10,
          end_timecode: 15,
          sentiment: "positive",
          intensity: 2,
          researcher_context: null,
          quote_type: "section",
          topic_label: "Onboarding",
          is_starred: false,
          is_hidden: false,
          edited_text: null,
          tags: [{ name: "UX", codebook_group: "General", colour_set: "", colour_index: 0 }],
          deleted_badges: [],
          proposed_tags: [],
          segment_index: 0,
        },
        {
          dom_id: "q-P2-20",
          text: "I got confused by the navigation buttons",
          verbatim_excerpt: "confused by the navigation",
          participant_id: "P2",
          session_id: "s2",
          speaker_name: "Bob",
          start_timecode: 20,
          end_timecode: 25,
          sentiment: "frustration",
          intensity: 3,
          researcher_context: null,
          quote_type: "section",
          topic_label: "Onboarding",
          is_starred: true,
          is_hidden: false,
          edited_text: null,
          tags: [{ name: "Performance", codebook_group: "General", colour_set: "", colour_index: 0 }],
          deleted_badges: [],
          proposed_tags: [],
          segment_index: 1,
        },
      ],
    },
    {
      cluster_id: 2,
      screen_label: "Settings",
      description: "Settings page findings",
      display_order: 2,
      quotes: [
        {
          dom_id: "q-P3-30",
          text: "Settings were hard to find",
          verbatim_excerpt: "hard to find",
          participant_id: "P3",
          session_id: "s3",
          speaker_name: "Charlie",
          start_timecode: 30,
          end_timecode: 35,
          sentiment: "negative",
          intensity: 2,
          researcher_context: null,
          quote_type: "section",
          topic_label: "Settings",
          is_starred: false,
          is_hidden: false,
          edited_text: null,
          tags: [],
          deleted_badges: [],
          proposed_tags: [],
          segment_index: 0,
        },
      ],
    },
  ],
  themes: [
    {
      theme_id: 1,
      theme_label: "Usability",
      description: "Overall usability",
      quotes: [
        {
          dom_id: "q-P4-40",
          text: "The interface felt intuitive and easy to use",
          verbatim_excerpt: "intuitive and easy",
          participant_id: "P4",
          session_id: "s4",
          speaker_name: "Dana",
          start_timecode: 40,
          end_timecode: 45,
          sentiment: "positive",
          intensity: 2,
          researcher_context: null,
          quote_type: "theme",
          topic_label: "Usability",
          is_starred: true,
          is_hidden: false,
          edited_text: null,
          tags: [{ name: "UX", codebook_group: "General", colour_set: "", colour_index: 0 }],
          deleted_badges: [],
          proposed_tags: [],
          segment_index: 0,
        },
      ],
    },
  ],
  total_quotes: 4,
  total_hidden: 0,
  total_starred: 2,
  has_moderator: false,
};

function mockFetch() {
  globalThis.fetch = vi.fn().mockResolvedValue({
    ok: true,
    json: () => Promise.resolve(MOCK_DATA),
  });
}

beforeEach(() => {
  resetStore();
  mockFetch();
  mockGetCodebook.mockResolvedValue({
    all_tag_names: ["UX", "Performance"],
    groups: [],
    ungrouped: [],
  } as never);
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("Toolbar → Store → Quote Islands integration", () => {
  it("search query filters quotes in sections", async () => {
    render(<QuoteSections projectId="1" />);
    await waitFor(() => {
      expect(screen.getByText(/onboarding was really smooth/i)).toBeInTheDocument();
    });

    // Both section quotes visible initially
    expect(screen.getByText(/confused by the navigation/i)).toBeInTheDocument();

    // Set search query — "smooth" matches only first quote
    act(() => setSearchQuery("smooth"));
    await waitFor(() => {
      expect(screen.getByText(/smooth/i)).toBeInTheDocument();
      expect(screen.queryByText(/confused by the navigation/i)).not.toBeInTheDocument();
    });

    // Clear search — both visible again
    act(() => setSearchQuery(""));
    await waitFor(() => {
      expect(screen.getByText(/confused by the navigation/i)).toBeInTheDocument();
    });
  });

  it("search highlighting wraps matched text in <mark> elements", async () => {
    render(<QuoteSections projectId="1" />);
    await waitFor(() => {
      expect(screen.getByText(/onboarding was really smooth/i)).toBeInTheDocument();
    });

    act(() => setSearchQuery("smooth"));
    await waitFor(() => {
      const marks = document.querySelectorAll("mark.search-mark");
      expect(marks.length).toBeGreaterThan(0);
      expect(marks[0].textContent).toBe("smooth");
    });
  });

  it("starred view mode filters out non-starred quotes", async () => {
    render(<QuoteSections projectId="1" />);
    await waitFor(() => {
      expect(screen.getByText(/onboarding was really smooth/i)).toBeInTheDocument();
    });

    // Switch to starred view
    act(() => setViewMode("starred"));
    await waitFor(() => {
      // Bob's quote is starred — should be visible
      expect(screen.getByText(/confused by the navigation/i)).toBeInTheDocument();
      // Alice's quote is not starred — should be hidden
      expect(screen.queryByText(/onboarding was really smooth/i)).not.toBeInTheDocument();
      // Charlie's quote is not starred — Settings section should disappear
      expect(screen.queryByText(/Settings were hard to find/i)).not.toBeInTheDocument();
    });

    // Back to all
    act(() => setViewMode("all"));
    await waitFor(() => {
      expect(screen.getByText(/onboarding was really smooth/i)).toBeInTheDocument();
    });
  });

  it("tag filter hides quotes with unchecked tags", async () => {
    render(<QuoteSections projectId="1" />);
    await waitFor(() => {
      expect(screen.getByText(/onboarding was really smooth/i)).toBeInTheDocument();
    });

    // Uncheck "UX" tag — Alice's quote (tagged UX) should be hidden
    act(() => setTagFilter({ unchecked: ["UX"], noTagsUnchecked: false, clearAll: false }));
    await waitFor(() => {
      expect(screen.queryByText(/onboarding was really smooth/i)).not.toBeInTheDocument();
      // Bob's quote (tagged Performance) still visible
      expect(screen.getByText(/confused by the navigation/i)).toBeInTheDocument();
    });
  });

  it("tag filter clearAll hides all quotes", async () => {
    render(<QuoteSections projectId="1" />);
    await waitFor(() => {
      expect(screen.getByText(/onboarding was really smooth/i)).toBeInTheDocument();
    });

    act(() => setTagFilter({ unchecked: [], noTagsUnchecked: true, clearAll: true }));
    await waitFor(() => {
      expect(screen.queryByText(/onboarding was really smooth/i)).not.toBeInTheDocument();
      expect(screen.queryByText(/confused by the navigation/i)).not.toBeInTheDocument();
    });
  });

  it("noTagsUnchecked hides untagged quotes", async () => {
    render(<QuoteSections projectId="1" />);
    await waitFor(() => {
      expect(screen.getByText(/Settings were hard to find/i)).toBeInTheDocument();
    });

    // Charlie's quote has no tags — should be hidden when noTagsUnchecked
    act(() => setTagFilter({ unchecked: [], noTagsUnchecked: true, clearAll: false }));
    await waitFor(() => {
      expect(screen.queryByText(/Settings were hard to find/i)).not.toBeInTheDocument();
      // Tagged quotes still visible
      expect(screen.getByText(/onboarding was really smooth/i)).toBeInTheDocument();
    });
  });

  it("themes are filtered by search query", async () => {
    render(<QuoteThemes projectId="1" />);
    await waitFor(() => {
      expect(screen.getByText(/intuitive and easy to use/i)).toBeInTheDocument();
    });

    // Search for something that doesn't match the theme quote
    act(() => setSearchQuery("onboarding"));
    await waitFor(() => {
      expect(screen.queryByText(/intuitive and easy to use/i)).not.toBeInTheDocument();
    });
  });

  it("themes are filtered by view mode", async () => {
    render(<QuoteThemes projectId="1" />);
    await waitFor(() => {
      expect(screen.getByText(/intuitive and easy to use/i)).toBeInTheDocument();
    });

    // Dana's quote is starred — should remain visible
    act(() => setViewMode("starred"));
    await waitFor(() => {
      expect(screen.getByText(/intuitive and easy to use/i)).toBeInTheDocument();
    });
  });

  it("starring a quote via store makes it visible in starred view", async () => {
    render(<QuoteSections projectId="1" />);
    await waitFor(() => {
      expect(screen.getByText(/onboarding was really smooth/i)).toBeInTheDocument();
    });

    // Switch to starred — Alice's unstarred quote disappears
    act(() => setViewMode("starred"));
    await waitFor(() => {
      expect(screen.queryByText(/onboarding was really smooth/i)).not.toBeInTheDocument();
    });

    // Star Alice's quote via store
    act(() => toggleStar("q-P1-10", true));
    await waitFor(() => {
      expect(screen.getByText(/onboarding was really smooth/i)).toBeInTheDocument();
    });
  });

  it("empty sections are removed from the DOM when all quotes are filtered out", async () => {
    render(<QuoteSections projectId="1" />);
    await waitFor(() => {
      expect(screen.getByText("Settings")).toBeInTheDocument();
    });

    // Filter by starred — Settings section has no starred quotes, should disappear
    act(() => setViewMode("starred"));
    await waitFor(() => {
      // The Settings heading should no longer be rendered
      expect(screen.queryByText("Settings")).not.toBeInTheDocument();
      // Onboarding still has a starred quote (Bob's)
      expect(screen.getByText("Onboarding")).toBeInTheDocument();
    });
  });
});
