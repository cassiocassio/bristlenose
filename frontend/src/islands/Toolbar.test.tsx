import { render, fireEvent, act } from "@testing-library/react";
import { Toolbar } from "./Toolbar";
import { initFromQuotes, resetStore } from "../contexts/QuotesContext";
import type { QuoteResponse } from "../utils/types";

// Mock API
vi.mock("../utils/api", () => ({
  putHidden: vi.fn(),
  putStarred: vi.fn(),
  putEdits: vi.fn(),
  putTags: vi.fn(),
  putDeletedBadges: vi.fn(),
  acceptProposal: vi.fn().mockResolvedValue(undefined),
  denyProposal: vi.fn().mockResolvedValue(undefined),
  getCodebook: vi.fn().mockResolvedValue({
    groups: [
      {
        id: 1, name: "UX", subtitle: "", colour_set: "ux", order: 0,
        tags: [{ id: 10, name: "Navigation", count: 3, colour_index: 0 }],
        total_quotes: 3, is_default: false, framework_id: null,
      },
    ],
    ungrouped: [],
    all_tag_names: ["Navigation"],
  }),
}));

function makeQuote(overrides: Partial<QuoteResponse> = {}): QuoteResponse {
  return {
    dom_id: "q-p1-1",
    text: "Test quote about usability",
    verbatim_excerpt: "usability",
    participant_id: "p1",
    session_id: "s1",
    speaker_name: "Alice",
    start_timecode: 120,
    end_timecode: 130,
    sentiment: "frustration",
    intensity: 2,
    researcher_context: null,
    quote_type: "experience",
    topic_label: "Usability",
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

beforeEach(() => {
  resetStore();
  vi.useFakeTimers();
});

afterEach(() => {
  vi.useRealTimers();
});

describe("Toolbar", () => {
  it("renders all four toolbar sections", () => {
    const { getByTestId } = render(<Toolbar />);
    expect(getByTestId("bn-toolbar")).toBeDefined();
    expect(getByTestId("bn-toolbar-search")).toBeDefined();
    expect(getByTestId("bn-toolbar-tag-filter")).toBeDefined();
    expect(getByTestId("bn-toolbar-view-switcher")).toBeDefined();
    expect(getByTestId("bn-toolbar-csv")).toBeDefined();
  });

  it("applies .toolbar CSS class", () => {
    const { getByTestId } = render(<Toolbar />);
    expect(getByTestId("bn-toolbar").classList.contains("toolbar")).toBe(true);
  });

  it("search box updates store", () => {
    initFromQuotes([makeQuote()]);
    const { getByTestId } = render(<Toolbar />);

    // Expand search
    fireEvent.click(getByTestId("bn-toolbar-search-toggle"));
    fireEvent.change(getByTestId("bn-toolbar-search-input"), {
      target: { value: "usability" },
    });

    // Advance debounce
    act(() => vi.advanceTimersByTime(150));

    // The view switcher label should update to show matching count
    expect(getByTestId("bn-toolbar-view-switcher-btn").textContent).toContain("matching");
  });

  it("view switcher changes mode", () => {
    initFromQuotes([makeQuote({ is_starred: true }), makeQuote({ dom_id: "q-p1-2" })]);
    const { getByTestId, getByText } = render(<Toolbar />);

    fireEvent.click(getByTestId("bn-toolbar-view-switcher-btn"));
    fireEvent.click(getByText("Starred quotes"));

    // Label should now say "Starred quotes"
    expect(getByTestId("bn-toolbar-view-switcher-btn").textContent).toContain("Starred quotes");
  });

  it("CSV export copies to clipboard", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.assign(navigator, { clipboard: { writeText } });

    initFromQuotes([
      makeQuote({ dom_id: "q-p1-1", text: "Quote one", speaker_name: "Alice" }),
      makeQuote({ dom_id: "q-p1-2", text: "Quote two", speaker_name: "Bob" }),
    ]);

    const { getByTestId } = render(<Toolbar />);
    fireEvent.click(getByTestId("bn-toolbar-csv"));

    // Should have called clipboard with CSV
    expect(writeText).toHaveBeenCalledOnce();
    const csv = writeText.mock.calls[0][0] as string;
    expect(csv).toContain("Timecode,Quote,Participant,Topic,Sentiment,Tags");
    expect(csv).toContain("Quote one");
    expect(csv).toContain("Quote two");
    expect(csv).toContain("Alice");
  });

  it("mutual dropdown exclusion — opening one closes the other", () => {
    const { getByTestId, queryByTestId } = render(<Toolbar />);

    // Open tag filter
    fireEvent.click(getByTestId("bn-toolbar-tag-filter-btn"));
    // Tag filter should request open — but we need to wait for async codebook fetch

    // Open view switcher
    fireEvent.click(getByTestId("bn-toolbar-view-switcher-btn"));
    expect(queryByTestId("bn-toolbar-view-switcher-menu")).not.toBeNull();

    // Now open tag filter — view switcher should close
    fireEvent.click(getByTestId("bn-toolbar-tag-filter-btn"));
    expect(queryByTestId("bn-toolbar-view-switcher-menu")).toBeNull();
  });
});
