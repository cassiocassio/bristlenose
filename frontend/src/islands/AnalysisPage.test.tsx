import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { AnalysisPage } from "./AnalysisPage";
import type { TagAnalysisResponse, SentimentAnalysisData } from "../utils/types";

// ---------------------------------------------------------------------------
// Mock data
// ---------------------------------------------------------------------------

const mockTagData: TagAnalysisResponse = {
  signals: [
    {
      location: "Checkout",
      source_type: "section",
      group_name: "Pain points",
      count: 5,
      participants: ["p1", "p2", "p3"],
      n_eff: 2.8,
      mean_intensity: 2.1,
      concentration: 2.5,
      composite_signal: 0.4567,
      confidence: "strong",
      quotes: [
        {
          text: "The checkout was really slow",
          participant_id: "p1",
          session_id: "s1",
          start_seconds: 120.5,
          intensity: 3,
        },
        {
          text: "I had to wait for ages",
          participant_id: "p2",
          session_id: "s1",
          start_seconds: 200.0,
          intensity: 2,
        },
      ],
    },
    {
      location: "Onboarding",
      source_type: "theme",
      group_name: "Mental models",
      count: 3,
      participants: ["p1", "p3"],
      n_eff: 1.8,
      mean_intensity: 1.5,
      concentration: 1.8,
      composite_signal: 0.2345,
      confidence: "moderate",
      quotes: [
        {
          text: "I expected a wizard flow",
          participant_id: "p1",
          session_id: "s1",
          start_seconds: 50.0,
          intensity: 2,
        },
      ],
    },
  ],
  section_matrix: {
    cells: {
      "Checkout|Pain points": { count: 5, weighted_count: 4.2, participants: { p1: 2, p2: 2, p3: 1 }, intensities: [3, 2, 2, 3, 1] },
      "Checkout|Mental models": { count: 1, weighted_count: 0.8, participants: { p1: 1 }, intensities: [2] },
      "Search|Pain points": { count: 1, weighted_count: 1.0, participants: { p2: 1 }, intensities: [1] },
      "Search|Mental models": { count: 0, weighted_count: 0, participants: {}, intensities: [] },
    },
    row_totals: { Checkout: 6, Search: 1 },
    col_totals: { "Pain points": 6, "Mental models": 1 },
    grand_total: 7,
    row_labels: ["Checkout", "Search"],
  },
  theme_matrix: {
    cells: {
      "Onboarding|Pain points": { count: 1, weighted_count: 1.0, participants: { p1: 1 }, intensities: [2] },
      "Onboarding|Mental models": { count: 3, weighted_count: 2.4, participants: { p1: 2, p3: 1 }, intensities: [2, 1, 2] },
    },
    row_totals: { Onboarding: 4 },
    col_totals: { "Pain points": 1, "Mental models": 3 },
    grand_total: 4,
    row_labels: ["Onboarding"],
  },
  total_participants: 4,
  columns: ["Pain points", "Mental models"],
  participant_ids: ["p1", "p2", "p3"],
  source_breakdown: { accepted: 3, pending: 4, total: 7 },
  trade_off_note: "Quotes tagged with codes from multiple groups...",
};

const mockSentimentData: SentimentAnalysisData = {
  signals: [
    {
      location: "Checkout",
      sourceType: "section",
      sentiment: "frustration",
      count: 4,
      participants: ["p1", "p2"],
      nEff: 1.9,
      meanIntensity: 2.5,
      concentration: 3.0,
      compositeSignal: 0.5123,
      confidence: "strong",
      quotes: [
        { text: "This is so frustrating", pid: "p1", sessionId: "s1", startSeconds: 100, intensity: 3 },
      ],
    },
  ],
  sectionMatrix: {
    cells: { "Checkout|frustration": { count: 4 } },
    rowTotals: { Checkout: 4 },
    colTotals: { frustration: 4 },
    grandTotal: 4,
    rowLabels: ["Checkout"],
  },
  themeMatrix: {
    cells: {},
    rowTotals: {},
    colTotals: {},
    grandTotal: 0,
    rowLabels: [],
  },
  totalParticipants: 4,
  sentiments: ["frustration"],
  participantIds: ["p1", "p2"],
};

const emptyTagData: TagAnalysisResponse = {
  signals: [],
  section_matrix: { cells: {}, row_totals: {}, col_totals: {}, grand_total: 0, row_labels: [] },
  theme_matrix: { cells: {}, row_totals: {}, col_totals: {}, grand_total: 0, row_labels: [] },
  total_participants: 0,
  columns: [],
  participant_ids: [],
  source_breakdown: { accepted: 0, pending: 0, total: 0 },
  trade_off_note: "",
};

// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------

let fetchMock: ReturnType<typeof vi.fn>;

beforeEach(() => {
  fetchMock = vi.fn();
  global.fetch = fetchMock;
  // Reset window globals
  (window as Record<string, unknown>).BRISTLENOSE_ANALYSIS = undefined;
  (window as Record<string, unknown>).BRISTLENOSE_API_BASE = "/api/projects/1";
});

afterEach(() => {
  vi.restoreAllMocks();
});

function mockFetchTagAnalysis(data: TagAnalysisResponse) {
  fetchMock.mockResolvedValue({
    ok: true,
    json: () => Promise.resolve(data),
  });
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("AnalysisPage", () => {
  it("renders tag signal cards when API returns data", async () => {
    mockFetchTagAnalysis(mockTagData);
    render(<AnalysisPage projectId="1" />);

    await waitFor(() => {
      expect(screen.getAllByTestId("bn-signal-card")).toHaveLength(2);
    });

    // "Checkout" appears in both signal card and heatmap
    expect(screen.getAllByText("Checkout").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("Pain points").length).toBeGreaterThanOrEqual(1);
  });

  it("shows source breakdown banner for pending tags", async () => {
    mockFetchTagAnalysis(mockTagData);
    render(<AnalysisPage projectId="1" />);

    await waitFor(() => {
      expect(screen.getByTestId("bn-source-banner")).toBeTruthy();
    });
    expect(screen.getByTestId("bn-source-banner").textContent).toContain("3 accepted");
    expect(screen.getByTestId("bn-source-banner").textContent).toContain("4 pending");
  });

  it("renders heatmap table", async () => {
    mockFetchTagAnalysis(mockTagData);
    render(<AnalysisPage projectId="1" />);

    await waitFor(() => {
      expect(screen.getAllByTestId("bn-heatmap").length).toBeGreaterThan(0);
    });
  });

  it("shows no-data message when API returns empty", async () => {
    mockFetchTagAnalysis(emptyTagData);
    render(<AnalysisPage projectId="1" />);

    await waitFor(() => {
      expect(screen.getByText(/no analysis data available/i)).toBeTruthy();
    }, { timeout: 3000 });
  });

  it("shows sentiment signals when baked data exists", async () => {
    (window as Record<string, unknown>).BRISTLENOSE_ANALYSIS = mockSentimentData;
    mockFetchTagAnalysis(emptyTagData);
    render(<AnalysisPage projectId="1" />);

    await waitFor(() => {
      expect(screen.getAllByTestId("bn-signal-card")).toHaveLength(1);
    });
    // "frustration" may appear in both signal card badge and heatmap
    expect(screen.getAllByText("frustration").length).toBeGreaterThanOrEqual(1);
  });

  it("shows toggle when both sentiment and tag data exist", async () => {
    (window as Record<string, unknown>).BRISTLENOSE_ANALYSIS = mockSentimentData;
    mockFetchTagAnalysis(mockTagData);
    render(<AnalysisPage projectId="1" />);

    await waitFor(() => {
      expect(screen.getByTestId("bn-analysis-toggle")).toBeTruthy();
    });
    expect(screen.getByText("Sentiment signals")).toBeTruthy();
    expect(screen.getByText("Tag signals")).toBeTruthy();
  });

  it("switches between views on toggle click", async () => {
    (window as Record<string, unknown>).BRISTLENOSE_ANALYSIS = mockSentimentData;
    mockFetchTagAnalysis(mockTagData);
    render(<AnalysisPage projectId="1" />);

    await waitFor(() => {
      expect(screen.getByTestId("bn-analysis-toggle")).toBeTruthy();
    });

    // Default is tags view — "Pain points" appears in card and heatmap
    await waitFor(() => {
      expect(screen.getAllByText("Pain points").length).toBeGreaterThanOrEqual(1);
    });

    // Click sentiment toggle
    fireEvent.click(screen.getByText("Sentiment signals"));

    await waitFor(() => {
      expect(screen.getAllByText("frustration").length).toBeGreaterThanOrEqual(1);
    });
  });

  it("expands signal card quotes on toggle click", async () => {
    mockFetchTagAnalysis(mockTagData);
    render(<AnalysisPage projectId="1" />);

    await waitFor(() => {
      expect(screen.getAllByTestId("bn-signal-card")).toHaveLength(2);
    });

    // First card has 2 quotes — 1 visible, 1 hidden
    const toggle = screen.getAllByTestId("bn-signal-toggle")[0];
    expect(toggle.textContent).toContain("Show all 2 quotes");
    fireEvent.click(toggle);
    expect(toggle.textContent).toContain("Hide");
  });

  it("does not show source banner when only sentiment data", async () => {
    (window as Record<string, unknown>).BRISTLENOSE_ANALYSIS = mockSentimentData;
    mockFetchTagAnalysis(emptyTagData);
    render(<AnalysisPage projectId="1" />);

    await waitFor(() => {
      expect(screen.getAllByTestId("bn-signal-card")).toHaveLength(1);
    });

    expect(screen.queryByTestId("bn-source-banner")).toBeNull();
  });

  it("renders metrics for each signal card", async () => {
    mockFetchTagAnalysis(mockTagData);
    render(<AnalysisPage projectId="1" />);

    await waitFor(() => {
      expect(screen.getAllByTestId("bn-signal-card")).toHaveLength(2);
    });

    // Should contain metric values from the first signal
    expect(screen.getByText("0.4567")).toBeTruthy(); // composite signal
    expect(screen.getByText("2.5×")).toBeTruthy();   // concentration
  });

  it("shows participant grid with presence indicators", async () => {
    mockFetchTagAnalysis(mockTagData);
    render(<AnalysisPage projectId="1" />);

    await waitFor(() => {
      expect(screen.getAllByTestId("bn-signal-card")).toHaveLength(2);
    });

    // Should show participant count
    const grids = document.querySelectorAll(".participant-grid");
    expect(grids.length).toBeGreaterThan(0);
  });
});
