import { render, fireEvent, act } from "@testing-library/react";
import { Toolbar } from "./Toolbar";
import { initFromQuotes, resetStore } from "../contexts/QuotesContext";
import { _resetEmbeddedCache } from "../utils/embedded";
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
  delete (window as unknown as Record<string, unknown>).__BRISTLENOSE_EMBEDDED__;
  _resetEmbeddedCache();
  vi.useFakeTimers();
});

afterEach(() => {
  vi.useRealTimers();
  delete (window as unknown as Record<string, unknown>).__BRISTLENOSE_EMBEDDED__;
  _resetEmbeddedCache();
});

describe("Toolbar", () => {
  it("renders toolbar sections (search + view switcher, no tag filter)", () => {
    const { getByTestId, queryByTestId } = render(<Toolbar />);
    expect(getByTestId("bn-toolbar")).toBeDefined();
    expect(getByTestId("bn-toolbar-search")).toBeDefined();
    expect(getByTestId("bn-toolbar-view-switcher")).toBeDefined();
    // Tag-filter dropdown removed (v0.16) — superseded by the tag sidebar.
    expect(queryByTestId("bn-toolbar-tag-filter")).toBeNull();
  });

  it("renders nothing in embedded (macOS) mode", () => {
    (window as unknown as Record<string, unknown>).__BRISTLENOSE_EMBEDDED__ = true;
    _resetEmbeddedCache();
    const { queryByTestId } = render(<Toolbar />);
    // Search + starred are native toolbar controls; tags are the sidebar.
    expect(queryByTestId("bn-toolbar")).toBeNull();
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
});
