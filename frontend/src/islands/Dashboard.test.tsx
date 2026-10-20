import { describe, it, expect, vi, beforeEach } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { NavigateFunction } from "react-router-dom";
import { installNavigationShims } from "../shims/navigation";
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

describe("Dashboard stat-card destinations", () => {
  // The rename to Signals moved the TAB_ROUTES key and left this caller behind:
  // `target: "analysis:..."` looked up a tab the map no longer had, took the
  // `?? "/report/"` fallback, and landed the researcher back on the dashboard
  // they clicked from. No test asserted where a stat card GOES, so 0.30.0
  // shipped it. Assert the destination, not the string.
  it("every stat card reaches the lens its target names", async () => {
    mockFetch(baseDashboard);
    const { container } = render(<Dashboard projectId="1" />);
    await screen.findByText("Transcript coverage");

    const links = container.querySelectorAll<HTMLAnchorElement>("a[data-stat-link]");
    expect(links.length).toBeGreaterThan(0);

    for (const link of links) {
      const target = link.dataset.statLink ?? "";
      const [tab] = target.split(":");
      const href = link.getAttribute("href") ?? "";
      if (tab === "project") {
        expect(href).toMatch(/^\/report\/(#|$)/);
        continue;
      }
      // An unknown tab silently resolves to the project dashboard. A card that
      // names a lens must not land there.
      expect(
        /^\/report\/(#|$)/.test(href),
        `stat card "${target}" resolves to "${href}" — the dashboard it was clicked from`,
      ).toBe(false);
      expect(href).toContain(`/report/${tab}/`);
    }
  });

  it("the AI-tags card opens the Signals lens", async () => {
    mockFetch(baseDashboard);
    const { container } = render(<Dashboard projectId="1" />);
    await screen.findByText("Transcript coverage");
    const card = container.querySelector<HTMLAnchorElement>(
      'a[data-stat-link^="signals:"]',
    );
    expect(card).toBeTruthy();
    expect(card!.getAttribute("href")).toBe("/report/signals/#section-x-sentiment");
  });
});

describe("Dashboard sessions table — the person picker (design-people.md §J8.7)", () => {
  it("each speaker is the picker's button, and a write re-reads the dashboard", async () => {
    mockFetch(baseDashboard);
    render(<Dashboard projectId="1" />);
    await waitFor(() => expect(screen.getByTestId("bn-speaker-trigger-m1")).toBeTruthy());
    expect(screen.getByTestId("bn-speaker-trigger-p1").closest(".bn-session-speakers")).not.toBeNull();

    mockFetch(baseDashboard);
    const before = (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls.length;
    window.dispatchEvent(new CustomEvent("bn:speakers-written"));
    await waitFor(() =>
      expect((globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls.length).toBe(before + 1),
    );
    expect(String((globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls[before][0])).toContain("/dashboard");
  });
});

describe("Dashboard sessions table — row click (R65)", () => {
  const navigate = vi.fn();
  beforeEach(() => {
    navigate.mockClear();
    installNavigationShims(navigate as unknown as NavigateFunction, () => {});
  });
  const row = () => screen.getByText("#1").closest("tr") as HTMLElement;

  it("a click anywhere on a row opens that session's transcript", async () => {
    mockFetch(baseDashboard);
    render(<Dashboard projectId="1" />);
    await screen.findByText("#1");
    fireEvent.click(row().querySelector(".bn-session-duration")!);
    expect(navigate).toHaveBeenCalledWith("/report/sessions/s1", undefined);
  });

  it("a control inside the row keeps its own click", async () => {
    mockFetch(baseDashboard);
    render(<Dashboard projectId="1" />);
    await screen.findByText("#1");
    // The media link opens the player; the #N link is the keyboard route.
    fireEvent.click(screen.getByText("session1.mp4"));
    fireEvent.click(screen.getByText("#1"));
    expect(navigate).not.toHaveBeenCalled();
  });

  it("a drag that selected text is a selection, not a click", async () => {
    mockFetch(baseDashboard);
    render(<Dashboard projectId="1" />);
    await screen.findByText("#1");
    const cell = row().querySelector(".bn-session-duration")!;
    const range = document.createRange();
    range.selectNodeContents(cell);
    window.getSelection()!.removeAllRanges();
    window.getSelection()!.addRange(range);
    fireEvent.click(cell);
    window.getSelection()!.removeAllRanges();
    expect(navigate).not.toHaveBeenCalled();
  });
});

describe("Dashboard featured quote", () => {
  it("links its speaker to the paragraph the transcript can land on", async () => {
    mockFetch({
      ...baseDashboard,
      featured_quotes: [
        {
          dom_id: "q-p1-123", text: "It took three weeks", participant_id: "p1", session_id: "s1",
          speaker_name: "Jordan", start_timecode: 123.6, end_timecode: 130, sentiment: null, intensity: 1,
          researcher_context: null, rank: 1, has_media: false, is_starred: false, is_hidden: false,
        },
      ],
    });
    const { container } = render(<Dashboard projectId="1" />);
    await waitFor(() => expect(container.querySelector(".bn-featured-quote .speaker-link")).not.toBeNull());
    // `t-<seconds>`, the id TranscriptPage gives a paragraph; `t-s1-123` matched nothing and the
    // page opened at the top.
    expect(container.querySelector(".bn-featured-quote .speaker-link")?.getAttribute("href")).toBe(
      "/report/sessions/s1#t-123",
    );
  });
});
