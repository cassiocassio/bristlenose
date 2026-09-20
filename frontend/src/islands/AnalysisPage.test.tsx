import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { AnalysisPage } from "./AnalysisPage";
import type { CodebookAnalysisListResponse, SentimentAnalysisData } from "../utils/types";
import { resetAnalysisSignalStore } from "../contexts/AnalysisSignalStore";

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
            // Five quotes so four are visible and one is hidden — the toggle
            // has nothing to reveal below the cap, and two tests here are
            // about the toggle.
            {
              text: "It spun for a long time",
              participant_id: "p3",
              session_id: "s2",
              start_seconds: 300.0,
              intensity: 2,
              tag_names: ["Latency"],
              segment_index: 30,
            },
            {
              text: "I nearly gave up waiting",
              participant_id: "p4",
              session_id: "s2",
              start_seconds: 400.0,
              intensity: 3,
              tag_names: ["Latency"],
              segment_index: 40,
            },
            {
              text: "Eventually it came back",
              participant_id: "p5",
              session_id: "s3",
              start_seconds: 500.0,
              intensity: 1,
              tag_names: ["Latency"],
              segment_index: 50,
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

// eslint-disable-next-line @typescript-eslint/no-explicit-any
let fetchMock: any;

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
    expect(screen.getAllByText("Frustration").length).toBeGreaterThanOrEqual(1);
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
    expect(screen.getAllByText("Frustration").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("Pain points").length).toBeGreaterThanOrEqual(1);
  });

  it("groups cards by location instead of by kind", async () => {
    (window as unknown as Record<string, unknown>).BRISTLENOSE_ANALYSIS = mockSentimentData;
    mockFetchCodebookAnalysis(mockCbData);
    render(<AnalysisPage projectId="1" />);

    await waitFor(() => {
      expect(screen.getAllByTestId("bn-signal-card")).toHaveLength(3);
    });

    // The two kind-split headings are gone. A place appeared in both halves
    // and nowhere as itself; it is a heading of its own now.
    expect(screen.queryByText("Sentiment signals")).toBeNull();
    expect(screen.queryByText("Tag signals")).toBeNull();

    const headings = [...document.querySelectorAll(".analysis-codebook-heading")]
      .map((n) => n.textContent);
    expect(headings.length).toBeGreaterThan(0);
    expect(headings).toContain("Checkout");
    // Every card sits under one of those headings.
    expect(document.querySelectorAll(".signal-cards").length).toBe(headings.length);
  });

  // The flush-to-datum contract, cheap. e2e/tests/lens-datum.spec.ts is the
  // real gate, but it needs a server; this catches the enrolment breaking at
  // the moment someone edits the render. The refactor that grouped cards by
  // location removed the lens's only .section-heading and took the datum with
  // it — no unit test could see the CSS selector stop matching, so this asserts
  // the shape the selector needs instead.
  it("keeps the lens enrolled in the flush-to-datum system", async () => {
    mockFetchCodebookAnalysis(mockCbData);
    render(<AnalysisPage projectId="1" />);

    await waitFor(() => {
      expect(screen.getAllByTestId("bn-signal-card").length).toBeGreaterThan(0);
    });

    const pane = document.querySelector(".analysis-center");
    expect(pane).toBeTruthy();
    // `.analysis-center > .section-heading:first-of-type { margin-top: 0 }`
    expect(pane!.querySelector(":scope > .section-heading")).toBeTruthy();
    expect(pane!.firstElementChild!.classList.contains("section-heading")).toBe(true);
  });

  it("the sidebar list and the rendered cards are the same set", async () => {
    // The 1:1 invariant: every nav row lands on a card, and no card is
    // unreachable. It used to hold by ACCIDENT — MAX_SIGNALS sliced one list
    // that both surfaces read. De-duplication runs once, over the merged list,
    // and both read its output, so they cannot drift apart.
    (window as unknown as Record<string, unknown>).BRISTLENOSE_ANALYSIS = mockSentimentData;
    mockFetchCodebookAnalysis(mockCbData);
    render(<AnalysisPage projectId="1" />);

    await waitFor(() => {
      expect(screen.getAllByTestId("bn-signal-card").length).toBeGreaterThan(0);
    });

    const { renderHook } = await import("@testing-library/react");
    const { useAnalysisSignalStore } = await import("../contexts/AnalysisSignalStore");
    const { result } = renderHook(() => useAnalysisSignalStore());
    expect(result.current.signals.length)
      .toBe(screen.getAllByTestId("bn-signal-card").length);
  });

  it("no longer renders the pattern chip, though the pattern still arrives", async () => {
    const named: CodebookAnalysisListResponse = JSON.parse(JSON.stringify(mockCbData));
    named.codebooks[0].signals[0].signal_name = "Checkout Latency Tension";
    named.codebooks[0].signals[0].pattern = "tension";
    mockFetchCodebookAnalysis(named);
    render(<AnalysisPage projectId="1" />);

    await waitFor(() => {
      expect(screen.getByText("Checkout Latency Tension")).toBeTruthy();
    });
    expect(screen.queryByTestId("pattern-badge")).toBeNull();
    expect(screen.queryByText("TENSION")).toBeNull();
  });

  it("expands signal card quotes on toggle click", async () => {
    mockFetchCodebookAnalysis(mockCbData);
    render(<AnalysisPage projectId="1" />);

    await waitFor(() => {
      expect(screen.getAllByTestId("bn-signal-card")).toHaveLength(2);
    });

    // First card (Checkout/Pain points) has 5 quotes — 4 visible, 1 hidden
    const toggle = screen.getAllByTestId("bn-signal-toggle")[0];
    expect(toggle.textContent).toContain("Show all 5 quotes");
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

  it("shows the score on the hero chip and hides the working behind it", async () => {
    mockFetchCodebookAnalysis(mockCbData);
    render(<AnalysisPage projectId="1" />);

    await waitFor(() => {
      expect(screen.getAllByTestId("bn-signal-card")).toHaveLength(2);
    });

    // One number, on the chip. Measured across a trial project's 24 signals,
    // Agreement takes 3 distinct values and Intensity 4 — captions, not
    // columns — so the rest is for whoever wants to audit it.
    expect(screen.getAllByTestId("bn-signal-hero")[0].textContent).toContain("0.46");
    expect(screen.queryByText("2.5×")).toBeNull();
    expect(screen.queryAllByTestId("bn-signal-working")).toHaveLength(0);
  });

  it("the hero chip opens and closes the working", async () => {
    mockFetchCodebookAnalysis(mockCbData);
    render(<AnalysisPage projectId="1" />);

    await waitFor(() => {
      expect(screen.getAllByTestId("bn-signal-card")).toHaveLength(2);
    });

    const hero = screen.getAllByTestId("bn-signal-hero")[0];
    expect(hero.getAttribute("aria-expanded")).toBe("false");

    fireEvent.click(hero);
    expect(hero.getAttribute("aria-expanded")).toBe("true");
    expect(screen.getByText("2.5×")).toBeTruthy();   // concentration

    fireEvent.click(hero);
    expect(hero.getAttribute("aria-expanded")).toBe("false");
    expect(screen.queryByText("2.5×")).toBeNull();
  });

  it("opening the working does not also focus the card", async () => {
    // The card is role="button" and focuses on click, so the chip must stop
    // the event — pressing a disclosure should not re-point the inspector.
    resetAnalysisSignalStore();
    mockFetchCodebookAnalysis(mockCbData);
    render(<AnalysisPage projectId="1" />);

    await waitFor(() => {
      expect(screen.getAllByTestId("bn-signal-card")).toHaveLength(2);
    });

    const card = screen.getAllByTestId("bn-signal-card")[0];
    expect(card.classList.contains("bn-selected")).toBe(false);
    fireEvent.click(screen.getAllByTestId("bn-signal-hero")[0]);
    expect(card.classList.contains("bn-selected")).toBe(false);
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

  it("renders per-codebook tabs in inspector panel", async () => {
    mockFetchCodebookAnalysis(mockCbData);
    render(<AnalysisPage projectId="1" />);

    await waitFor(() => {
      expect(screen.getAllByTestId("bn-signal-card")).toHaveLength(2);
    });

    // Codebook names appear as inspector panel tabs
    expect(screen.getByTestId("inspector-tab-cb-uxr")).toBeTruthy();
    expect(screen.getByTestId("inspector-tab-cb-norman")).toBeTruthy();
    expect(screen.getByTestId("inspector-tab-cb-uxr").textContent).toBe("UX Research");
    expect(screen.getByTestId("inspector-tab-cb-norman").textContent).toBe("Norman Usability");
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

  it("the hero carries the group name and its colour", async () => {
    // The group badge used to sit in the card's identity column (nameless
    // card) or in a badge stack above the metrics (elaborated card). It is the
    // hero's own label now — the two card kinds are the same card, and the
    // only thing that differs is whether the hero names a sentiment or a group.
    mockFetchCodebookAnalysis(mockCbData);
    render(<AnalysisPage projectId="1" />);

    await waitFor(() => {
      expect(screen.getAllByTestId("bn-signal-card")).toHaveLength(2);
    });

    expect(document.querySelectorAll(".signal-group-badge").length).toBe(0);
    const heroes = screen.getAllByTestId("bn-signal-hero");
    expect(heroes.length).toBe(2);
    const tagHero = heroes.find((h) => h.textContent?.includes("Pain points"));
    expect(tagHero).toBeTruthy();
    expect(tagHero!.getAttribute("style")).toContain("background-color");
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
    expect(expansion.style.maxHeight).toMatch(/^0(px)?$/);

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

    const card = screen.getAllByTestId("bn-signal-card")[0];
    const blockquotes = card.querySelectorAll("blockquote");
    // Both should be solo — PersonBadge on both
    for (const bq of blockquotes) {
      expect(bq.querySelector(".bn-person-badge")).toBeTruthy();
      expect(bq.classList.contains("seq-first")).toBe(false);
    }
  });

  it("Cmd+click on a location heading does not call switchToTab", async () => {
    mockFetchCodebookAnalysis(mockCbData);
    (window as unknown as Record<string, unknown>).switchToTab = vi.fn();
    render(<AnalysisPage projectId="1" />);

    await waitFor(() => {
      expect(screen.getAllByTestId("bn-signal-card")).toHaveLength(2);
    });

    const link = document
      .querySelector(".analysis-codebook-heading a.signal-card-location-link") as HTMLElement;
    expect(link).toBeTruthy();

    // Cmd+click (Mac) — should NOT intercept
    fireEvent.click(link, { metaKey: true });
    expect(window.switchToTab).not.toHaveBeenCalled();

    // Ctrl+click (Win/Linux) — should NOT intercept
    fireEvent.click(link, { ctrlKey: true });
    expect(window.switchToTab).not.toHaveBeenCalled();

    // Plain click — should intercept
    fireEvent.click(link);
    expect(window.switchToTab).toHaveBeenCalledWith("quotes");
  });

  // An ELABORATED card renders a different header from a nameless one: the
  // headline is the signal's own name and the location moves to the source
  // line above it. That branch had no location link at all, so the card that
  // tells the researcher most was the one that could not hand them the quotes
  // — and no fixture in this file carried a signal_name, which is why nothing
  // caught it.
  it("a location's heading is the link to the quotes lens, and the card carries none", async () => {
    mockFetchCodebookAnalysis(mockCbData);
    (window as unknown as Record<string, unknown>).switchToTab = vi.fn();
    (window as unknown as Record<string, unknown>).scrollToAnchor = vi.fn();
    render(<AnalysisPage projectId="1" />);

    await waitFor(() => {
      expect(screen.getAllByTestId("bn-signal-card").length).toBeGreaterThan(0);
    });

    // The link lives on the heading, once per location — not once per card.
    const heading = document.querySelector(".analysis-codebook-heading") as HTMLElement;
    const link = heading.querySelector("a.signal-card-location-link") as HTMLElement;
    expect(link).toBeTruthy();
    expect(link.textContent).toBe("Checkout");

    // And no card repeats it. The location is stated once, above the run.
    for (const card of screen.getAllByTestId("bn-signal-card")) {
      expect(card.querySelector("a.signal-card-location-link")).toBeNull();
    }

    fireEvent.click(link);
    expect(window.switchToTab).toHaveBeenCalledWith("quotes");
    expect(window.scrollToAnchor).toHaveBeenCalledWith("section-checkout");
  });

  // The card is itself role="button" and focuses on click, so a link inside it
  // must stop the event: otherwise following the location to the quotes lens
  // also re-focuses the card and re-points the inspector behind your back.
  it("the location link is outside every card, so following it cannot focus one", async () => {
    // This replaces a test that pinned a stopPropagation on the card's own
    // location link: the whole card is role="button", so clicking the link
    // fired BOTH — you landed in the quotes lens and the analysis lens had
    // silently re-focused the card behind you. The link now lives on the
    // heading, outside every card, so the hazard is structural rather than
    // guarded. This asserts the structure that makes it impossible.
    resetAnalysisSignalStore();   // module singleton — an earlier test's focus leaks in
    mockFetchCodebookAnalysis(mockCbData);
    (window as unknown as Record<string, unknown>).switchToTab = vi.fn();
    (window as unknown as Record<string, unknown>).scrollToAnchor = vi.fn();
    render(<AnalysisPage projectId="1" />);

    await waitFor(() => {
      expect(screen.getAllByTestId("bn-signal-card")).toHaveLength(2);
    });

    const link = document
      .querySelector(".analysis-codebook-heading a.signal-card-location-link") as HTMLElement;
    for (const card of screen.getAllByTestId("bn-signal-card")) {
      expect(card.contains(link)).toBe(false);
    }

    fireEvent.click(link);
    await waitFor(() => {
      expect(window.switchToTab).toHaveBeenCalledWith("quotes");
    });
    for (const card of screen.getAllByTestId("bn-signal-card")) {
      expect(card.classList.contains("bn-selected")).toBe(false);
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

  // -------------------------------------------------------------------------
  // Heatmap dark mode
  //
  // The desktop app never writes `data-theme` — appearance is owned natively
  // and the webview follows `prefers-color-scheme` — so reading the attribute
  // alone pinned every embedded report to the light lightness band.
  // -------------------------------------------------------------------------

  describe("heatmap dark mode", () => {
    // A 2×2 matrix. The shared fixtures above are single-column, which makes
    // every adjusted residual zero, so not one of their cells gets a colour.
    const contrastCbData: CodebookAnalysisListResponse = {
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
              count: 8,
              participants: ["p1", "p2"],
              n_eff: 1.9,
              mean_intensity: 2.0,
              concentration: 2.0,
              composite_signal: 0.5,
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
              ],
            },
          ],
          section_matrix: {
            cells: {
              "Checkout|Pain points": { count: 8, weighted_count: 8, participants: { p1: 4, p2: 4 }, intensities: [2] },
              "Checkout|Praise": { count: 1, weighted_count: 1, participants: { p1: 1 }, intensities: [1] },
              "Search|Pain points": { count: 1, weighted_count: 1, participants: { p2: 1 }, intensities: [1] },
              "Search|Praise": { count: 8, weighted_count: 8, participants: { p1: 4, p2: 4 }, intensities: [2] },
            },
            row_totals: { Checkout: 9, Search: 9 },
            col_totals: { "Pain points": 9, Praise: 9 },
            grand_total: 18,
            row_labels: ["Checkout", "Search"],
          },
          theme_matrix: {
            cells: {},
            row_totals: {},
            col_totals: {},
            grand_total: 0,
            row_labels: [],
          },
          columns: ["Pain points", "Praise"],
          participant_ids: ["p1", "p2"],
          source_breakdown: { accepted: 18, pending: 0, total: 18 },
          tag_colour_indices: { Latency: 0 },
        },
      ],
      total_participants: 2,
      trade_off_note: "",
    };

    // jsdom ships no matchMedia at all, so each test installs one.
    function installMatchMedia(matches: boolean) {
      Object.defineProperty(window, "matchMedia", {
        configurable: true,
        writable: true,
        value: vi.fn((query: string) => ({
          matches,
          media: query,
          addEventListener: vi.fn(),
          removeEventListener: vi.fn(),
          dispatchEvent: vi.fn(),
        })),
      });
    }

    afterEach(() => {
      delete (window as unknown as Record<string, unknown>).matchMedia;
      document.documentElement.removeAttribute("data-theme");
    });

    /** Render, then read the OKLCH lightness off the first coloured cell. */
    async function renderAndReadLightness(): Promise<number> {
      mockFetchCodebookAnalysis(contrastCbData);
      render(<AnalysisPage projectId="1" />);
      await waitFor(() => {
        expect(screen.getAllByTestId("bn-heatmap").length).toBeGreaterThan(0);
      });
      const cell = Array.from(
        document.querySelectorAll<HTMLElement>(".heatmap-cell"),
      ).find((el) => el.style.background.startsWith("oklch("));
      expect(cell).toBeTruthy();
      return parseFloat(cell!.style.background.slice("oklch(".length));
    }

    // The bands are dark [0.25, 0.55] and light [0.55, 0.95]; this fixture's
    // strongest cell lands at ~0.30 dark and ~0.62 light.
    const BAND_EDGE = 0.55;

    it("uses the dark band when the OS is dark and nothing is forced", async () => {
      installMatchMedia(true);
      expect(await renderAndReadLightness()).toBeLessThan(BAND_EDGE);
    });

    it("uses the light band when the OS is light and nothing is forced", async () => {
      installMatchMedia(false);
      expect(await renderAndReadLightness()).toBeGreaterThan(BAND_EDGE);
    });

    it("honours a forced data-theme=light over a dark OS", async () => {
      installMatchMedia(true);
      document.documentElement.setAttribute("data-theme", "light");
      expect(await renderAndReadLightness()).toBeGreaterThan(BAND_EDGE);
    });

    it("honours a forced data-theme=dark over a light OS", async () => {
      installMatchMedia(false);
      document.documentElement.setAttribute("data-theme", "dark");
      expect(await renderAndReadLightness()).toBeLessThan(BAND_EDGE);
    });
  });

  it("NEVER puts the location in a card's headline", async () => {
    // The location is the heading directly above the run, and it is the one
    // string that is definitionally not a finding. The first build of this
    // change fell back to it when no name had been generated — and because the
    // lens fetches twice, that was EVERY card for the first few seconds.
    mockFetchCodebookAnalysis(mockCbData);   // no elaborations in this fixture
    render(<AnalysisPage projectId="1" />);

    await waitFor(() => {
      expect(screen.getAllByTestId("bn-signal-card").length).toBeGreaterThan(0);
    });

    const heading = document.querySelector(".analysis-codebook-heading") as HTMLElement;
    const location = heading.textContent?.trim();
    expect(location).toBeTruthy();

    for (const card of screen.getAllByTestId("bn-signal-card")) {
      const headline = card.querySelector(".signal-card-location");
      // Either absent, or a skeleton, or a real finding — never the location.
      if (headline) {
        expect(headline.textContent?.trim()).not.toBe(location);
      }
    }
  });

  it("shows a skeleton while elaborations are in flight, not a fallback string", async () => {
    mockFetchCodebookAnalysis(mockCbData);
    render(<AnalysisPage projectId="1" />);
    await waitFor(() => {
      expect(screen.getAllByTestId("bn-signal-card").length).toBeGreaterThan(0);
    });
    // Whatever occupies the headline slot before a finding arrives carries no
    // text at all — there is nothing true to put there yet.
    for (const el of document.querySelectorAll(".signal-card-location-pending")) {
      expect(el.textContent).toBe("");
    }
  });


  it("marks the quote that took the reserved dissenting slot", async () => {
    // The slot is the whole reason a card is not simply agreeing with itself.
    // If it is spent and nothing says so, the reader cannot tell the card
    // carries a voice that argues with it.
    const many: CodebookAnalysisListResponse = JSON.parse(JSON.stringify(mockCbData));
    const sig = many.codebooks[0].signals[0];
    sig.group_name = "Sentiment";
    sig.label = "frustration";
    sig.label_kind = "value";
    sig.quotes = [
      { text: "a", participant_id: "p1", session_id: "s1", start_seconds: 10, intensity: 3, tag_names: ["frustration"], segment_index: 0 },
      { text: "b", participant_id: "p1", session_id: "s1", start_seconds: 60, intensity: 3, tag_names: ["frustration"], segment_index: 1 },
      { text: "c", participant_id: "p2", session_id: "s1", start_seconds: 120, intensity: 3, tag_names: ["frustration"], segment_index: 2 },
      { text: "d", participant_id: "p2", session_id: "s1", start_seconds: 180, intensity: 1, tag_names: ["frustration"], segment_index: 3 },
      { text: "e", participant_id: "p3", session_id: "s1", start_seconds: 240, intensity: 3, tag_names: ["delight"], segment_index: 4 },
    ];
    mockFetchCodebookAnalysis(many);
    render(<AnalysisPage projectId="1" />);

    await waitFor(() => {
      expect(screen.getAllByTestId("bn-signal-card").length).toBeGreaterThan(0);
    });

    const marked = document.querySelectorAll("blockquote.bn-dissenting");
    expect(marked).toHaveLength(1);
    expect(marked[0].textContent).toContain("e");
  });

});
