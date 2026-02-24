import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { TranscriptPage } from "./TranscriptPage";
import type { TranscriptPageResponse } from "../utils/types";

// ---------------------------------------------------------------------------
// Mock data
// ---------------------------------------------------------------------------

const mockData: TranscriptPageResponse = {
  session_id: "s1",
  session_number: 1,
  duration_seconds: 78.0,
  has_media: true,
  project_name: "Test Project",
  report_filename: "bristlenose-test-project-report.html",
  speakers: [
    { code: "m1", name: "Sarah", role: "researcher" },
    { code: "p1", name: "Maya", role: "participant" },
  ],
  segments: [
    {
      speaker_code: "m1",
      start_time: 2.0,
      end_time: 10.0,
      text: "Thanks for joining me today.",
      html_text: null,
      is_moderator: true,
      is_quoted: false,
      quote_ids: [],
      segment_index: 0,
    },
    {
      speaker_code: "p1",
      start_time: 10.0,
      end_time: 19.0,
      text: "I found the dashboard pretty confusing.",
      html_text:
        '<mark class="bn-cited" data-quote-id="q-p1-10">I found the dashboard pretty confusing.</mark>',
      is_moderator: false,
      is_quoted: true,
      quote_ids: ["q-p1-10"],
      segment_index: 1,
    },
    {
      speaker_code: "m1",
      start_time: 19.0,
      end_time: 26.0,
      text: "What specifically was confusing?",
      html_text: null,
      is_moderator: true,
      is_quoted: false,
      quote_ids: [],
      segment_index: 2,
    },
    {
      speaker_code: "p1",
      start_time: 26.0,
      end_time: 39.0,
      text: "The navigation was hidden behind a hamburger menu.",
      html_text:
        '<mark class="bn-cited" data-quote-id="q-p1-26">The navigation was hidden behind a hamburger menu.</mark>',
      is_moderator: false,
      is_quoted: true,
      quote_ids: ["q-p1-26"],
      segment_index: 3,
    },
    {
      speaker_code: "p1",
      start_time: 46.0,
      end_time: 56.0,
      text: "The search was great actually.",
      html_text:
        '<mark class="bn-cited" data-quote-id="q-p1-46">The search was great actually.</mark>',
      is_moderator: false,
      is_quoted: true,
      quote_ids: ["q-p1-46"],
      segment_index: 4,
    },
  ],
  journey_labels: ["Dashboard", "Search"],
  annotations: {
    "q-p1-10": {
      label: "Dashboard",
      label_type: "section",
      sentiment: "confusion",
      participant_id: "p1",
      start_timecode: 10.0,
      end_timecode: 19.0,
      verbatim_excerpt: "I found the dashboard pretty confusing.",
      tags: [{ name: "usability", codebook_group: "UX", colour_set: "ux", colour_index: 0 }],
      deleted_badges: [],
    },
    "q-p1-26": {
      label: "Dashboard",
      label_type: "section",
      sentiment: "frustration",
      participant_id: "p1",
      start_timecode: 26.0,
      end_timecode: 39.0,
      verbatim_excerpt: "The navigation was hidden behind a hamburger menu.",
      tags: [],
      deleted_badges: [],
    },
    "q-p1-46": {
      label: "Search",
      label_type: "section",
      sentiment: "satisfaction",
      participant_id: "p1",
      start_timecode: 46.0,
      end_timecode: 56.0,
      verbatim_excerpt: "The search was great actually.",
      tags: [],
      deleted_badges: [],
    },
  },
};

// ---------------------------------------------------------------------------
// Mock API
// ---------------------------------------------------------------------------

vi.mock("../utils/api", () => ({
  getTranscript: vi.fn(),
  getSessionList: vi.fn().mockResolvedValue([]),
  putDeletedBadges: vi.fn(),
  putTags: vi.fn(),
}));

import { getTranscript } from "../utils/api";

const mockedGetTranscript = vi.mocked(getTranscript);

beforeEach(() => {
  vi.clearAllMocks();
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("TranscriptPage", () => {
  it("shows loading state", () => {
    mockedGetTranscript.mockReturnValue(new Promise(() => {})); // never resolves
    render(<TranscriptPage projectId="1" sessionId="s1" />);
    expect(screen.getByTestId("transcript-loading")).toBeTruthy();
  });

  it("shows error state on fetch failure", async () => {
    mockedGetTranscript.mockRejectedValue(new Error("Network error"));
    render(<TranscriptPage projectId="1" sessionId="s1" />);
    await waitFor(() => {
      expect(screen.getByTestId("transcript-error")).toBeTruthy();
    });
  });

  it("renders correct number of segments", async () => {
    mockedGetTranscript.mockResolvedValue(mockData);
    render(<TranscriptPage projectId="1" sessionId="s1" />);
    await waitFor(() => {
      expect(screen.getByTestId("transcript-body")).toBeTruthy();
    });
    const body = screen.getByTestId("transcript-body");
    const segments = body.querySelectorAll(".transcript-segment");
    expect(segments).toHaveLength(5);
  });

  it("moderator segments get segment-moderator class", async () => {
    mockedGetTranscript.mockResolvedValue(mockData);
    render(<TranscriptPage projectId="1" sessionId="s1" />);
    await waitFor(() => {
      expect(screen.getByTestId("segment-t-2")).toBeTruthy();
    });
    const modSeg = screen.getByTestId("segment-t-2");
    expect(modSeg.classList.contains("segment-moderator")).toBe(true);
  });

  it("quoted segments get segment-quoted class", async () => {
    mockedGetTranscript.mockResolvedValue(mockData);
    render(<TranscriptPage projectId="1" sessionId="s1" />);
    await waitFor(() => {
      expect(screen.getByTestId("segment-t-10")).toBeTruthy();
    });
    const quotedSeg = screen.getByTestId("segment-t-10");
    expect(quotedSeg.classList.contains("segment-quoted")).toBe(true);
  });

  it("quoted segments have data-quote-ids attribute", async () => {
    mockedGetTranscript.mockResolvedValue(mockData);
    render(<TranscriptPage projectId="1" sessionId="s1" />);
    await waitFor(() => {
      expect(screen.getByTestId("segment-t-10")).toBeTruthy();
    });
    const quotedSeg = screen.getByTestId("segment-t-10");
    expect(quotedSeg.getAttribute("data-quote-ids")).toBe("q-p1-10");
  });

  it("annotations render only on first segment per quote", async () => {
    mockedGetTranscript.mockResolvedValue(mockData);
    render(<TranscriptPage projectId="1" sessionId="s1" />);
    await waitFor(() => {
      expect(screen.getByTestId("annotation-q-p1-10")).toBeTruthy();
    });
    // Each quote ID should have exactly one annotation rendered
    expect(screen.getByTestId("annotation-q-p1-10")).toBeTruthy();
    expect(screen.getByTestId("annotation-q-p1-26")).toBeTruthy();
  });

  it("renders TimecodeLink for media sessions", async () => {
    mockedGetTranscript.mockResolvedValue(mockData);
    render(<TranscriptPage projectId="1" sessionId="s1" />);
    await waitFor(() => {
      expect(screen.getByTestId("transcript-body")).toBeTruthy();
    });
    const body = screen.getByTestId("transcript-body");
    const timecodeLinks = body.querySelectorAll("a.timecode");
    expect(timecodeLinks.length).toBeGreaterThan(0);
  });

  it("renders plain span timecodes for non-media sessions", async () => {
    const noMedia = { ...mockData, has_media: false };
    mockedGetTranscript.mockResolvedValue(noMedia);
    render(<TranscriptPage projectId="1" sessionId="s1" />);
    await waitFor(() => {
      expect(screen.getByTestId("transcript-body")).toBeTruthy();
    });
    const body = screen.getByTestId("transcript-body");
    const timecodeLinks = body.querySelectorAll("a.timecode");
    expect(timecodeLinks).toHaveLength(0);
    const timecodeSpans = body.querySelectorAll("span.timecode");
    expect(timecodeSpans.length).toBeGreaterThan(0);
  });

  it("has data-testid attributes on key elements", async () => {
    mockedGetTranscript.mockResolvedValue(mockData);
    render(<TranscriptPage projectId="1" sessionId="s1" />);
    await waitFor(() => {
      expect(screen.getByTestId("transcript-body")).toBeTruthy();
    });
    expect(screen.getByTestId("transcript-body")).toBeTruthy();
  });

  it("segments have correct data attributes for player.js", async () => {
    mockedGetTranscript.mockResolvedValue(mockData);
    render(<TranscriptPage projectId="1" sessionId="s1" />);
    await waitFor(() => {
      expect(screen.getByTestId("segment-t-10")).toBeTruthy();
    });
    const seg = screen.getByTestId("segment-t-10");
    expect(seg.getAttribute("data-participant")).toBe("p1");
    expect(seg.getAttribute("data-start-seconds")).toBe("10");
    expect(seg.getAttribute("data-end-seconds")).toBe("19");
  });

  it("renders journey header when journey_labels is non-empty", async () => {
    mockedGetTranscript.mockResolvedValue(mockData);
    render(<TranscriptPage projectId="1" sessionId="s1" />);
    await waitFor(() => {
      expect(screen.getByTestId("transcript-journey-header")).toBeTruthy();
    });
    const chain = screen.getByTestId("transcript-journey-chain");
    expect(chain.textContent).toContain("Dashboard");
    expect(chain.textContent).toContain("Search");
  });

  it("shows sticky header without journey chain when no section annotations exist", async () => {
    mockedGetTranscript.mockResolvedValue({
      ...mockData,
      journey_labels: [],
      annotations: {},
      segments: mockData.segments.map((s) => ({
        ...s,
        is_quoted: false,
        quote_ids: [],
      })),
    });
    render(<TranscriptPage projectId="1" sessionId="s1" />);
    await waitFor(() => {
      expect(screen.getByTestId("transcript-body")).toBeTruthy();
    });
    // Sticky header always present (acts as page title / session selector)
    expect(screen.getByTestId("transcript-journey-header")).toBeTruthy();
    // But journey chain is hidden when no journey data
    expect(screen.queryByTestId("transcript-journey-chain")).toBeNull();
  });

  // ── Session roles line ──────────────────────────────────────────────

  it("renders moderator in roles line", async () => {
    mockedGetTranscript.mockResolvedValue(mockData);
    render(<TranscriptPage projectId="1" sessionId="s1" />);
    await waitFor(() => {
      expect(screen.getByTestId("transcript-roles")).toBeTruthy();
    });
    const roles = screen.getByTestId("transcript-roles");
    expect(roles.textContent).toContain("Moderator");
    expect(roles.textContent).toContain("m1");
    expect(roles.textContent).toContain("Sarah");
  });

  it("does not render roles line when only participants", async () => {
    const participantsOnly: TranscriptPageResponse = {
      ...mockData,
      speakers: [
        { code: "p1", name: "Maya", role: "participant" },
        { code: "p2", name: "Alex", role: "participant" },
      ],
    };
    mockedGetTranscript.mockResolvedValue(participantsOnly);
    render(<TranscriptPage projectId="1" sessionId="s1" />);
    await waitFor(() => {
      expect(screen.getByTestId("transcript-body")).toBeTruthy();
    });
    expect(screen.queryByTestId("transcript-roles")).toBeNull();
  });

  it("renders moderator and observer together", async () => {
    const withObserver: TranscriptPageResponse = {
      ...mockData,
      speakers: [
        { code: "m1", name: "Sarah", role: "researcher" },
        { code: "p1", name: "Maya", role: "participant" },
        { code: "o1", name: "Peter", role: "observer" },
      ],
    };
    mockedGetTranscript.mockResolvedValue(withObserver);
    render(<TranscriptPage projectId="1" sessionId="s1" />);
    await waitFor(() => {
      expect(screen.getByTestId("transcript-roles")).toBeTruthy();
    });
    const text = screen.getByTestId("transcript-roles").textContent ?? "";
    expect(text).toContain("Moderator");
    expect(text).toContain("Sarah");
    expect(text).toContain("observer");
    expect(text).toContain("Peter");
    // "observer" should be lowercase (not first group)
    expect(text).not.toMatch(/Observer/);
  });

  it("pluralises Moderators and observers", async () => {
    const multi: TranscriptPageResponse = {
      ...mockData,
      speakers: [
        { code: "m1", name: "Sarah", role: "researcher" },
        { code: "m2", name: "James", role: "researcher" },
        { code: "p1", name: "Maya", role: "participant" },
        { code: "o1", name: "Peter", role: "observer" },
        { code: "o2", name: "Alex", role: "observer" },
      ],
    };
    mockedGetTranscript.mockResolvedValue(multi);
    render(<TranscriptPage projectId="1" sessionId="s1" />);
    await waitFor(() => {
      expect(screen.getByTestId("transcript-roles")).toBeTruthy();
    });
    const text = screen.getByTestId("transcript-roles").textContent ?? "";
    expect(text).toContain("Moderators");
    expect(text).toContain("observers");
  });

  it("capitalises Observer when no moderator present", async () => {
    const observerOnly: TranscriptPageResponse = {
      ...mockData,
      speakers: [
        { code: "p1", name: "Maya", role: "participant" },
        { code: "o1", name: "Peter", role: "observer" },
      ],
    };
    mockedGetTranscript.mockResolvedValue(observerOnly);
    render(<TranscriptPage projectId="1" sessionId="s1" />);
    await waitFor(() => {
      expect(screen.getByTestId("transcript-roles")).toBeTruthy();
    });
    const text = screen.getByTestId("transcript-roles").textContent ?? "";
    expect(text).toMatch(/^Observer/);
  });

  it("uses Oxford comma with 3+ in a group", async () => {
    const threeObs: TranscriptPageResponse = {
      ...mockData,
      speakers: [
        { code: "p1", name: "Maya", role: "participant" },
        { code: "o1", name: "A", role: "observer" },
        { code: "o2", name: "B", role: "observer" },
        { code: "o3", name: "C", role: "observer" },
      ],
    };
    mockedGetTranscript.mockResolvedValue(threeObs);
    render(<TranscriptPage projectId="1" sessionId="s1" />);
    await waitFor(() => {
      expect(screen.getByTestId("transcript-roles")).toBeTruthy();
    });
    const text = screen.getByTestId("transcript-roles").textContent ?? "";
    // Should have Oxford comma: "A, B, and C"
    expect(text).toContain(", and");
  });

  it("renders full journey with revisits (not deduplicated)", async () => {
    const revisitData: TranscriptPageResponse = {
      ...mockData,
      journey_labels: ["Dashboard", "Search"],
      segments: [
        {
          speaker_code: "p1", start_time: 10.0, end_time: 19.0,
          text: "The dashboard is confusing.",
          html_text: null, is_moderator: false, is_quoted: true,
          quote_ids: ["q-p1-10"], segment_index: 0,
        },
        {
          speaker_code: "p1", start_time: 30.0, end_time: 39.0,
          text: "Search works well.",
          html_text: null, is_moderator: false, is_quoted: true,
          quote_ids: ["q-p1-30"], segment_index: 1,
        },
        {
          speaker_code: "p1", start_time: 50.0, end_time: 59.0,
          text: "Back to the dashboard, still confused.",
          html_text: null, is_moderator: false, is_quoted: true,
          quote_ids: ["q-p1-50"], segment_index: 2,
        },
      ],
      annotations: {
        "q-p1-10": {
          label: "Dashboard", label_type: "section", sentiment: "confusion",
          participant_id: "p1", start_timecode: 10.0, end_timecode: 19.0,
          verbatim_excerpt: "The dashboard is confusing.",
          tags: [], deleted_badges: [],
        },
        "q-p1-30": {
          label: "Search", label_type: "section", sentiment: "satisfaction",
          participant_id: "p1", start_timecode: 30.0, end_timecode: 39.0,
          verbatim_excerpt: "Search works well.",
          tags: [], deleted_badges: [],
        },
        "q-p1-50": {
          label: "Dashboard", label_type: "section", sentiment: "confusion",
          participant_id: "p1", start_timecode: 50.0, end_timecode: 59.0,
          verbatim_excerpt: "Back to the dashboard, still confused.",
          tags: [], deleted_badges: [],
        },
      },
    };
    mockedGetTranscript.mockResolvedValue(revisitData);
    render(<TranscriptPage projectId="1" sessionId="s1" />);
    await waitFor(() => {
      expect(screen.getByTestId("transcript-journey-chain")).toBeTruthy();
    });
    const chain = screen.getByTestId("transcript-journey-chain");
    const labels = chain.querySelectorAll(".bn-journey-label");
    // Should be 3 labels (Dashboard → Search → Dashboard), not 2
    expect(labels).toHaveLength(3);
    expect(labels[0].textContent).toBe("Dashboard");
    expect(labels[1].textContent).toBe("Search");
    expect(labels[2].textContent).toBe("Dashboard");
  });

  it("shows badge only when speaker has no name", async () => {
    const noName: TranscriptPageResponse = {
      ...mockData,
      speakers: [
        { code: "m1", name: "m1", role: "researcher" },
        { code: "p1", name: "Maya", role: "participant" },
      ],
    };
    mockedGetTranscript.mockResolvedValue(noName);
    render(<TranscriptPage projectId="1" sessionId="s1" />);
    await waitFor(() => {
      expect(screen.getByTestId("transcript-roles")).toBeTruthy();
    });
    const roles = screen.getByTestId("transcript-roles");
    // Should NOT have a separate name span when name === code
    const nameSpans = roles.querySelectorAll(".bn-transcript-roles__name");
    expect(nameSpans).toHaveLength(0);
  });
});
