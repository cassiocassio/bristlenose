import { act, renderHook, waitFor } from "@testing-library/react";
import { useReportQuotes } from "./quoteCardHost";
import { resetStore } from "../contexts/QuotesContext";
import { apiGet, getCodebook } from "../utils/api";
import type { ProposedTagBrief, QuoteResponse } from "../utils/types";

vi.mock("../utils/api", () => ({
  apiGet: vi.fn(),
  getCodebook: vi.fn(),
}));

const mockApiGet = vi.mocked(apiGet);
const mockGetCodebook = vi.mocked(getCodebook);

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

const PROPOSAL: ProposedTagBrief = {
  id: 7,
  tag_name: "Jargon barrier",
  group_name: "Norman",
  colour_set: "ux",
  colour_index: 0,
  confidence: 0.9,
  rationale: "",
};

function quotesResponse(quote: QuoteResponse) {
  return { sections: [{ quotes: [quote] }], themes: [], unjoined: [], has_moderator: false };
}

describe("useReportQuotes", () => {
  beforeEach(() => {
    resetStore();
    vi.clearAllMocks();
    mockGetCodebook.mockResolvedValue({ all_tag_names: [], groups: [] } as never);
  });

  it("reloads when tags change elsewhere, so AutoCode's proposals appear without a reload", async () => {
    mockApiGet.mockResolvedValueOnce(quotesResponse(makeQuote()) as never);
    const { result } = renderHook(() => useReportQuotes("test"));
    await waitFor(() => expect(result.current.loaded).toBe(true));
    expect(result.current.store.proposedTags["q-P1-120"]).toBeUndefined();

    mockApiGet.mockResolvedValueOnce(
      quotesResponse(makeQuote({ proposed_tags: [PROPOSAL] })) as never,
    );
    act(() => {
      document.dispatchEvent(new CustomEvent("bn:tags-changed"));
    });

    await waitFor(() =>
      expect(result.current.store.proposedTags["q-P1-120"]).toEqual([PROPOSAL]),
    );
    expect(mockApiGet).toHaveBeenCalledTimes(2);
  });
});
