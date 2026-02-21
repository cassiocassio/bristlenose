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
    },
    {
      speaker_code: "p1",
      start_time: 46.0,
      end_time: 56.0,
      text: "The search was great actually.",
      html_text: null,
      is_moderator: false,
      is_quoted: false,
      quote_ids: [],
    },
  ],
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
  },
};

// ---------------------------------------------------------------------------
// Mock API
// ---------------------------------------------------------------------------

vi.mock("../utils/api", () => ({
  getTranscript: vi.fn(),
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

  it("speaker names appear in heading", async () => {
    mockedGetTranscript.mockResolvedValue(mockData);
    render(<TranscriptPage projectId="1" sessionId="s1" />);
    await waitFor(() => {
      expect(screen.getByTestId("transcript-heading")).toBeTruthy();
    });
    const heading = screen.getByTestId("transcript-heading");
    expect(heading.textContent).toContain("Sarah");
    expect(heading.textContent).toContain("Maya");
  });

  it("has data-testid attributes on key elements", async () => {
    mockedGetTranscript.mockResolvedValue(mockData);
    render(<TranscriptPage projectId="1" sessionId="s1" />);
    await waitFor(() => {
      expect(screen.getByTestId("transcript-body")).toBeTruthy();
    });
    expect(screen.getByTestId("transcript-heading")).toBeTruthy();
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
});
