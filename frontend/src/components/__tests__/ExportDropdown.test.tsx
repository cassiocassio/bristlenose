import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { ExportDropdown } from "../ExportDropdown";
import { initFromQuotes, resetStore } from "../../contexts/QuotesContext";
import { FocusProvider } from "../../contexts/FocusContext";
import type { QuoteResponse } from "../../utils/types";

// Mock API
vi.mock("../../utils/api", () => ({
  authHeaders: vi.fn(() => ({ Authorization: "Bearer test-token" })),
  putHidden: vi.fn(),
  putStarred: vi.fn(),
  putEdits: vi.fn(),
  putTags: vi.fn(),
  putDeletedBadges: vi.fn(),
  acceptProposal: vi.fn().mockResolvedValue(undefined),
  denyProposal: vi.fn().mockResolvedValue(undefined),
  getCodebook: vi.fn().mockResolvedValue({ groups: [], ungrouped: [], all_tag_names: [] }),
}));

// Mock toast
vi.mock("../../utils/toast", () => ({
  toast: vi.fn(),
}));

// Mock announce
vi.mock("../../utils/announce", () => ({
  announce: vi.fn(),
}));

// Mock exportData
vi.mock("../../utils/exportData", () => ({
  isExportMode: vi.fn(() => false),
  getExportData: vi.fn(() => null),
}));

function makeQuote(overrides: Partial<QuoteResponse> = {}): QuoteResponse {
  return {
    dom_id: "q-p1-1",
    text: "Test quote",
    verbatim_excerpt: "test",
    participant_id: "p1",
    session_id: "s1",
    speaker_name: "Alice",
    start_timecode: 10,
    end_timecode: 20,
    sentiment: "frustration",
    intensity: 2,
    researcher_context: null,
    quote_type: "experience",
    topic_label: "Dashboard",
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

function renderDropdown(initialEntry = "/report/quotes/") {
  const onExportReport = vi.fn();
  const router = createMemoryRouter(
    [
      {
        path: "/report/*",
        element: (
          <FocusProvider>
            <ExportDropdown onExportReport={onExportReport} />
          </FocusProvider>
        ),
      },
    ],
    { initialEntries: [initialEntry] },
  );
  const result = render(<RouterProvider router={router} />);
  return { ...result, onExportReport };
}

beforeEach(() => {
  resetStore();
  vi.clearAllMocks();
});

describe("ExportDropdown", () => {
  it("renders trigger button", () => {
    renderDropdown();
    expect(screen.getByRole("button", { name: "Export" })).toBeInTheDocument();
  });

  it("opens dropdown on click", () => {
    renderDropdown();
    fireEvent.click(screen.getByRole("button", { name: "Export" }));
    expect(screen.getByTestId("export-dropdown-menu")).toBeInTheDocument();
  });

  it("shows 4 items on Quotes tab", () => {
    initFromQuotes([makeQuote()]);
    renderDropdown("/report/quotes/");
    fireEvent.click(screen.getByRole("button", { name: "Export" }));

    const items = screen.getAllByRole("menuitem");
    expect(items).toHaveLength(4);
  });

  it("shows only Export Report on non-Quotes tabs", () => {
    renderDropdown("/report/sessions/");
    fireEvent.click(screen.getByRole("button", { name: "Export" }));

    const items = screen.getAllByRole("menuitem");
    expect(items).toHaveLength(1);
    expect(items[0].textContent).toContain("Export Report");
  });

  it("shows quote count in Copy label", () => {
    initFromQuotes([
      makeQuote({ dom_id: "q-p1-1" }),
      makeQuote({ dom_id: "q-p1-2" }),
    ]);
    renderDropdown("/report/quotes/");
    fireEvent.click(screen.getByRole("button", { name: "Export" }));

    const items = screen.getAllByRole("menuitem");
    expect(items[0].textContent).toContain("2");
  });

  it("shows paste hint on Quotes tab", () => {
    initFromQuotes([makeQuote()]);
    renderDropdown("/report/quotes/");
    fireEvent.click(screen.getByRole("button", { name: "Export" }));

    expect(screen.getByText(/Miro, Excel/)).toBeInTheDocument();
  });

  it("Export Report calls onExportReport callback", () => {
    const { onExportReport } = renderDropdown("/report/sessions/");
    fireEvent.click(screen.getByRole("button", { name: "Export" }));
    fireEvent.click(screen.getByRole("menuitem"));
    expect(onExportReport).toHaveBeenCalledOnce();
  });

  it("closes dropdown after action", () => {
    renderDropdown("/report/sessions/");
    fireEvent.click(screen.getByRole("button", { name: "Export" }));
    expect(screen.getByTestId("export-dropdown-menu")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("menuitem"));
    expect(screen.queryByTestId("export-dropdown-menu")).toBeNull();
  });

  it("has aria-haspopup and aria-expanded", () => {
    renderDropdown();
    const btn = screen.getByRole("button", { name: "Export" });
    expect(btn.getAttribute("aria-haspopup")).toBe("menu");
    expect(btn.getAttribute("aria-expanded")).toBe("false");

    fireEvent.click(btn);
    expect(btn.getAttribute("aria-expanded")).toBe("true");
  });

  it("has separators between quote actions and report export", () => {
    initFromQuotes([makeQuote()]);
    renderDropdown("/report/quotes/");
    fireEvent.click(screen.getByRole("button", { name: "Export" }));

    const menu = screen.getByTestId("export-dropdown-menu");
    const separators = menu.querySelectorAll('[role="separator"]');
    expect(separators.length).toBeGreaterThanOrEqual(2);
  });

  it("Escape closes dropdown", () => {
    renderDropdown();
    fireEvent.click(screen.getByRole("button", { name: "Export" }));
    expect(screen.getByTestId("export-dropdown-menu")).toBeInTheDocument();

    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.queryByTestId("export-dropdown-menu")).toBeNull();
  });

  it("Copy Quotes calls fetch with auth header", async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      text: () => Promise.resolve("csv,data"),
    });
    vi.stubGlobal("fetch", mockFetch);

    // Mock clipboard — jsdom doesn't have ClipboardItem
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.assign(navigator, { clipboard: { writeText, write: undefined } });

    initFromQuotes([makeQuote()]);
    renderDropdown("/report/quotes/");
    fireEvent.click(screen.getByRole("button", { name: "Export" }));

    const items = screen.getAllByRole("menuitem");
    fireEvent.click(items[0]); // Copy Quotes

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledOnce();
      const [url, opts] = mockFetch.mock.calls[0];
      expect(url).toContain("/export/quotes.csv");
      expect(opts.headers).toHaveProperty("Authorization");
    });

    vi.unstubAllGlobals();
  });
});
