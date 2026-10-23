import { render, screen, waitFor, act, fireEvent } from "@testing-library/react";
import { QuoteSections } from "./QuoteSections";
import { QuoteThemes } from "./QuoteThemes";
import type { QuotesListResponse } from "../utils/types";
import { commitHeadingEdit, resetStore } from "../contexts/QuotesContext";
import { redo, resetUndoStore, undo } from "../contexts/UndoStore";

vi.mock("../utils/api", () => ({
  apiGet: vi.fn(),
  getCodebook: vi.fn(),
  patchEdits: vi.fn(() => Promise.resolve()),
}));

import { apiGet, getCodebook, patchEdits } from "../utils/api";
const mockApiGet = vi.mocked(apiGet);
const mockGetCodebook = vi.mocked(getCodebook);

const MOCK_QUOTES: QuotesListResponse = {
  sections: [
    {
      cluster_id: 1,
      screen_label: "Login",
      description: "Login screen findings",
      display_order: 1,
      edited_label: null,
      edited_description: null,
      is_new: false,
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
      edited_label: null,
      edited_description: null,
      is_new: false,
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
  resetStore();
  resetUndoStore();
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

  it("Edit ▸ Undo redraws a section rename, and redo brings it back", async () => {
    mockQuotesApi(MOCK_QUOTES);
    render(<QuoteSections projectId="1" />);
    await waitFor(() => expect(screen.getByText("Login")).toBeInTheDocument());
    act(() => commitHeadingEdit("section-cluster-1:title", "Sign-in"));
    expect(screen.getByText("Sign-in")).toBeInTheDocument();
    await act(async () => {
      await undo();
    });
    expect(screen.getByText("Login")).toBeInTheDocument();
    expect(screen.queryByText("Sign-in")).not.toBeInTheDocument();
    await act(async () => {
      await redo();
    });
    expect(screen.getByText("Sign-in")).toBeInTheDocument();
  });

  // Decision #30: the report does not show spacing, so respacing a heading's
  // description is no edit — no write, no "Undo Edit Description".
  it("a description changed only in spacing writes nothing", async () => {
    mockQuotesApi(MOCK_QUOTES);
    render(<QuoteSections projectId="1" />);
    await waitFor(() => expect(screen.getByText("Login")).toBeInTheDocument());
    vi.mocked(patchEdits).mockClear();
    act(() => screen.getByRole("button", { name: "Edit section description" }).click());
    const desc = screen.getByTestId("bn-group-section-1-desc");
    desc.textContent = "Login  screen findings";
    fireEvent.keyDown(desc, { key: "Enter" });
    expect(patchEdits).not.toHaveBeenCalled();
  });

  it("anchors a section on its id, so renaming it moves no link", async () => {
    mockQuotesApi({
      ...MOCK_QUOTES,
      sections: [{ ...MOCK_QUOTES.sections[0], edited_label: "Sign-in" }],
    });
    render(<QuoteSections projectId="1" />);
    await waitFor(() => expect(screen.getByText("Sign-in")).toBeInTheDocument());
    expect(document.getElementById("section-1")).toHaveTextContent("Sign-in");
    act(() => commitHeadingEdit("section-cluster-1:title", "Account access"));
    expect(document.getElementById("section-1")).toHaveTextContent("Account access");
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

    // Simulate the event the codebook lens dispatches after bulk apply
    // (`CodebookV2.tsx`; `AppLayout` dispatches the same one).
    act(() => {
      document.dispatchEvent(new CustomEvent("bn:tags-changed"));
    });

    // After the event, quotes should re-fetch and show the new tag.
    await waitFor(() => {
      expect(screen.getByText("Frustration")).toBeInTheDocument();
    });
  });
});


// R86: a read that fails said "Failed to load quotes: GET /quotes 500: …", the
// wire string in a sentence, and offered nothing to do about it.
describe("a failed read says so in the lens's words, with Retry", () => {
  for (const [name, Lens] of [["sections", QuoteSections], ["themes", QuoteThemes]] as const) {
    it(`on the ${name} grouping`, async () => {
      const logged = vi.spyOn(console, "error").mockImplementation(() => {});
      const wire = new Error("GET /quotes 500: Internal Server Error");
      mockApiGet.mockRejectedValue(wire);
      render(<Lens projectId="1" />);
      expect(
        await screen.findByText("This lens couldn’t be shown. Try again, or choose another lens."),
      ).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument();
      expect(screen.queryByText(/500|\/quotes/)).toBeNull();
      expect(logged).toHaveBeenCalledWith(expect.any(String), wire);
    });

    it(`on the ${name} grouping, clears once the next read answers`, async () => {
      // During a run there is a re-read per import; one that fails must not stay
      // over the good one that follows (as QuoteSessions already did).
      vi.spyOn(console, "error").mockImplementation(() => {});
      mockApiGet.mockRejectedValueOnce(new Error("busy")).mockResolvedValue(MOCK_QUOTES);
      const { rerender } = render(<Lens projectId="1" refreshKey={0} />);
      await screen.findByText("This lens couldn’t be shown. Try again, or choose another lens.");
      rerender(<Lens projectId="1" refreshKey={1} />);
      await waitFor(() =>
        expect(
          screen.queryByText("This lens couldn’t be shown. Try again, or choose another lens."),
        ).toBeNull(),
      );
    });
  }
});

// After a run the new quotes land with the hand-over on the lens's own section (useLensRead).
describe.each([
  ["QuoteSections", (k: number) => <QuoteSections projectId="1" refreshKey={k} />],
  ["QuoteThemes", (k: number) => <QuoteThemes projectId="1" refreshKey={k} />],
])("%s — the read after a run", (_name, lens) => {
  it("plays the hand-over on the drawn section when new quotes land", async () => {
    mockQuotesApi({
      ...MOCK_QUOTES,
      themes: [{
        theme_id: 1, theme_label: "Trust", description: "", edited_label: null,
        edited_description: null, is_new: false, quotes: MOCK_QUOTES.sections[0].quotes,
      }],
    });
    const { container, rerender } = render(lens(0));
    await waitFor(() => expect(container.querySelector("section")).not.toBeNull());
    await waitFor(() => expect(screen.getAllByText("I found the login confusing").length).toBeGreaterThan(0));
    expect(container.querySelector(".bn-handover")).toBeNull();
    rerender(lens(1));
    await waitFor(() => expect(container.querySelector("section.bn-handover")).not.toBeNull());
  });
});
