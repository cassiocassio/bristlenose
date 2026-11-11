import { resetSignalWorkingStore } from "../contexts/SignalWorkingStore";
import { featureFlags, resetFeatureFlags } from "../utils/featureFlags";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { act, render, renderHook, screen, waitFor, fireEvent } from "@testing-library/react";
import { SignalsPage } from "./SignalsPage";
import type { CodebookSignalsListResponse, SentimentSignalsData } from "../utils/types";
import { resetSignalStore, useSignalStore } from "../contexts/SignalStore";
import { resetInspectorStore } from "../contexts/InspectorStore";
import { navigateTo } from "../shims/navigation";
import { ANCHOR_SELECTORS } from "../hooks/useAnchorReporter";
import { useInspectorStore } from "../contexts/InspectorStore";
import { _resetDisplayPrefs, setDisplayPref } from "../contexts/DisplayPrefsStore";

// The location link goes to the Quotes lens's own address (utils/quotesLink.ts), through the
// navigation shim: a link to a group shows Sections & themes for the visit (QuotesArrival).
vi.mock("../shims/navigation", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../shims/navigation")>()),
  navigateTo: vi.fn(),
  navigationReady: () => true,
}));

// The server withholds the Signals lens while its first report is being built
// (docs/design-signals-lens-readiness.md); the page reads that through useLenses.
const lensState = vi.hoisted(() => ({ signalsWithheld: false }));
vi.mock("../contexts/ConditionStore", async (importOriginal) => {
  const original = await importOriginal<typeof import("../contexts/ConditionStore")>();
  return {
    ...original,
    useLenses: () => ({ ...original.ALL_LENSES, signals: !lensState.signalsWithheld }),
  };
});

// ---------------------------------------------------------------------------
// Mock data — per-codebook shape
// ---------------------------------------------------------------------------

const mockCbData: CodebookSignalsListResponse = {
  codebooks: [
    {
      codebook_id: "uxr",
      codebook_name: "UX Research",
      colour_set: "ux",
      signals: [
        {
          location: "Checkout",
          source_type: "section",
          anchor: "section-7",
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
          anchor: "theme-onboarding",
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

const mockSentimentData: SentimentSignalsData = {
  signals: [
    {
      location: "Checkout",
      sourceType: "section",
      anchor: "section-checkout",
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

const emptyCbData: CodebookSignalsListResponse = {
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
  _resetDisplayPrefs();
  lensState.signalsWithheld = false;
    resetSignalWorkingStore();
    resetFeatureFlags();
  resetSignalStore();
  resetInspectorStore();
  fetchMock = vi.fn();
  globalThis.fetch = fetchMock;
  // Reset window globals
  (window as unknown as Record<string, unknown>).BRISTLENOSE_ANALYSIS = undefined;
  (window as unknown as Record<string, unknown>).BRISTLENOSE_API_BASE = "/api/projects/1";
  // jsdom has no scrollIntoView, and the page scrolls to a focused card a frame after the
  // focus lands: under load that frame fires before the test ends and was an uncaught
  // TypeError (gotchas.md § Testing). `recordScrolls()` replaces this when a test asserts on it.
  Element.prototype.scrollIntoView = vi.fn();
});

afterEach(() => {
  _resetDisplayPrefs();
  vi.useRealTimers();
  vi.restoreAllMocks();
});

function mockFetchCodebookSignals(data: CodebookSignalsListResponse) {
  fetchMock.mockResolvedValue({
    ok: true,
    json: () => Promise.resolve({
      snapshot: data,
      source: "codebook_apply",
      computed_at: "2026-10-27T12:00:00+00:00",
    }),
  });
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("SignalsPage", () => {
  it("renders tag signal cards when API returns data", async () => {
    mockFetchCodebookSignals(mockCbData);
    render(<SignalsPage projectId="1" />);

    await waitFor(() => {
      expect(screen.getAllByTestId("bn-signal-card")).toHaveLength(2);
    });

    expect(screen.getAllByText("Checkout").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("Pain points").length).toBeGreaterThanOrEqual(1);
    const urls = fetchMock.mock.calls.map(([url]: [string]) => String(url));
    expect(urls.some((url: string) => url.endsWith("/signals/snapshot"))).toBe(true);
    expect(urls.some((url: string) => url.includes("/signals/elaborations"))).toBe(false);
  });

  it("quietly receives a first snapshot the sidecar is materialising", async () => {
    vi.useFakeTimers();
    (window as unknown as Record<string, unknown>).BRISTLENOSE_ANALYSIS = mockSentimentData;
    fetchMock
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ snapshot: null, source: null, computed_at: null, pending: true }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ snapshot: mockCbData, source: "startup_missing_snapshot", computed_at: "2026-10-28T09:00:00+00:00", pending: false }),
      });

    render(<SignalsPage projectId="1" />);
    await act(async () => { await vi.advanceTimersByTimeAsync(0); });
    expect(fetchMock).toHaveBeenCalledTimes(1);

    await act(async () => { await vi.advanceTimersByTimeAsync(2_000); });
    expect(screen.getAllByTestId("bn-signal-card")).toHaveLength(3);
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("shows nothing at all while the lens is withheld, not the live cards and not a sentence", async () => {
    lensState.signalsWithheld = true;
    (window as unknown as Record<string, unknown>).BRISTLENOSE_ANALYSIS = mockSentimentData;
    mockFetchCodebookSignals(mockCbData);
    const { container } = render(<SignalsPage projectId="1" />);

    expect(screen.getByTestId("signals-withheld")).toBeTruthy();
    expect(screen.queryAllByTestId("bn-signal-card")).toHaveLength(0);
    expect(container.textContent).toBe("");
  });

  it("a page open when a build begins has the report as soon as the lens lights, with nothing wrong shown in between", async () => {
    vi.useFakeTimers();
    (window as unknown as Record<string, unknown>).BRISTLENOSE_ANALYSIS = mockSentimentData;
    // Mounted lit, the last read says there is nothing and nothing is coming.
    fetchMock.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ snapshot: null, source: null, computed_at: null, pending: false }),
    });
    const { rerender, container } = render(<SignalsPage projectId="1" />);
    await act(async () => { await vi.advanceTimersByTimeAsync(0); });
    expect(fetchMock).toHaveBeenCalledTimes(1);

    // A run completes: the lens is withheld. The page empties and keeps reading.
    lensState.signalsWithheld = true;
    rerender(<SignalsPage projectId="1" />);
    await act(async () => { await vi.advanceTimersByTimeAsync(0); });
    expect(screen.getByTestId("signals-withheld")).toBeTruthy();
    expect(container.textContent).toBe("");
    const readsWhileWithheld = fetchMock.mock.calls.length;

    // The report lands. The page reads it while still withheld.
    fetchMock.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({
        snapshot: mockCbData, source: "new_interviews", computed_at: "2026-10-30T09:01:00+00:00", pending: false,
      }),
    });
    await act(async () => { await vi.advanceTimersByTimeAsync(2_000); });
    expect(fetchMock.mock.calls.length).toBeGreaterThan(readsWhileWithheld);
    expect(screen.queryAllByTestId("bn-signal-card")).toHaveLength(0);

    // The lens lights: cards, never the no-data sentence or the live cards first.
    lensState.signalsWithheld = false;
    rerender(<SignalsPage projectId="1" />);
    await act(async () => { await vi.advanceTimersByTimeAsync(0); });
    expect(screen.getAllByTestId("bn-signal-card").length).toBeGreaterThan(0);
    expect(container.textContent).not.toContain("No signals yet");
  });

  it("publishes no entries to the sidebar while the body is empty", async () => {
    lensState.signalsWithheld = true;
    (window as unknown as Record<string, unknown>).BRISTLENOSE_ANALYSIS = mockSentimentData;
    mockFetchCodebookSignals(mockCbData);
    function Probe() {
      return <span data-testid="probe">{useSignalStore().signals.length}</span>;
    }
    render(<><SignalsPage projectId="1" /><Probe /></>);
    await waitFor(() => expect(screen.getByTestId("signals-withheld")).toBeTruthy());
    expect(screen.getByTestId("probe").textContent).toBe("0");
  });

  it("keeps asking while an empty report is pending, so the first real one arrives", async () => {
    vi.useFakeTimers();
    (window as unknown as Record<string, unknown>).BRISTLENOSE_ANALYSIS = mockSentimentData;
    fetchMock
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({
          snapshot: { codebooks: [] }, source: "t", computed_at: "2026-10-30T09:00:00+00:00", pending: true,
        }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({
          snapshot: mockCbData, source: "new_interviews", computed_at: "2026-10-30T09:01:00+00:00", pending: false,
        }),
      });

    render(<SignalsPage projectId="1" />);
    await act(async () => { await vi.advanceTimersByTimeAsync(0); });
    expect(fetchMock).toHaveBeenCalledTimes(1);

    await act(async () => { await vi.advanceTimersByTimeAsync(2_000); });
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(screen.getAllByTestId("bn-signal-card").length).toBeGreaterThan(0);
  });

  it("does not poll an absent snapshot when no background repair is pending", async () => {
    vi.useFakeTimers();
    (window as unknown as Record<string, unknown>).BRISTLENOSE_ANALYSIS = mockSentimentData;
    fetchMock.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ snapshot: null, source: null, computed_at: null, pending: false }),
    });

    render(<SignalsPage projectId="1" />);
    await act(async () => { await vi.advanceTimersByTimeAsync(10_000); });
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("shows one compound location at a time and reveals the sidebar target", async () => {
    mockFetchCodebookSignals(mockCbData);
    render(<SignalsPage projectId="1" />);

    await waitFor(() => {
      expect(screen.getByLabelText("Checkout")).not.toHaveAttribute("hidden");
    });

    window.dispatchEvent(new CustomEvent("bn:signal-focus", {
      detail: { key: "theme|Onboarding|Mental models" },
    }));

    await waitFor(() => {
      expect(screen.getByLabelText("Checkout")).toHaveAttribute("hidden");
      expect(screen.getByLabelText("Onboarding")).not.toHaveAttribute("hidden");
    });
  });

  it("draws each card with an id the Signals anchor selector matches, one per card", async () => {
    // Decision #182: the Mac app comes back to the card by this id. A selector
    // dies silently when the DOM it watches changes, so pin it here.
    mockFetchCodebookSignals(mockCbData);
    const { container } = render(<SignalsPage projectId="1" />);
    await waitFor(() => expect(screen.getAllByTestId("bn-signal-card")).toHaveLength(2));
    const ids = [...container.querySelectorAll(ANCHOR_SELECTORS.signals)].map((el) => el.id);
    expect(ids).toHaveLength(2);
    expect(new Set(ids).size).toBe(2);
  });

  it("shows the place a reopened study's card is on, and selects nothing", async () => {
    // `scrollToAnchor` found the remembered card in a hidden place and asks the
    // page to show it (`bn:reveal-anchor`). The page shows the place and claims
    // the landing; no selection, no inspector sync (decision #182).
    mockFetchCodebookSignals(mockCbData);
    const { container } = render(<SignalsPage projectId="1" />);
    await waitFor(() => {
      expect(screen.getByLabelText("Checkout")).not.toHaveAttribute("hidden");
    });
    const signalStore = renderHook(() => useSignalStore());
    const inspector = renderHook(() => useInspectorStore());
    const sourceBefore = inspector.result.current.activeSource;
    const card = container.querySelector<HTMLElement>(
      `section[aria-label="Onboarding"] ${ANCHOR_SELECTORS.signals}`,
    );
    expect(card).not.toBeNull();

    let claimed = false;
    act(() => {
      const reveal = new CustomEvent("bn:reveal-anchor", { detail: { id: card!.id }, cancelable: true });
      claimed = !window.dispatchEvent(reveal);
    });

    expect(claimed).toBe(true);
    await waitFor(() => {
      expect(screen.getByLabelText("Onboarding")).not.toHaveAttribute("hidden");
      expect(screen.getByLabelText("Checkout")).toHaveAttribute("hidden");
    });
    expect(signalStore.result.current.focusedKey).toBeNull();
    expect(inspector.result.current.activeSource).toBe(sourceBefore);
    expect(container.querySelector(".signal-card.bn-selected")).toBeNull();
  });

  it("lands a reopened study's first card on the place showing with its title, and claims it", async () => {
    // The visible case: the shim offers it too, and the page lands it as its list does
    // (`scrollToCard`), so the place title comes with the first card.
    const scrolled: Element[] = [];
    Element.prototype.scrollIntoView = function (this: Element) { scrolled.push(this); };
    mockFetchCodebookSignals(mockCbData);
    const { container } = render(<SignalsPage projectId="1" />);
    await waitFor(() => {
      expect(screen.getByLabelText("Checkout")).not.toHaveAttribute("hidden");
    });
    const card = container.querySelector<HTMLElement>(
      `section[aria-label="Checkout"] ${ANCHOR_SELECTORS.signals}`,
    );
    scrolled.length = 0;
    let claimed = false;
    act(() => {
      claimed = !window.dispatchEvent(
        new CustomEvent("bn:reveal-anchor", { detail: { id: card!.id }, cancelable: true }),
      );
    });
    expect(claimed).toBe(true);
    await waitFor(() => expect(scrolled.length).toBeGreaterThan(0));
    expect(scrolled[scrolled.length - 1].classList.contains("signals-center")).toBe(true);
    expect(container.querySelector(".signal-card.bn-selected")).toBeNull();
  });

  it("leaves a reveal it does not know unclaimed", async () => {
    mockFetchCodebookSignals(mockCbData);
    render(<SignalsPage projectId="1" />);
    await waitFor(() => expect(screen.getAllByTestId("bn-signal-card")).toHaveLength(2));
    let claimed = true;
    act(() => {
      claimed = !window.dispatchEvent(
        new CustomEvent("bn:reveal-anchor", { detail: { id: "q-p1-10" }, cancelable: true }),
      );
    });
    expect(claimed).toBe(false);
  });

  it("shows source breakdown banner for pending tags", async () => {
    mockFetchCodebookSignals(mockCbData);
    render(<SignalsPage projectId="1" />);

    await waitFor(() => {
      expect(screen.getByTestId("bn-source-banner")).toBeTruthy();
    });
    // Aggregated: 3+1=4 accepted, 2+2=4 pending
    expect(screen.getByTestId("bn-source-banner").textContent).toContain("4 accepted");
    expect(screen.getByTestId("bn-source-banner").textContent).toContain("4 pending");
  });

  it("renders heatmap table", async () => {
    mockFetchCodebookSignals(mockCbData);
    render(<SignalsPage projectId="1" />);

    await waitFor(() => {
      expect(screen.getAllByTestId("bn-heatmap").length).toBeGreaterThan(0);
    });
  });

  it("shows no-data message when API returns empty", async () => {
    mockFetchCodebookSignals(emptyCbData);
    render(<SignalsPage projectId="1" />);

    await waitFor(() => {
      expect(screen.getByText(/no signals yet/i)).toBeTruthy();
    }, { timeout: 3000 });
  });

  it("shows sentiment signals when baked data exists", async () => {
    (window as unknown as Record<string, unknown>).BRISTLENOSE_ANALYSIS = mockSentimentData;
    mockFetchCodebookSignals(emptyCbData);
    render(<SignalsPage projectId="1" />);

    await waitFor(() => {
      expect(screen.getAllByTestId("bn-signal-card")).toHaveLength(1);
    });
    expect(screen.getAllByText("Frustration").length).toBeGreaterThanOrEqual(1);
  });

  it("shows both sentiment and tag cards when both data exist", async () => {
    (window as unknown as Record<string, unknown>).BRISTLENOSE_ANALYSIS = mockSentimentData;
    mockFetchCodebookSignals(mockCbData);
    render(<SignalsPage projectId="1" />);

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
    mockFetchCodebookSignals(mockCbData);
    render(<SignalsPage projectId="1" />);

    await waitFor(() => {
      expect(screen.getAllByTestId("bn-signal-card")).toHaveLength(3);
    });

    // The two kind-split headings are gone. A place appeared in both halves
    // and nowhere as itself; it is a heading of its own now.
    expect(screen.queryByText("Sentiment signals")).toBeNull();
    expect(screen.queryByText("Tag signals")).toBeNull();

    // Each page is one section or theme, and its title is that place, once.
    const title = document.querySelector(".signals-center > .section-heading") as HTMLElement;
    expect(title.textContent?.trim()).not.toBe("Signals");
    expect(document.querySelectorAll(".signals-codebook-heading")).toHaveLength(0);
    // One run of cards per place, each place a section of its own.
    const places = [...document.querySelectorAll(".signal-compound-page")];
    expect(places.length).toBeGreaterThan(0);
    expect(places.map((n) => n.getAttribute("aria-label"))).toContain(title.textContent?.trim());
    expect(document.querySelectorAll(".signal-cards").length).toBe(places.length);
  });

  // The flush-to-datum contract, cheap. e2e/tests/lens-datum.spec.ts is the
  // real gate, but it needs a server; this catches the enrolment breaking at
  // the moment someone edits the render. The refactor that grouped cards by
  // location removed the lens's only .section-heading and took the datum with
  // it — no unit test could see the CSS selector stop matching, so this asserts
  // the shape the selector needs instead.
  it("keeps the lens enrolled in the flush-to-datum system", async () => {
    mockFetchCodebookSignals(mockCbData);
    render(<SignalsPage projectId="1" />);

    await waitFor(() => {
      expect(screen.getAllByTestId("bn-signal-card").length).toBeGreaterThan(0);
    });

    const pane = document.querySelector(".signals-center");
    expect(pane).toBeTruthy();
    // `.signals-center > .section-heading:first-of-type { margin-top: 0 }`
    expect(pane!.querySelector(":scope > .section-heading")).toBeTruthy();
    expect(pane!.firstElementChild!.classList.contains("section-heading")).toBe(true);
  });

  // The empty states are enrolled too. A study with no Signals report yet (no
  // cloud model, or a first report not built) rendered the "no data" sentence
  // under a heading in a bare <div>, so the lens opened 40px low in exactly the
  // state a researcher without a cloud key sees every time (2 Nov 2026).
  it("keeps the no-data state enrolled in the flush-to-datum system", async () => {
    fetchMock.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ snapshot: null, source: null, computed_at: null, pending: false }),
    });
    render(<SignalsPage projectId="1" />);

    await waitFor(() => {
      expect(screen.getByText(/No signals yet\./)).toBeTruthy();
    });

    const pane = document.querySelector(".signals-center");
    expect(pane).toBeTruthy();
    expect(pane!.firstElementChild!.classList.contains("section-heading")).toBe(true);
  });

  it("the sidebar list and the rendered cards are the same set", async () => {
    // The 1:1 invariant: every nav row lands on a card, and no card is
    // unreachable. It used to hold by ACCIDENT — MAX_SIGNALS sliced one list
    // that both surfaces read. De-duplication runs once, over the merged list,
    // and both read its output, so they cannot drift apart.
    (window as unknown as Record<string, unknown>).BRISTLENOSE_ANALYSIS = mockSentimentData;
    mockFetchCodebookSignals(mockCbData);
    render(<SignalsPage projectId="1" />);

    await waitFor(() => {
      expect(screen.getAllByTestId("bn-signal-card").length).toBeGreaterThan(0);
    });

    const { renderHook } = await import("@testing-library/react");
    const { useSignalStore } = await import("../contexts/SignalStore");
    const { result } = renderHook(() => useSignalStore());
    expect(result.current.signals.length)
      .toBe(screen.getAllByTestId("bn-signal-card").length);
  });

  it("no longer renders the pattern chip, though the pattern still arrives", async () => {
    const named: CodebookSignalsListResponse = JSON.parse(JSON.stringify(mockCbData));
    named.codebooks[0].signals[0].signal_name = "Checkout Latency Tension";
    named.codebooks[0].signals[0].pattern = "tension";
    mockFetchCodebookSignals(named);
    render(<SignalsPage projectId="1" />);

    await waitFor(() => {
      expect(screen.getByText("Checkout Latency Tension")).toBeTruthy();
    });
    expect(screen.queryByTestId("pattern-badge")).toBeNull();
    expect(screen.queryByText("TENSION")).toBeNull();
  });

  it("renders a validated evidence assertion inline and links its speaker badge to the source quote", async () => {
    const asserted: CodebookSignalsListResponse = JSON.parse(JSON.stringify(mockCbData));
    const signal = asserted.codebooks[0].signals[0];
    signal.elaboration = "Checkout delays interrupt purchase intent. || Participants wait for a response before continuing.";
    signal.quotes[0].quote_id = "q_checkout_latency";
    const assertionText = "One participant said the checkout was really slow.";
    const highlighted = "the checkout was really slow";
    signal.evidence_assertions = [{
      id: "ea_checkout_latency",
      ordinal: 0,
      text: assertionText,
      source_quote_id: "q_checkout_latency",
      participant_id: "p1",
      source_excerpt: "checkout was really slow",
      intervention_fragment: {
        start: assertionText.indexOf(highlighted),
        end: assertionText.indexOf(highlighted) + highlighted.length,
        text: highlighted,
        rationale: "negative_actionable_cause",
      },
    }];
    mockFetchCodebookSignals(asserted);
    render(<SignalsPage projectId="1" />);

    await waitFor(() => {
      expect(screen.getByTestId("signal-evidence-assertions")).toBeTruthy();
    });

    const list = screen.getByTestId("signal-evidence-assertions");
    expect(list.querySelector("mark")?.textContent).toBe(highlighted);
    expect(screen.queryByText("Participants wait for a response before continuing.")).toBeNull();

    // The speaker badge in the bullet and the one on the quote do the same thing: they go to
    // the transcript at that moment, as the badge does everywhere else.
    const bulletBadge = list.querySelector("a.speaker-link") as HTMLAnchorElement;
    const quoteEl = document.querySelector('blockquote[data-quote-id="q_checkout_latency"]') as HTMLElement;
    const quoteBadge = quoteEl.querySelector("a.speaker-link") as HTMLAnchorElement;
    expect(bulletBadge.getAttribute("href")).toContain("/report/sessions/");
    expect(bulletBadge.getAttribute("href")).toBe(quoteBadge.getAttribute("href"));
    expect(screen.queryByRole("button", { name: /focus evidence assertion using this quote/ })).toBeNull();
    // The timecode is the shared play link (it plays the video where there is a recording),
    // not a bare anchor to the transcript.
    const timecode = quoteEl.querySelector("a.timecode") as HTMLElement;
    expect(timecode.getAttribute("data-participant")).toBeTruthy();
    expect(timecode.getAttribute("data-seconds")).not.toBeNull();

    // The highlighted words are the control: pressing them flashes the quote they came from.
    expect(quoteEl.hasAttribute("data-arrived")).toBe(false);
    // Its name is its own words (a visible label must be part of the accessible name); the
    // tooltip says what pressing it does.
    const words = screen.getByRole("button", { name: highlighted });
    expect(words.getAttribute("title")).toBe("Participant p1; show source quote supporting this evidence");
    // Not a <button>: a browser lays a button out as one unbreakable box, so a phrase longer
    // than the rest of the line jumped whole to the next line and stranded the words before it.
    expect(words.tagName).toBe("SPAN");
    // Enter and Space press it, as they would a button.
    quoteEl.removeAttribute("data-arrived");
    fireEvent.keyDown(words, { key: "Enter" });
    expect(quoteEl.hasAttribute("data-arrived")).toBe(true);
    fireEvent.click(words);
    expect(quoteEl.hasAttribute("data-arrived")).toBe(true);
    // No persistent state is left on anything: the flash is the whole cue.
    expect(document.querySelector("[data-evidence-focused]")).toBeNull();
    expect(words.getAttribute("aria-pressed")).toBeNull();

    // A repeat press flashes again.
    quoteEl.removeAttribute("data-arrived");
    fireEvent.click(words);
    expect(quoteEl.hasAttribute("data-arrived")).toBe(true);
  });

  it("expands signal card quotes on toggle click", async () => {
    mockFetchCodebookSignals(mockCbData);
    render(<SignalsPage projectId="1" />);

    await waitFor(() => {
      expect(screen.getAllByTestId("bn-signal-card")).toHaveLength(2);
    });

    // First card (Checkout/Pain points) has 5 quotes — 4 visible, 1 hidden
    const toggle = screen.getAllByTestId("bn-signal-toggle")[0];
    expect(toggle.textContent).toContain("Show all 5 quotes");
    fireEvent.click(toggle);
    // "Hide" is the researcher's word for a quote they set aside; this link only collapses.
    expect(toggle.textContent).toContain("Show fewer");
    expect(toggle.textContent).not.toContain("Hide");
  });

  it("keeps the claim alone, not the summary paragraph, when every cited quote has stopped counting", async () => {
    const filtered: CodebookSignalsListResponse = JSON.parse(JSON.stringify(mockCbData));
    const signal = filtered.codebooks[0].signals[0];
    signal.elaboration = "Checkout delays interrupt purchase intent. || Participants wait for a response before continuing.";
    // The server has dropped the only assertion because its quote was hidden.
    signal.evidence_assertions = [];
    (signal as { had_evidence_assertions?: boolean }).had_evidence_assertions = true;
    mockFetchCodebookSignals(filtered);
    render(<SignalsPage projectId="1" />);

    await waitFor(() => {
      expect(screen.getByText("Checkout delays interrupt purchase intent.")).toBeTruthy();
    });
    expect(screen.queryByText("Participants wait for a response before continuing.")).toBeNull();
  });

  it("still shows the whole narrative when a card never had evidence assertions", async () => {
    const plain: CodebookSignalsListResponse = JSON.parse(JSON.stringify(mockCbData));
    const signal = plain.codebooks[0].signals[0];
    signal.elaboration = "Checkout delays interrupt purchase intent. || Participants wait for a response before continuing.";
    signal.evidence_assertions = [];
    mockFetchCodebookSignals(plain);
    render(<SignalsPage projectId="1" />);

    await waitFor(() => {
      expect(screen.getByText("Participants wait for a response before continuing.")).toBeTruthy();
    });
  });

  it("opens the overflow and flashes the source quote when its evidence words are pressed", async () => {
    const asserted: CodebookSignalsListResponse = JSON.parse(JSON.stringify(mockCbData));
    const signal = asserted.codebooks[0].signals[0];
    signal.elaboration = "Checkout delays interrupt purchase intent.";
    signal.quotes[4].quote_id = "q_overflow";
    signal.evidence_assertions = [{
      id: "ea_overflow",
      ordinal: 0,
      text: "One participant described the lengthy wait.",
      source_quote_id: "q_overflow",
      participant_id: signal.quotes[4].participant_id,
      source_excerpt: signal.quotes[4].text,
      intervention_fragment: {
        start: "One participant described the lengthy wait.".indexOf("the lengthy wait"),
        end: "One participant described the lengthy wait.".indexOf("the lengthy wait") + "the lengthy wait".length,
        text: "the lengthy wait",
        rationale: "negative_actionable_cause",
      },
    }];
    mockFetchCodebookSignals(asserted);
    render(<SignalsPage projectId="1" />);

    await waitFor(() => {
      expect(screen.getByTestId("signal-evidence-assertions")).toBeTruthy();
    });
    const card = screen.getAllByTestId("bn-signal-card")[0];
    expect(card.classList.contains("expanded")).toBe(false);
    fireEvent.click(screen.getByRole("button", { name: "the lengthy wait" }));
    expect(card.classList.contains("expanded")).toBe(true);
    expect(document.querySelector('blockquote[data-arrived]')?.textContent)
      .toContain(signal.quotes[4].text);
  });

  it("does not show source banner when only sentiment data", async () => {
    (window as unknown as Record<string, unknown>).BRISTLENOSE_ANALYSIS = mockSentimentData;
    mockFetchCodebookSignals(emptyCbData);
    render(<SignalsPage projectId="1" />);

    await waitFor(() => {
      expect(screen.getAllByTestId("bn-signal-card")).toHaveLength(1);
    });

    expect(screen.queryByTestId("bn-source-banner")).toBeNull();
  });

  it("shows the score on the hero chip and hides the working behind it", async () => {
    mockFetchCodebookSignals(mockCbData);
    render(<SignalsPage projectId="1" />);

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

  it("does not draw the folded readings line while it is parked", async () => {
    const dup: CodebookSignalsListResponse = JSON.parse(JSON.stringify(mockCbData));
    const a = dup.codebooks[0].signals[0];
    const b = JSON.parse(JSON.stringify(a));
    b.group_name = "Conceptual model";
    b.composite_signal = a.composite_signal / 2;
    dup.codebooks[0].signals.push(b);
    dup.codebooks[0].columns.push("Conceptual model");
    mockFetchCodebookSignals(dup);
    render(<SignalsPage projectId="1" />);
    await waitFor(() => {
      expect(screen.getAllByTestId("bn-signal-card").length).toBeGreaterThan(0);
    });
    expect(screen.queryByTestId("bn-signal-alternates")).toBeNull();
    expect(screen.queryByText("Also read as")).toBeNull();
  });

  it("opens the working on every card at once, and keeps it open when the page is left and returned to", async () => {
    mockFetchCodebookSignals(mockCbData);
    const first = render(<SignalsPage projectId="1" />);
    await waitFor(() => {
      expect(screen.getAllByTestId("bn-signal-card")).toHaveLength(2);
    });
    expect(screen.queryAllByTestId("bn-signal-working")).toHaveLength(0);

    // The working is store state the cards subscribe to from an effect, which under load is
    // still pending when the cards are first on the page: a click before it lands shows on the
    // next flush, not synchronously, so each step waits for what it expects.
    fireEvent.click(screen.getAllByTestId("bn-signal-hero")[0]);
    // One card was clicked; both show their working.
    await waitFor(() => {
      expect(screen.getAllByTestId("bn-signal-working")).toHaveLength(2);
    });

    // Leave the lens and come back: it is still open on every card.
    first.unmount();
    mockFetchCodebookSignals(mockCbData);
    render(<SignalsPage projectId="1" />);
    await waitFor(() => {
      expect(screen.getAllByTestId("bn-signal-card")).toHaveLength(2);
      expect(screen.getAllByTestId("bn-signal-working")).toHaveLength(2);
    });

    // Closing it on the second card closes it on both.
    fireEvent.click(screen.getAllByTestId("bn-signal-hero")[1]);
    await waitFor(() => {
      expect(screen.queryAllByTestId("bn-signal-working")).toHaveLength(0);
    });
  });

  it("puts the intensity circles first in the quote's body, small, so the words flow around them", async () => {
    mockFetchCodebookSignals(mockCbData);
    render(<SignalsPage projectId="1" />);
    await waitFor(() => {
      expect(screen.getAllByTestId("bn-signal-card")).toHaveLength(2);
    });
    const body = document.querySelector(".signal-card-quotes .quote-body") as HTMLElement;
    // First in the body: a float placed after the text draws below it, not top right.
    expect(body.firstElementChild?.classList.contains("intensity-dots")).toBe(true);
    expect(body.querySelector("svg")?.getAttribute("data-size")).toBe("s");
    // The chart's dots are the larger size.
    fireEvent.click(screen.getAllByTestId("bn-signal-hero")[0]);
    expect(screen.getAllByTestId("bn-metric-dots")[0].getAttribute("data-size")).toBe("m");
  });

  const LONG_EVIDENCE_QUOTE =
    "Well, I can see the different sections... across the top quite easily — that makes it easier to select stuff. I'm... interested both in the... bed linen, ... that's... right there because that's something I've been looking at at the minute. I mean, it looks like an IKEA website. Then I scroll down and, so, I see the kitchen storage... which is what I came for, because I need jars and tins for the shelf. Fine, that works for me.";

  function cardsWithLongQuote(): CodebookSignalsListResponse {
    const data = structuredClone(mockCbData);
    data.codebooks[0].signals[0].quotes[0].text = LONG_EVIDENCE_QUOTE;
    return data;
  }

  it("draws a long evidence quote as one run of words when Break long paragraphs is off", async () => {
    mockFetchCodebookSignals(cardsWithLongQuote());
    act(() => setDisplayPref("breaks", "off"));
    render(<SignalsPage projectId="1" />);
    await waitFor(() => {
      expect(screen.getAllByTestId("bn-signal-card")).toHaveLength(2);
    });
    expect(document.querySelectorAll(".bn-block")).toHaveLength(0);
    expect(document.querySelector(".signal-card-quotes .quote-text")?.textContent).toBe(LONG_EVIDENCE_QUOTE);
  });

  it("breaks a long evidence quote into blocks, keeping every word, when Break long paragraphs is on", async () => {
    mockFetchCodebookSignals(cardsWithLongQuote());
    act(() => setDisplayPref("breaks", "on"));
    render(<SignalsPage projectId="1" />);
    await waitFor(() => {
      expect(screen.getAllByTestId("bn-signal-card")).toHaveLength(2);
    });
    const blocks = Array.from(document.querySelectorAll(".signal-card-quotes .quote-text .bn-block"));
    expect(blocks.length).toBeGreaterThan(1);
    const words = (t: string) => t.split(/\s+/).filter(Boolean).join(" ");
    expect(words(blocks.map((b) => b.textContent ?? "").join(" "))).toBe(words(LONG_EVIDENCE_QUOTE));
    // Signals draws no quote marks, so the blocks add none.
    expect(document.querySelectorAll(".signal-card-quotes .smart-quote")).toHaveLength(0);
  });

  it("measures an expanded card again when Break long paragraphs changes, so taller quotes are not clipped", async () => {
    // jsdom has no layout: stand in for the height the browser would report.
    let height = 100;
    const spy = vi.spyOn(HTMLElement.prototype, "scrollHeight", "get").mockImplementation(() => height);
    mockFetchCodebookSignals(cardsWithLongQuote());
    act(() => setDisplayPref("breaks", "off"));
    render(<SignalsPage projectId="1" />);
    await waitFor(() => {
      expect(screen.getAllByTestId("bn-signal-card")).toHaveLength(2);
    });
    fireEvent.click(screen.getAllByTestId("bn-signal-toggle")[0]);
    const expansion = document.querySelector(".signal-card-expansion") as HTMLElement;
    expect(expansion.style.maxHeight).toBe("100px");

    height = 160;
    act(() => setDisplayPref("breaks", "on"));
    expect(expansion.style.maxHeight).toBe("160px");
    spy.mockRestore();
  });

  /** Two cards for one place: the first and a second one under it. */
  function twoCardsOnOnePage(): CodebookSignalsListResponse {
    const base = mockCbData.codebooks[0];
    const first = base.signals[0];
    // Different quotes, or the page folds the two readings into one card.
    const other = mockCbData.codebooks[1].signals[0];
    return {
      ...mockCbData,
      codebooks: [{
        ...base,
        signals: [first, {
          ...other,
          location: first.location,
          source_type: first.source_type,
          anchor: first.anchor,
          group_name: "Mental models",
          composite_signal: 0.31,
        }],
      }],
    };
  }

  async function renderTwoCards() {
    mockFetchCodebookSignals(twoCardsOnOnePage());
    render(<SignalsPage projectId="1" />);
    await waitFor(() => {
      expect(screen.getAllByTestId("bn-signal-card")).toHaveLength(2);
    });
  }

  function recordScrolls() {
    const scrolled: { el: Element; arg: unknown }[] = [];
    const original = Element.prototype.scrollIntoView;
    Element.prototype.scrollIntoView = function (this: Element, arg?: unknown) {
      scrolled.push({ el: this, arg });
    };
    return { scrolled, restore: () => { Element.prototype.scrollIntoView = original; } };
  }

  it("a later card scrolls so its top edge is just inside the viewport", async () => {
    const rec = recordScrolls();
    try {
      await renderTwoCards();
      rec.scrolled.length = 0;
      act(() => {
        window.dispatchEvent(new CustomEvent("bn:signal-focus", {
          detail: { key: "section|Checkout|Mental models" },
        }));
      });
      await waitFor(() => expect(rec.scrolled.length).toBeGreaterThan(0));
      const last = rec.scrolled[rec.scrolled.length - 1];
      expect(last.el.getAttribute("data-testid")).toBe("bn-signal-card");
      expect(last.el.textContent).toContain("Mental models");
      expect((last.arg as ScrollIntoViewOptions).block).toBe("start");
    } finally {
      rec.restore();
    }
  });

  it("the first card on a page scrolls to the top of the page, title and all", async () => {
    const rec = recordScrolls();
    try {
      await renderTwoCards();
      rec.scrolled.length = 0;
      act(() => {
        window.dispatchEvent(new CustomEvent("bn:signal-focus", {
          detail: { key: "section|Checkout|Pain points" },
        }));
      });
      await waitFor(() => expect(rec.scrolled.length).toBeGreaterThan(0));
      const last = rec.scrolled[rec.scrolled.length - 1];
      expect(last.el.classList.contains("signals-center")).toBe(true);
      expect((last.arg as ScrollIntoViewOptions).block).toBe("start");
    } finally {
      rec.restore();
    }
  });

  it("a click on the card itself selects it, without scrolling", async () => {
    const rec = recordScrolls();
    try {
      await renderTwoCards();
      rec.scrolled.length = 0;
      const [, second] = screen.getAllByTestId("bn-signal-card");
      expect(second.classList.contains("bn-selected")).toBe(false);
      fireEvent.click(second);
      expect(second.classList.contains("bn-selected")).toBe(true);
      // Selection is said to assistive technology too, on the card as on its list row.
      expect(second.getAttribute("aria-current")).toBe("true");
      expect(screen.getAllByTestId("bn-signal-card")[0].hasAttribute("aria-current")).toBe(false);
      expect(screen.getAllByTestId("bn-signal-card")[0].classList.contains("bn-selected")).toBe(false);
      expect(rec.scrolled).toHaveLength(0);
    } finally {
      rec.restore();
    }
  });

  it("a click on a control or a link inside the card does not select it", async () => {
    await renderTwoCards();
    const [first] = screen.getAllByTestId("bn-signal-card");
    // The chip opens the chart; it stops the click itself.
    fireEvent.click(first.querySelector("[data-testid='bn-signal-hero']") as HTMLElement);
    expect(first.classList.contains("bn-selected")).toBe(false);
    // A link inside the card: the participant badge.
    const link = first.querySelector("a");
    expect(link).not.toBeNull();
    fireEvent.click(link as HTMLElement);
    expect(first.classList.contains("bn-selected")).toBe(false);
  });

  it("the show-all toggle does not select the card, it only expands it", async () => {
    // More quotes than a card shows at rest, so the toggle exists. It does not stop
    // the click itself, so the card's own guard is what keeps it from selecting.
    const many = twoCardsOnOnePage();
    const q = many.codebooks[0].signals[0].quotes;
    // A copy: the fixture's signals are shared with every other test in the file.
    many.codebooks[0].signals[0] = {
      ...many.codebooks[0].signals[0],
      quotes: [...q, ...q, ...q].map((x, i) => ({
        ...x, text: `${x.text} ${i}`, start_seconds: x.start_seconds + i,
      })),
    };
    mockFetchCodebookSignals(many);
    render(<SignalsPage projectId="1" />);
    await waitFor(() => expect(screen.getAllByTestId("bn-signal-card")).toHaveLength(2));
    const toggle = screen.getAllByTestId("bn-signal-toggle")[0];
    fireEvent.click(toggle);
    expect(screen.getAllByTestId("bn-signal-card")[0].classList.contains("bn-selected")).toBe(false);
  });

  it("a focus aimed at the first card of a page that was hidden scrolls to the top of that page", async () => {
    const rec = recordScrolls();
    try {
      mockFetchCodebookSignals(mockCbData); // two places, one card each
      render(<SignalsPage projectId="1" />);
      await waitFor(() => expect(screen.getAllByTestId("bn-signal-card")).toHaveLength(2));
      rec.scrolled.length = 0;
      act(() => {
        window.dispatchEvent(new CustomEvent("bn:signal-focus", {
          detail: { key: "theme|Onboarding|Mental models" },
        }));
      });
      await waitFor(() => expect(rec.scrolled.length).toBeGreaterThan(0));
      const last = rec.scrolled[rec.scrolled.length - 1];
      expect(last.el.classList.contains("signals-center")).toBe(true);
      // The page that was hidden is the one showing now.
      const shown = document.querySelector(".signal-compound-page:not([hidden])");
      expect(shown?.getAttribute("aria-label")).toBe("Onboarding");
    } finally {
      rec.restore();
    }
  });

  it("selecting words does not select the card", async () => {
    await renderTwoCards();
    const [first] = screen.getAllByTestId("bn-signal-card");
    const spy = vi.spyOn(window, "getSelection").mockReturnValue({ toString: () => "some words" } as unknown as Selection);
    try {
      fireEvent.click(first);
      expect(first.classList.contains("bn-selected")).toBe(false);
    } finally {
      spy.mockRestore();
    }
  });

  it("names each metric in full, with the short name beside it for narrow cards", async () => {
    mockFetchCodebookSignals(mockCbData);
    render(<SignalsPage projectId="1" />);
    await waitFor(() => {
      expect(screen.getAllByTestId("bn-signal-card")).toHaveLength(2);
    });
    fireEvent.click(screen.getAllByTestId("bn-signal-hero")[0]);

    // The working opens on a store-driven render, so wait for it rather than read it at once.
    const working = (await screen.findAllByTestId("bn-signal-working"))[0];
    const long = [...working.querySelectorAll(".metric-label-long")].map((n) => n.textContent);
    const short = [...working.querySelectorAll(".metric-label-short")].map((n) => n.textContent);
    expect(long).toEqual([
      "Signal strength", "Concentration ratio", "Voices in agreement", "Emotional intensity",
    ]);
    // The short names are the ones the card used before; the card's container query picks one.
    expect(short).toEqual(["Signal", "Conc.", "Agree.", "Intensity"]);
  });

  it("the hero chip opens and closes the working", async () => {
    mockFetchCodebookSignals(mockCbData);
    render(<SignalsPage projectId="1" />);

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
    // Pressing the disclosure never changes the navigation-owned selection.
    resetSignalStore();
    mockFetchCodebookSignals(mockCbData);
    render(<SignalsPage projectId="1" />);

    await waitFor(() => {
      expect(screen.getAllByTestId("bn-signal-card")).toHaveLength(2);
    });

    const card = screen.getAllByTestId("bn-signal-card")[0];
    expect(card.classList.contains("bn-selected")).toBe(false);
    fireEvent.click(screen.getAllByTestId("bn-signal-hero")[0]);
    expect(card.classList.contains("bn-selected")).toBe(false);
  });

  it("shows the responsive evidence contribution array", async () => {
    mockFetchCodebookSignals(mockCbData);
    render(<SignalsPage projectId="1" />);

    await waitFor(() => {
      expect(screen.getAllByTestId("bn-signal-card")).toHaveLength(2);
    });

    const grids = document.querySelectorAll(".evidence-contribution-array");
    expect(grids.length).toBeGreaterThan(0);
    expect(document.querySelectorAll(".evidence-contribution-cell.strength-3").length).toBeGreaterThan(0);
  });

  // --- Per-codebook features ---

  it("renders per-codebook tabs in inspector panel", async () => {
    mockFetchCodebookSignals(mockCbData);
    render(<SignalsPage projectId="1" />);

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
    mockFetchCodebookSignals(mockCbData);
    render(<SignalsPage projectId="1" />);

    await waitFor(() => {
      expect(screen.getAllByTestId("bn-signal-card")).toHaveLength(2);
    });

    const cards = screen.getAllByTestId("bn-signal-card");
    expect(cards[0].textContent).toContain("Pain points");
    expect(cards[1].textContent).toContain("Mental models");
  });

  it("renders PersonBadge in quote blocks", async () => {
    mockFetchCodebookSignals(mockCbData);
    render(<SignalsPage projectId="1" />);

    await waitFor(() => {
      expect(screen.getAllByTestId("bn-signal-card")).toHaveLength(2);
    });

    const badges = document.querySelectorAll(".bn-person-badge");
    expect(badges.length).toBeGreaterThan(0);
  });

  it("renders per-quote tag badges", async () => {
    mockFetchCodebookSignals(mockCbData);
    render(<SignalsPage projectId="1" />);

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
    mockFetchCodebookSignals(mockCbData);
    render(<SignalsPage projectId="1" />);

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
    mockFetchCodebookSignals(mockCbData);
    render(<SignalsPage projectId="1" />);

    await waitFor(() => {
      expect(screen.getAllByTestId("bn-heatmap").length).toBeGreaterThan(0);
    });

    const rotatedHeaders = document.querySelectorAll(".heatmap-col-header");
    expect(rotatedHeaders.length).toBeGreaterThan(0);

    const rotatedLabels = document.querySelectorAll(".heatmap-col-label");
    expect(rotatedLabels.length).toBeGreaterThan(0);
  });

  it("expansion toggle reveals hidden quotes", async () => {
    mockFetchCodebookSignals(mockCbData);
    render(<SignalsPage projectId="1" />);

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
    const seqCbData: CodebookSignalsListResponse = {
      codebooks: [{
        codebook_id: "seq-test",
        codebook_name: "Sequence Test",
        colour_set: "ux",
        signals: [{
          location: "Onboarding",
          source_type: "section",
          anchor: "section-onboarding",
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
    mockFetchCodebookSignals(seqCbData);
    render(<SignalsPage projectId="1" />);

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
    const seqCbData: CodebookSignalsListResponse = {
      codebooks: [{
        codebook_id: "seq-test",
        codebook_name: "Sequence Test",
        colour_set: "ux",
        signals: [{
          location: "Onboarding",
          source_type: "section",
          anchor: "section-onboarding",
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
    mockFetchCodebookSignals(seqCbData);
    render(<SignalsPage projectId="1" />);

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
    mockFetchCodebookSignals(mockCbData);
    render(<SignalsPage projectId="1" />);

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
    const zeroCbData: CodebookSignalsListResponse = {
      codebooks: [{
        codebook_id: "zero-test",
        codebook_name: "Zero TC Test",
        colour_set: "ux",
        signals: [{
          location: "Section",
          source_type: "section",
          anchor: "section-section",
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
    mockFetchCodebookSignals(zeroCbData);
    render(<SignalsPage projectId="1" />);

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

  it("Cmd+click on a location heading is left to the browser", async () => {
    mockFetchCodebookSignals(mockCbData);
    vi.mocked(navigateTo).mockClear();
    render(<SignalsPage projectId="1" />);

    await waitFor(() => {
      expect(screen.getAllByTestId("bn-signal-card")).toHaveLength(2);
    });

    const link = document
      .querySelector(".signals-center > .section-heading a.signal-card-location-link") as HTMLElement;
    expect(link).toBeTruthy();

    // Cmd+click (Mac) — should NOT intercept
    fireEvent.click(link, { metaKey: true });
    expect(navigateTo).not.toHaveBeenCalled();

    // Ctrl+click (Win/Linux) — should NOT intercept
    fireEvent.click(link, { ctrlKey: true });
    expect(navigateTo).not.toHaveBeenCalled();

    // Plain click — should intercept
    fireEvent.click(link);
    expect(navigateTo).toHaveBeenCalledWith("/report/quotes/#section-7");
  });

  // An ELABORATED card renders a different header from a nameless one: the
  // headline is the signal's own name and the location moves to the source
  // line above it. That branch had no location link at all, so the card that
  // tells the researcher most was the one that could not hand them the quotes
  // — and no fixture in this file carried a signal_name, which is why nothing
  // caught it.
  it("the page title is the place, it links to the quotes lens, and the card carries no link", async () => {
    mockFetchCodebookSignals(mockCbData);
    (window as unknown as Record<string, unknown>).switchToTab = vi.fn();
    (window as unknown as Record<string, unknown>).scrollToAnchor = vi.fn();
    render(<SignalsPage projectId="1" />);

    await waitFor(() => {
      expect(screen.getAllByTestId("bn-signal-card").length).toBeGreaterThan(0);
    });

    // The link is the page's title, once: not once per card, and not a second heading.
    const heading = document.querySelector(".signals-center > .section-heading") as HTMLElement;
    const link = heading.querySelector("a.signal-card-location-link") as HTMLElement;
    expect(link).toBeTruthy();
    expect(link.textContent).toBe("Checkout");

    // And no card repeats it. The location is stated once, above the run.
    for (const card of screen.getAllByTestId("bn-signal-card")) {
      expect(card.querySelector("a.signal-card-location-link")).toBeNull();
    }

    vi.mocked(navigateTo).mockClear();
    fireEvent.click(link);
    // The server's anchor, keyed on the cluster id: a renamed section's link
    // still lands on it. The address is the Quotes lens's own, so a new tab
    // lands on the group too.
    expect(link.getAttribute("href")).toBe("/report/quotes/#section-7");
    expect(navigateTo).toHaveBeenCalledWith("/report/quotes/#section-7");
  });

  // The card is itself role="button" and focuses on click, so a link inside it
  // must stop the event: otherwise following the location to the quotes lens
  // also re-focuses the card and re-points the inspector behind your back.
  it("the location link is outside every card, so following it cannot focus one", async () => {
    // This replaces a test that pinned a stopPropagation on the card's own
    // The location link lives on the heading, outside every card, so following
    // it cannot alter a card's navigation-owned selection. This asserts the
    // structure that makes that separation automatic.
    resetSignalStore();   // module singleton — an earlier test's focus leaks in
    mockFetchCodebookSignals(mockCbData);
    (window as unknown as Record<string, unknown>).switchToTab = vi.fn();
    (window as unknown as Record<string, unknown>).scrollToAnchor = vi.fn();
    render(<SignalsPage projectId="1" />);

    await waitFor(() => {
      expect(screen.getAllByTestId("bn-signal-card")).toHaveLength(2);
    });

    const link = document
      .querySelector(".signals-center > .section-heading a.signal-card-location-link") as HTMLElement;
    for (const card of screen.getAllByTestId("bn-signal-card")) {
      expect(card.contains(link)).toBe(false);
    }

    vi.mocked(navigateTo).mockClear();
    fireEvent.click(link);
    await waitFor(() => {
      expect(navigateTo).toHaveBeenCalledWith("/report/quotes/#section-7");
    });
    for (const card of screen.getAllByTestId("bn-signal-card")) {
      expect(card.classList.contains("bn-selected")).toBe(false);
    }
  });

  it("heatmap cells with count=1 get data-count attribute", async () => {
    mockFetchCodebookSignals(mockCbData);
    render(<SignalsPage projectId="1" />);

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
    const contrastCbData: CodebookSignalsListResponse = {
      codebooks: [
        {
          codebook_id: "uxr",
          codebook_name: "UX Research",
          colour_set: "ux",
          signals: [
            {
              location: "Checkout",
              source_type: "section",
              anchor: "section-checkout",
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
      mockFetchCodebookSignals(contrastCbData);
      render(<SignalsPage projectId="1" />);
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
    mockFetchCodebookSignals(mockCbData);   // no elaborations in this fixture
    render(<SignalsPage projectId="1" />);

    await waitFor(() => {
      expect(screen.getAllByTestId("bn-signal-card").length).toBeGreaterThan(0);
    });

    const heading = document.querySelector(".signals-center > .section-heading") as HTMLElement;
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
    mockFetchCodebookSignals(mockCbData);
    render(<SignalsPage projectId="1" />);
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
    const many: CodebookSignalsListResponse = JSON.parse(JSON.stringify(mockCbData));
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
    mockFetchCodebookSignals(many);
    render(<SignalsPage projectId="1" />);

    await waitFor(() => {
      expect(screen.getAllByTestId("bn-signal-card").length).toBeGreaterThan(0);
    });

    const marked = document.querySelectorAll("blockquote.bn-dissenting");
    expect(marked).toHaveLength(1);
    expect(marked[0].textContent).toContain("e");
  });


  it("a folded reading carries its own claim, not just its name", async () => {
    // Parked (featureFlags.signalAlternateReadings): the behaviour is still specified here.
    featureFlags.signalAlternateReadings = true;
    // Storing a field and never reading it is what this change removed three
    // of. The folded card's claim is the thing that made it worth keeping.
    const dup: CodebookSignalsListResponse = JSON.parse(JSON.stringify(mockCbData));
    const a = dup.codebooks[0].signals[0];
    // A twin: same location, same evidence, different vocabulary. It folds.
    const b = JSON.parse(JSON.stringify(a));
    b.group_name = "Conceptual model";
    b.composite_signal = a.composite_signal / 2;   // so it is the one that folds
    b.signal_name = "Checkout Latency";
    b.elaboration = "Payment stalls. || Two of three waited long enough to say so.";
    dup.codebooks[0].signals.push(b);
    dup.codebooks[0].columns.push("Conceptual model");
    mockFetchCodebookSignals(dup);
    render(<SignalsPage projectId="1" />);

    await waitFor(() => {
      expect(screen.getAllByTestId("bn-signal-card").length).toBeGreaterThan(0);
    });

    const alt = document.querySelector(".signal-card-alternate") as HTMLElement;
    expect(alt).toBeTruthy();
    expect(alt.textContent).toBe("Checkout Latency");
    // The claim it was kept for, reachable — and without the raw `||`, which
    // is an authoring marker and not something a reader should ever see.
    expect(alt.getAttribute("title")).toContain("Payment stalls.");
    expect(alt.getAttribute("title")).not.toContain("||");
  });

});
