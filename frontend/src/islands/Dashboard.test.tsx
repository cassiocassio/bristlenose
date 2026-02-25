import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { Dashboard } from "./Dashboard";
import type { DashboardResponse } from "../utils/types";

// ---------------------------------------------------------------------------
// Mock data
// ---------------------------------------------------------------------------

const baseDashboard: DashboardResponse = {
  stats: {
    session_count: 2,
    total_duration_seconds: 3600,
    total_duration_human: "1h 0m",
    total_words: 5000,
    quotes_count: 20,
    sections_count: 2,
    themes_count: 1,
    ai_tags_count: 18,
    user_tags_count: 3,
  },
  sessions: [
    {
      session_id: "s1",
      session_number: 1,
      session_date: "2026-01-15",
      duration_seconds: 1800,
      duration_human: "30m",
      speakers: [
        { speaker_code: "m1", name: "Alex", role: "researcher" },
        { speaker_code: "p1", name: "Jordan", role: "participant" },
      ],
      source_filename: "session1.mp4",
      has_media: true,
      sentiment_counts: { frustration: 2, satisfaction: 1 },
    },
  ],
  featured_quotes: [],
  sections: [{ label: "Onboarding", anchor: "section-onboarding" }],
  themes: [{ label: "Trust", anchor: "theme-trust" }],
  moderator_header: "Moderated by Alex",
  observer_header: "",
  coverage: {
    pct_in_report: 86,
    pct_moderator: 4,
    pct_omitted: 10,
    omitted_by_session: [
      {
        session_number: 1,
        session_id: "s1",
        full_segments: [
          {
            speaker_code: "p1",
            start_time: 121.0,
            text: "No, for the hernia. For the hernia. Okay. Because it didn't heal.",
            session_id: "s1",
          },
        ],
        fragments_html:
          '<span class="label">Also omitted: </span><span class="verbatim">Okay.</span> (4\u00d7)',
      },
    ],
  },
};

// ---------------------------------------------------------------------------
// Fetch mock
// ---------------------------------------------------------------------------

function mockFetch(data: DashboardResponse) {
  (globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
    ok: true,
    json: async () => data,
  });
}

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn());
});

// ---------------------------------------------------------------------------
// Coverage box tests
// ---------------------------------------------------------------------------

describe("Dashboard CoverageBox", () => {
  it("renders the coverage heading", async () => {
    mockFetch(baseDashboard);
    render(<Dashboard projectId="1" />);
    expect(await screen.findByText("Transcript coverage")).toBeTruthy();
  });

  it("renders percentage values in legend", async () => {
    mockFetch(baseDashboard);
    render(<Dashboard projectId="1" />);
    expect(await screen.findByText("86%")).toBeTruthy();
    expect(screen.getByText("4%")).toBeTruthy();
    expect(screen.getByText("10%")).toBeTruthy();
  });

  it("renders legend labels", async () => {
    mockFetch(baseDashboard);
    const { container } = render(<Dashboard projectId="1" />);
    await screen.findByText("Transcript coverage");
    const legendItems = container.querySelectorAll(".bn-coverage-legend-item");
    expect(legendItems.length).toBe(3);
    expect(legendItems[0].textContent).toContain("in report");
    expect(legendItems[1].textContent).toContain("moderator");
    expect(legendItems[2].textContent).toContain("omitted");
  });

  it("renders stacked bar segments", async () => {
    mockFetch(baseDashboard);
    const { container } = render(<Dashboard projectId="1" />);
    await screen.findByText("Transcript coverage");
    const bar = container.querySelector(".bn-coverage-bar");
    expect(bar).toBeTruthy();
    const segments = bar!.querySelectorAll(".bn-coverage-bar-segment");
    expect(segments.length).toBe(3);
  });

  it("renders disclosure with omitted segments", async () => {
    mockFetch(baseDashboard);
    render(<Dashboard projectId="1" />);
    expect(await screen.findByText("Show omitted quotes")).toBeTruthy();
  });

  it("renders session title in omitted section", async () => {
    mockFetch(baseDashboard);
    render(<Dashboard projectId="1" />);
    expect(await screen.findByText("Session 1")).toBeTruthy();
  });

  it("renders omitted segment text", async () => {
    mockFetch(baseDashboard);
    render(<Dashboard projectId="1" />);
    expect(
      await screen.findByText(
        /No, for the hernia/,
      ),
    ).toBeTruthy();
  });

  it("hides moderator legend when pct_moderator is 0", async () => {
    const noMod = {
      ...baseDashboard,
      coverage: {
        ...baseDashboard.coverage!,
        pct_moderator: 0,
        pct_in_report: 62,
        pct_omitted: 38,
      },
    };
    mockFetch(noMod);
    const { container } = render(<Dashboard projectId="1" />);
    await screen.findByText("Transcript coverage");
    const legendItems = container.querySelectorAll(".bn-coverage-legend-item");
    // Should only have 2 legend items (report + omitted), no moderator.
    expect(legendItems.length).toBe(2);
  });

  it("shows nothing-omitted message when pct_omitted is 0", async () => {
    const fullCoverage = {
      ...baseDashboard,
      coverage: {
        pct_in_report: 92,
        pct_moderator: 8,
        pct_omitted: 0,
        omitted_by_session: [],
      },
    };
    mockFetch(fullCoverage);
    render(<Dashboard projectId="1" />);
    expect(
      await screen.findByText(/Nothing omitted/),
    ).toBeTruthy();
  });

  it("Cmd+click on nav list link does not call switchToTab", async () => {
    const withSections = {
      ...baseDashboard,
      sections: [{ label: "Onboarding", anchor: "section-onboarding" }],
    };
    mockFetch(withSections);
    const switchToTab = vi.fn();
    vi.stubGlobal("switchToTab", switchToTab);
    (window as unknown as Record<string, unknown>).switchToTab = switchToTab;

    render(<Dashboard projectId="1" />);
    const link = await screen.findByText("Onboarding");

    // Cmd+click should NOT call switchToTab
    const ev = new MouseEvent("click", { bubbles: true, metaKey: true });
    link.dispatchEvent(ev);
    expect(switchToTab).not.toHaveBeenCalled();
  });

  it("does not render coverage box when coverage is null", async () => {
    const noCoverage = { ...baseDashboard, coverage: null };
    mockFetch(noCoverage);
    const { container } = render(<Dashboard projectId="1" />);
    // Wait for the dashboard to render (sessions table heading appears).
    await screen.findByText("Participants");
    expect(container.querySelector(".bn-coverage-box")).toBeNull();
  });
});
