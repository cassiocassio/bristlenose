import { render, screen, waitFor, act } from "@testing-library/react";
import { QuoteSections } from "./QuoteSections";
import type { QuotesListResponse } from "../utils/types";

vi.mock("../utils/api", () => ({
  getCodebook: vi.fn(),
}));

import { getCodebook } from "../utils/api";
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
            { name: "Frustration", codebook_group: "Emotions", colour_set: "emo", colour_index: 0 },
          ],
        },
      ],
    },
  ],
};

function mockFetch(data: unknown) {
  globalThis.fetch = vi.fn().mockResolvedValue({
    ok: true,
    json: () => Promise.resolve(data),
  });
}

beforeEach(() => {
  mockGetCodebook.mockResolvedValue({ all_tag_names: [], groups: [], ungrouped: [] } as never);
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("QuoteSections", () => {
  it("renders quotes from API", async () => {
    mockFetch(MOCK_QUOTES);
    render(<QuoteSections projectId="1" />);
    await waitFor(() => {
      expect(screen.getByText("Login")).toBeInTheDocument();
    });
  });

  it("re-fetches quotes when bn:tags-changed event is dispatched", async () => {
    // Initial load returns quotes without tags.
    mockFetch(MOCK_QUOTES);

    render(<QuoteSections projectId="1" />);
    await waitFor(() => {
      expect(screen.getByText("Login")).toBeInTheDocument();
    });

    // No tag badges initially.
    expect(screen.queryByText("Frustration")).not.toBeInTheDocument();

    // Switch to returning quotes with tags for the next fetch.
    mockFetch(MOCK_QUOTES_WITH_TAGS);

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
