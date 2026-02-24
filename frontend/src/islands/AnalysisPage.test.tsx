import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { AnalysisPage } from "./AnalysisPage";
import type { CodebookAnalysisListResponse, SentimentAnalysisData } from "../utils/types";

// ---------------------------------------------------------------------------
// Mock data — per-codebook shape
// ---------------------------------------------------------------------------

const mockCbData: CodebookAnalysisListResponse = {
  codebooks: [
    {
      codebook_id: "uxr",
      codebook_name: "UX Research",
      colour_set: "ux",
      signals: [
        {
          location: "Checkout",
          source_type: "section",
          group_name: "Pain points",
          colour_set: "ux",
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
              tag_names: ["Latency"],
              segment_index: 12,
            },
            {
              text: "I had to wait for ages",
              participant_id: "p2",
              session_id: "s1",
              start_seconds: 200.0,
              intensity: 2,
              tag_names: ["Latency"],
              segment_index: 20,
            },
          ],
        },
      ],
      section_matrix: {
        cells: {
          "Checkout|Pain points": { count: 5, weighted_count: 4.2, participants: { p1: 2, p2: 2, p3: 1 }, intensities: [3, 2, 2, 3, 1] },
          "Search|Pain points": { count: 1, weighted_count: 1.0, participants: { p2: 1 }, intensities: [1] },
        },
        row_totals: { Checkout: 5, Search: 1 },
        col_totals: { "Pain points": 6 },
        grand_total: 6,
        row_labels: ["Checkout", "Search"],
      },
      theme_matrix: {
        cells: {},
        row_totals: {},
        col_totals: {},
        grand_total: 0,
        row_labels: [],
      },
      columns: ["Pain points"],
      participant_ids: ["p1", "p2", "p3"],
      source_breakdown: { accepted: 3, pending: 2, total: 5 },
      tag_colour_indices: { Latency: 0, "Error messages": 1 },
    },
    {
      codebook_id: "norman",
      codebook_name: "Norman Usability",
      colour_set: "task",
      signals: [
        {
          location: "Onboarding",
          source_type: "theme",
          group_name: "Mental models",
          colour_set: "task",
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
              tag_names: ["Conceptual model"],
              segment_index: 5,
            },
          ],
        },
      ],
      section_matrix: {
        cells: {
          "Checkout|Mental models": { count: 1, weighted_count: 0.8, participants: { p1: 1 }, intensities: [2] },
        },
        row_totals: { Checkout: 1 },
        col_totals: { "Mental models": 1 },
        grand_total: 1,
        row_labels: ["Checkout"],
      },
      theme_matrix: {
        cells: {
          "Onboarding|Mental models": { count: 3, weighted_count: 2.4, participants: { p1: 2, p3: 1 }, intensities: [2, 1, 2] },
        },
        row_totals: { Onboarding: 3 },
        col_totals: { "Mental models": 3 },
        grand_total: 3,
        row_labels: ["Onboarding"],
      },
      columns: ["Mental models"],
      participant_ids: ["p1", "p3"],
      source_breakdown: { accepted: 1, pending: 2, total: 3 },
      tag_colour_indices: { "Conceptual model": 0 },
    },
  ],
  total_participants: 4,
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
        { text: "This is so frustrating", pid: "p1", sessionId: "s1", startSeconds: 100, intensity: 3, segmentIndex: 10 },
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

const emptyCbData: CodebookAnalysisListResponse = {
  codebooks: [],
  total_participants: 0,
  trade_off_note: "",
};

// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------

let fetchMock: ReturnType<typeof vi.fn>;

beforeEach(() => {
  fetchMock = vi.fn();
  globalThis.fetch = fetchMock;
  // Reset window globals
  (window as unknown as Record<string, unknown>).BRISTLENOSE_ANALYSIS = undefined;
  (window as unknown as Record<string, unknown>).BRISTLENOSE_API_BASE = "/api/projects/1";
});

afterEach(() => {
  vi.restoreAllMocks();
});

function mockFetchCodebookAnalysis(data: CodebookAnalysisListResponse) {
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
    mockFetchCodebookAnalysis(mockCbData);
    render(<AnalysisPage projectId="1" />);

    await waitFor(() => {
      expect(screen.getAllByTestId("bn-signal-card")).toHaveLength(2);
    });

    expect(screen.getAllByText("Checkout").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("Pain points").length).toBeGreaterThanOrEqual(1);
  });

  it("shows source breakdown banner for pending tags", async () => {
    mockFetchCodebookAnalysis(mockCbData);
    render(<AnalysisPage projectId="1" />);

    await waitFor(() => {
      expect(screen.getByTestId("bn-source-banner")).toBeTruthy();
    });
    // Aggregated: 3+1=4 accepted, 2+2=4 pending
    expect(screen.getByTestId("bn-source-banner").textContent).toContain("4 accepted");
    expect(screen.getByTestId("bn-source-banner").textContent).toContain("4 pending");
  });

  it("renders heatmap table", async () => {
    mockFetchCodebookAnalysis(mockCbData);
    render(<AnalysisPage projectId="1" />);

    await waitFor(() => {
      expect(screen.getAllByTestId("bn-heatmap").length).toBeGreaterThan(0);
    });
  });

  it("shows no-data message when API returns empty", async () => {
    mockFetchCodebookAnalysis(emptyCbData);
    render(<AnalysisPage projectId="1" />);

    await waitFor(() => {
      expect(screen.getByText(/no analysis data available/i)).toBeTruthy();
    }, { timeout: 3000 });
  });

  it("shows sentiment signals when baked data exists", async () => {
    (window as unknown as Record<string, unknown>).BRISTLENOSE_ANALYSIS = mockSentimentData;
    mockFetchCodebookAnalysis(emptyCbData);
    render(<AnalysisPage projectId="1" />);

    await waitFor(() => {
      expect(screen.getAllByTestId("bn-signal-card")).toHaveLength(1);
    });
    expect(screen.getAllByText("frustration").length).toBeGreaterThanOrEqual(1);
  });

  it("shows both sentiment and tag cards when both data exist", async () => {
    (window as unknown as Record<string, unknown>).BRISTLENOSE_ANALYSIS = mockSentimentData;
    mockFetchCodebookAnalysis(mockCbData);
    render(<AnalysisPage projectId="1" />);

    await waitFor(() => {
      // 1 sentiment + 2 tag = 3 cards total
      expect(screen.getAllByTestId("bn-signal-card")).toHaveLength(3);
    });

    // Both types visible simultaneously — no toggle needed
    expect(screen.getAllByText("frustration").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("Pain points").length).toBeGreaterThanOrEqual(1);
  });

  it("shows separate headings for sentiment and tag signals", async () => {
    (window as unknown as Record<string, unknown>).BRISTLENOSE_ANALYSIS = mockSentimentData;
    mockFetchCodebookAnalysis(mockCbData);
    render(<AnalysisPage projectId="1" />);

    await waitFor(() => {
      expect(screen.getAllByTestId("bn-signal-card")).toHaveLength(3);
    });

    expect(screen.getByText("Sentiment signals")).toBeTruthy();
    expect(screen.getByText("Tag signals")).toBeTruthy();
  });

  it("expands signal card quotes on toggle click", async () => {
    mockFetchCodebookAnalysis(mockCbData);
    render(<AnalysisPage projectId="1" />);

    await waitFor(() => {
      expect(screen.getAllByTestId("bn-signal-card")).toHaveLength(2);
    });

    // First card (Checkout/Pain points) has 2 quotes — 1 visible, 1 hidden
    const toggle = screen.getAllByTestId("bn-signal-toggle")[0];
    expect(toggle.textContent).toContain("Show all 2 quotes");
    fireEvent.click(toggle);
    expect(toggle.textContent).toContain("Hide");
  });

  it("does not show source banner when only sentiment data", async () => {
    (window as unknown as Record<string, unknown>).BRISTLENOSE_ANALYSIS = mockSentimentData;
    mockFetchCodebookAnalysis(emptyCbData);
    render(<AnalysisPage projectId="1" />);

    await waitFor(() => {
      expect(screen.getAllByTestId("bn-signal-card")).toHaveLength(1);
    });

    expect(screen.queryByTestId("bn-source-banner")).toBeNull();
  });

  it("renders metrics for each signal card", async () => {
    mockFetchCodebookAnalysis(mockCbData);
    render(<AnalysisPage projectId="1" />);

    await waitFor(() => {
      expect(screen.getAllByTestId("bn-signal-card")).toHaveLength(2);
    });

    expect(screen.getByText("0.46")).toBeTruthy(); // composite signal
    expect(screen.getByText("2.5×")).toBeTruthy();   // concentration
  });

  it("shows participant grid with presence indicators", async () => {
    mockFetchCodebookAnalysis(mockCbData);
    render(<AnalysisPage projectId="1" />);

    await waitFor(() => {
      expect(screen.getAllByTestId("bn-signal-card")).toHaveLength(2);
    });

    const grids = document.querySelectorAll(".participant-grid");
    expect(grids.length).toBeGreaterThan(0);
  });

  // --- Per-codebook features ---

  it("renders separate heatmaps per codebook", async () => {
    mockFetchCodebookAnalysis(mockCbData);
    render(<AnalysisPage projectId="1" />);

    await waitFor(() => {
      expect(screen.getAllByTestId("bn-signal-card")).toHaveLength(2);
    });

    expect(screen.getByText("UX Research")).toBeTruthy();
    expect(screen.getByText("Norman Usability")).toBeTruthy();

    const codebookSections = document.querySelectorAll(".analysis-codebook-section");
    expect(codebookSections.length).toBe(2);
  });

  it("signals are interleaved across codebooks by composite score", async () => {
    mockFetchCodebookAnalysis(mockCbData);
    render(<AnalysisPage projectId="1" />);

    await waitFor(() => {
      expect(screen.getAllByTestId("bn-signal-card")).toHaveLength(2);
    });

    const cards = screen.getAllByTestId("bn-signal-card");
    expect(cards[0].textContent).toContain("Pain points");
    expect(cards[1].textContent).toContain("Mental models");
  });

  it("renders PersonBadge in quote blocks", async () => {
    mockFetchCodebookAnalysis(mockCbData);
    render(<AnalysisPage projectId="1" />);

    await waitFor(() => {
      expect(screen.getAllByTestId("bn-signal-card")).toHaveLength(2);
    });

    const badges = document.querySelectorAll(".bn-person-badge");
    expect(badges.length).toBeGreaterThan(0);
  });

  it("renders per-quote tag badges", async () => {
    mockFetchCodebookAnalysis(mockCbData);
    render(<AnalysisPage projectId="1" />);

    await waitFor(() => {
      expect(screen.getAllByTestId("bn-signal-card")).toHaveLength(2);
    });

    const tagBadges = document.querySelectorAll(".signal-quote-tag");
    expect(tagBadges.length).toBeGreaterThan(0);
    expect(screen.getAllByText("Latency").length).toBeGreaterThanOrEqual(1);
  });

  it("renders group heading badge with colour", async () => {
    mockFetchCodebookAnalysis(mockCbData);
    render(<AnalysisPage projectId="1" />);

    await waitFor(() => {
      expect(screen.getAllByTestId("bn-signal-card")).toHaveLength(2);
    });

    const groupBadges = document.querySelectorAll(".signal-group-badge");
    expect(groupBadges.length).toBe(2);
  });

  it("heatmap has rotated column headers for tag mode", async () => {
    mockFetchCodebookAnalysis(mockCbData);
    render(<AnalysisPage projectId="1" />);

    await waitFor(() => {
      expect(screen.getAllByTestId("bn-heatmap").length).toBeGreaterThan(0);
    });

    const rotatedHeaders = document.querySelectorAll(".heatmap-col-header");
    expect(rotatedHeaders.length).toBeGreaterThan(0);

    const rotatedLabels = document.querySelectorAll(".heatmap-col-label");
    expect(rotatedLabels.length).toBeGreaterThan(0);
  });

  it("expansion toggle reveals hidden quotes", async () => {
    mockFetchCodebookAnalysis(mockCbData);
    render(<AnalysisPage projectId="1" />);

    await waitFor(() => {
      expect(screen.getAllByTestId("bn-signal-card")).toHaveLength(2);
    });

    const card = screen.getAllByTestId("bn-signal-card")[0];
    const expansion = card.querySelector(".signal-card-expansion") as HTMLElement;
    expect(expansion).toBeTruthy();
    expect(expansion.style.maxHeight).toBe("0");

    const toggle = screen.getAllByTestId("bn-signal-toggle")[0];
    fireEvent.click(toggle);

    expect(card.classList.contains("expanded")).toBe(true);
  });

  // --- Quote sequence rendering ---

  it("suppresses PersonBadge on continuation quotes in a sequence", async () => {
    // Build mock data with 3 quotes from same pid/session within threshold
    const seqCbData: CodebookAnalysisListResponse = {
      codebooks: [{
        codebook_id: "seq-test",
        codebook_name: "Sequence Test",
        colour_set: "ux",
        signals: [{
          location: "Onboarding",
          source_type: "section",
          group_name: "Pain points",
          colour_set: "ux",
          count: 3,
          participants: ["p1"],
          n_eff: 1.0,
          mean_intensity: 2.0,
          concentration: 2.0,
          composite_signal: 0.5,
          confidence: "strong",
          quotes: [
            { text: "First thing I noticed", participant_id: "p1", session_id: "s1", start_seconds: 12, intensity: 2, tag_names: [], segment_index: 0 },
            { text: "And then it got worse", participant_id: "p1", session_id: "s1", start_seconds: 19, intensity: 2, tag_names: [], segment_index: 1 },
            { text: "But eventually it worked", participant_id: "p1", session_id: "s1", start_seconds: 31, intensity: 1, tag_names: [], segment_index: 3 },
          ],
        }],
        section_matrix: { cells: {}, row_totals: {}, col_totals: {}, grand_total: 0, row_labels: [] },
        theme_matrix: { cells: {}, row_totals: {}, col_totals: {}, grand_total: 0, row_labels: [] },
        columns: ["Pain points"],
        participant_ids: ["p1"],
        source_breakdown: { accepted: 3, pending: 0, total: 3 },
        tag_colour_indices: {},
      }],
      total_participants: 1,
      trade_off_note: "",
    };
    mockFetchCodebookAnalysis(seqCbData);
    render(<AnalysisPage projectId="1" />);

    await waitFor(() => {
      expect(screen.getAllByTestId("bn-signal-card")).toHaveLength(1);
    });

    // Expand to see all quotes
    const toggle = screen.getByTestId("bn-signal-toggle");
    fireEvent.click(toggle);

    const card = screen.getAllByTestId("bn-signal-card")[0];
    const blockquotes = card.querySelectorAll("blockquote");
    expect(blockquotes.length).toBe(3);

    // First quote (seq-first) should have a PersonBadge
    expect(blockquotes[0].querySelector(".bn-person-badge")).toBeTruthy();
    // Continuation quotes (seq-middle, seq-last) should NOT
    expect(blockquotes[1].querySelector(".bn-person-badge")).toBeNull();
    expect(blockquotes[2].querySelector(".bn-person-badge")).toBeNull();
  });

  it("applies seq-first/middle/last classes to sequence blockquotes", async () => {
    const seqCbData: CodebookAnalysisListResponse = {
      codebooks: [{
        codebook_id: "seq-test",
        codebook_name: "Sequence Test",
        colour_set: "ux",
        signals: [{
          location: "Onboarding",
          source_type: "section",
          group_name: "Flow",
          colour_set: "ux",
          count: 3,
          participants: ["p1"],
          n_eff: 1.0,
          mean_intensity: 2.0,
          concentration: 2.0,
          composite_signal: 0.5,
          confidence: "strong",
          quotes: [
            { text: "Quote A", participant_id: "p1", session_id: "s1", start_seconds: 10, intensity: 2, tag_names: [], segment_index: 0 },
            { text: "Quote B", participant_id: "p1", session_id: "s1", start_seconds: 20, intensity: 2, tag_names: [], segment_index: 1 },
            { text: "Quote C", participant_id: "p1", session_id: "s1", start_seconds: 30, intensity: 2, tag_names: [], segment_index: 2 },
          ],
        }],
        section_matrix: { cells: {}, row_totals: {}, col_totals: {}, grand_total: 0, row_labels: [] },
        theme_matrix: { cells: {}, row_totals: {}, col_totals: {}, grand_total: 0, row_labels: [] },
        columns: ["Flow"],
        participant_ids: ["p1"],
        source_breakdown: { accepted: 3, pending: 0, total: 3 },
        tag_colour_indices: {},
      }],
      total_participants: 1,
      trade_off_note: "",
    };
    mockFetchCodebookAnalysis(seqCbData);
    render(<AnalysisPage projectId="1" />);

    await waitFor(() => {
      expect(screen.getAllByTestId("bn-signal-card")).toHaveLength(1);
    });

    const toggle = screen.getByTestId("bn-signal-toggle");
    fireEvent.click(toggle);

    const card = screen.getAllByTestId("bn-signal-card")[0];
    const blockquotes = card.querySelectorAll("blockquote");
    expect(blockquotes[0].classList.contains("seq-first")).toBe(true);
    expect(blockquotes[1].classList.contains("seq-middle")).toBe(true);
    expect(blockquotes[2].classList.contains("seq-last")).toBe(true);
  });

  it("does not apply seq-* classes to solo quotes", async () => {
    // Use existing mockCbData — quotes from different pids, won't form sequences
    mockFetchCodebookAnalysis(mockCbData);
    render(<AnalysisPage projectId="1" />);

    await waitFor(() => {
      expect(screen.getAllByTestId("bn-signal-card")).toHaveLength(2);
    });

    // Expand first card to see both quotes
    const toggle = screen.getAllByTestId("bn-signal-toggle")[0];
    fireEvent.click(toggle);

    const card = screen.getAllByTestId("bn-signal-card")[0];
    const blockquotes = card.querySelectorAll("blockquote");
    for (const bq of blockquotes) {
      expect(bq.classList.contains("seq-first")).toBe(false);
      expect(bq.classList.contains("seq-middle")).toBe(false);
      expect(bq.classList.contains("seq-last")).toBe(false);
    }
  });

  it("does not form sequences from zero-timecode quotes", async () => {
    const zeroCbData: CodebookAnalysisListResponse = {
      codebooks: [{
        codebook_id: "zero-test",
        codebook_name: "Zero TC Test",
        colour_set: "ux",
        signals: [{
          location: "Section",
          source_type: "section",
          group_name: "Group",
          colour_set: "ux",
          count: 2,
          participants: ["p1"],
          n_eff: 1.0,
          mean_intensity: 1.0,
          concentration: 1.5,
          composite_signal: 0.3,
          confidence: "moderate",
          quotes: [
            { text: "No timecode A", participant_id: "p1", session_id: "s1", start_seconds: 0, intensity: 1, tag_names: [], segment_index: 0 },
            { text: "No timecode B", participant_id: "p1", session_id: "s1", start_seconds: 0, intensity: 1, tag_names: [], segment_index: 1 },
          ],
        }],
        section_matrix: { cells: {}, row_totals: {}, col_totals: {}, grand_total: 0, row_labels: [] },
        theme_matrix: { cells: {}, row_totals: {}, col_totals: {}, grand_total: 0, row_labels: [] },
        columns: ["Group"],
        participant_ids: ["p1"],
        source_breakdown: { accepted: 2, pending: 0, total: 2 },
        tag_colour_indices: {},
      }],
      total_participants: 1,
      trade_off_note: "",
    };
    mockFetchCodebookAnalysis(zeroCbData);
    render(<AnalysisPage projectId="1" />);

    await waitFor(() => {
      expect(screen.getAllByTestId("bn-signal-card")).toHaveLength(1);
    });

    const toggle = screen.getByTestId("bn-signal-toggle");
    fireEvent.click(toggle);

    const card = screen.getAllByTestId("bn-signal-card")[0];
    const blockquotes = card.querySelectorAll("blockquote");
    // Both should be solo — PersonBadge on both
    for (const bq of blockquotes) {
      expect(bq.querySelector(".bn-person-badge")).toBeTruthy();
      expect(bq.classList.contains("seq-first")).toBe(false);
    }
  });

  it("heatmap cells with count=1 get data-count attribute", async () => {
    mockFetchCodebookAnalysis(mockCbData);
    render(<AnalysisPage projectId="1" />);

    await waitFor(() => {
      expect(screen.getAllByTestId("bn-heatmap").length).toBeGreaterThan(0);
    });

    // "Search|Pain points" has count=1 in the UXR section matrix
    const cells = document.querySelectorAll('.heatmap-cell[data-count="1"]');
    expect(cells.length).toBeGreaterThan(0);
  });
});
