import { render, screen, waitFor, act } from "@testing-library/react";
import { QuoteSections } from "./QuoteSections";
import type { QuotesListResponse } from "../utils/types";

vi.mock("../utils/api", () => ({
  apiGet: vi.fn(),
  getCodebook: vi.fn(),
}));

import { apiGet, getCodebook } from "../utils/api";
const mockApiGet = vi.mocked(apiGet);
const mockGetCodebook = vi.mocked(getCodebook);

const MOCK_QUOTES: QuotesListResponse = {
  sections: [
    {
      cluster_id: 1,
      screen_label: "Login",
      description: "Login screen findings",
      display_order: 1,
      quotes: [
        {
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
        },
      ],
    },
  ],
  themes: [],
  total_quotes: 1,
  total_hidden: 0,
  total_starred: 0,
  has_moderator: false,
};

const MOCK_QUOTES_WITH_TAGS: QuotesListResponse = {
  ...MOCK_QUOTES,
  sections: [
    {
      ...MOCK_QUOTES.sections[0],
      quotes: [
        {
          ...MOCK_QUOTES.sections[0].quotes[0],
          tags: [
            { name: "Frustration", codebook_group: "Emotions", colour_set: "emo", colour_index: 0, source: "human" },
          ],
        },
      ],
    },
  ],
};

function mockQuotesApi(data: unknown) {
  mockApiGet.mockResolvedValue(data);
}

const MOCK_CODEBOOK_WITH_GROUPS = {
  all_tag_names: ["Findable", "Credible", "Useful"],
  groups: [
    {
      id: 1,
      name: "Morville Honeycomb",
      subtitle: "UX honeycomb facets",
      colour_set: "morville",
      order: 0,
      tags: [
        { id: 1, name: "Findable", count: 0, colour_index: 0 },
        { id: 2, name: "Credible", count: 0, colour_index: 1 },
        { id: 3, name: "Useful", count: 0, colour_index: 2 },
      ],
      total_quotes: 0,
      is_default: false,
      framework_id: "morville",
    },
  ],
  ungrouped: [],
};

beforeEach(() => {
  mockGetCodebook.mockResolvedValue({ all_tag_names: [], groups: [], ungrouped: [] } as never);
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("QuoteSections", () => {
  it("renders quotes from API", async () => {
    mockQuotesApi(MOCK_QUOTES);
    render(<QuoteSections projectId="1" />);
    await waitFor(() => {
      expect(screen.getByText("Login")).toBeInTheDocument();
    });
  });

  it("builds tag vocabulary from codebook groups", async () => {
    mockQuotesApi(MOCK_QUOTES);
    mockGetCodebook.mockResolvedValue(MOCK_CODEBOOK_WITH_GROUPS as never);

    render(<QuoteSections projectId="1" />);
    await waitFor(() => {
      expect(screen.getByText("Login")).toBeInTheDocument();
    });

    // The codebook tag names should be fetched and available — verify
    // the getCodebook was called (the tagGroupMap is internal state,
    // but we verify the data flow works without errors).
    expect(mockGetCodebook).toHaveBeenCalled();
  });

  it("re-fetches quotes when bn:tags-changed event is dispatched", async () => {
    // Initial load returns quotes without tags.
    mockQuotesApi(MOCK_QUOTES);

    render(<QuoteSections projectId="1" />);
    await waitFor(() => {
      expect(screen.getByText("Login")).toBeInTheDocument();
    });

    // No tag badges initially.
    expect(screen.queryByText("Frustration")).not.toBeInTheDocument();

    // Switch to returning quotes with tags for the next fetch.
    mockQuotesApi(MOCK_QUOTES_WITH_TAGS);

    // Simulate the event that CodebookPanel dispatches after bulk apply.
    act(() => {
      document.dispatchEvent(new CustomEvent("bn:tags-changed"));
    });

    // After the event, quotes should re-fetch and show the new tag.
    await waitFor(() => {
      expect(screen.getByText("Frustration")).toBeInTheDocument();
    });
  });
});
