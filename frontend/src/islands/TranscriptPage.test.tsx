import { describe, it, expect, vi, beforeEach, afterAll } from "vitest";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { bumpRefreshKey, resetLastRunStore } from "../contexts/LastRunStore";
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
      words: null,
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
      words: null,
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
      words: null,
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
      words: null,
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
      words: null,
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
  postParagraphSplit: vi.fn().mockResolvedValue({ id: 1 }),
  postParagraphJoin: vi.fn().mockResolvedValue({ id: 2 }),
  deleteParagraphEdit: vi.fn().mockResolvedValue(undefined),
}));

// Mock embedded detection — default false (browser); flip per-test. The house
// pattern (SidebarLayout.test.tsx): mock the module, never toggle the global —
// isEmbedded() memoises on first call.
let mockEmbedded = false;
vi.mock("../utils/embedded", () => ({
  isEmbedded: () => mockEmbedded,
}));

import { getTranscript, getSessionList, postParagraphJoin, postParagraphSplit } from "../utils/api";
import { navigateTo } from "../shims/navigation";

// The gutter's marks navigate through the shim (utils/quotesLink.ts): the page renders without a router here.
vi.mock("../shims/navigation", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../shims/navigation")>()),
  navigateTo: vi.fn(),
}));

const mockedGetTranscript = vi.mocked(getTranscript);
const mockedGetSessionList = vi.mocked(getSessionList);

// jsdom has no scrollIntoView; the journey chain centres its active label with it.
const realScrollIntoView = Element.prototype.scrollIntoView;
const scrolledInto: string[] = [];

beforeEach(() => {
  vi.clearAllMocks();
  mockEmbedded = false;
  mockedGetSessionList.mockResolvedValue([]);
  scrolledInto.length = 0;
  Element.prototype.scrollIntoView = function (this: Element) {
    scrolledInto.push(this.id);
  };
});

afterAll(() => {
  Element.prototype.scrollIntoView = realScrollIntoView;
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

  it("draws an inaudible segment as a gap, never as words", async () => {
    const gap = {
      ...mockData.segments[3],
      start_time: 39.0,
      end_time: 46.0,
      text: "",
      html_text: null,
      is_quoted: false,
      quote_ids: [],
      segment_index: 4,
      inaudible: true,
    };
    mockedGetTranscript.mockResolvedValue({
      ...mockData,
      segments: [...mockData.segments.slice(0, 4), gap, mockData.segments[4]],
    });
    render(<TranscriptPage projectId="1" sessionId="s1" />);
    await waitFor(() => {
      expect(screen.getByTestId("segment-t-39")).toBeTruthy();
    });
    const marker = screen.getByTestId("segment-t-39").querySelector(".segment-inaudible");
    expect(marker?.getAttribute("contenteditable")).toBe("false");
    expect(marker?.textContent).toBe("Inaudible");
    expect(screen.getByTestId("segment-t-26").querySelector(".segment-inaudible")).toBeNull();
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

  // ── Participant identity in the sticky header ───────────────────────

  it("names participants in the sticky header, not the transcript body", async () => {
    mockedGetTranscript.mockResolvedValue(mockData);
    render(<TranscriptPage projectId="1" sessionId="s1" />);
    await waitFor(() => {
      expect(screen.getByTestId("transcript-header-people")).toBeTruthy();
    });

    // The header is sticky, so "who is p1" survives scrolling.
    const people = screen.getByTestId("transcript-header-people");
    expect(people.textContent).toContain("p1");
    expect(people.textContent).toContain("Maya");
    // Moderators stay in the roles line below — the header is participants only.
    expect(people.textContent).not.toContain("m1");

    // Every segment badge is code-only, including the speaker's first turn:
    // a name there would overflow the fixed 2.2rem badge column.
    const body = screen.getByTestId("transcript-body");
    expect(body.querySelector(".bn-speaker-badge-name")).toBeNull();
    expect(body.textContent).not.toContain("Maya");
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
          quote_ids: ["q-p1-10"], segment_index: 0, words: null,
        },
        {
          speaker_code: "p1", start_time: 30.0, end_time: 39.0,
          text: "Search works well.",
          html_text: null, is_moderator: false, is_quoted: true,
          quote_ids: ["q-p1-30"], segment_index: 1, words: null,
        },
        {
          speaker_code: "p1", start_time: 50.0, end_time: 59.0,
          text: "Back to the dashboard, still confused.",
          html_text: null, is_moderator: false, is_quoted: true,
          quote_ids: ["q-p1-50"], segment_index: 2, words: null,
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

  // ── Word-level highlighting ─────────────────────────────────────────

  it("renders word spans when words data is present", async () => {
    const withWords: TranscriptPageResponse = {
      ...mockData,
      segments: [
        {
          speaker_code: "p1",
          start_time: 10.0,
          end_time: 19.0,
          text: "I found it confusing.",
          html_text: null,
          is_moderator: false,
          is_quoted: false,
          quote_ids: [],
          segment_index: 0,
          words: [
            { text: "I", start: 10.0, end: 10.5 },
            { text: "found", start: 10.5, end: 11.2 },
            { text: "it", start: 11.2, end: 11.6 },
            { text: "confusing.", start: 11.6, end: 12.8 },
          ],
        },
      ],
    };
    mockedGetTranscript.mockResolvedValue(withWords);
    render(<TranscriptPage projectId="1" sessionId="s1" />);
    await waitFor(() => {
      expect(screen.getByTestId("transcript-body")).toBeTruthy();
    });
    const body = screen.getByTestId("transcript-body");
    const wordSpans = body.querySelectorAll(".transcript-word");
    expect(wordSpans).toHaveLength(4);
    expect(wordSpans[0].textContent).toBe("I ");
    expect(wordSpans[0].getAttribute("data-start")).toBe("10");
    expect(wordSpans[0].getAttribute("data-end")).toBe("10.5");
    expect(wordSpans[3].textContent).toBe("confusing.");
    expect(wordSpans[3].getAttribute("data-start")).toBe("11.6");
    expect(wordSpans[3].getAttribute("data-end")).toBe("12.8");
  });

  it("falls back to plain text when words is null", async () => {
    mockedGetTranscript.mockResolvedValue(mockData);
    render(<TranscriptPage projectId="1" sessionId="s1" />);
    await waitFor(() => {
      expect(screen.getByTestId("transcript-body")).toBeTruthy();
    });
    const body = screen.getByTestId("transcript-body");
    // No word spans — words is null on all segments
    const wordSpans = body.querySelectorAll(".transcript-word");
    expect(wordSpans).toHaveLength(0);
    // Plain text still renders
    expect(body.textContent).toContain("Thanks for joining me today.");
  });

  it("without word timings, draws the quote's words as spans and keeps the text exact", async () => {
    const emptyWords: TranscriptPageResponse = {
      ...mockData,
      segments: [
        {
          speaker_code: "p1",
          start_time: 10.0,
          end_time: 19.0,
          text: "I found the dashboard pretty confusing.",
          html_text:
            '<mark class="bn-cited">I found the dashboard pretty confusing.</mark>',
          is_moderator: false,
          is_quoted: true,
          quote_ids: ["q-p1-10"],
          segment_index: 0,
          words: [],
        },
      ],
    };
    mockedGetTranscript.mockResolvedValue(emptyWords);
    render(<TranscriptPage projectId="1" sessionId="s1" />);
    await waitFor(() => {
      expect(screen.getByTestId("transcript-body")).toBeTruthy();
    });
    const body = screen.getByTestId("transcript-body");
    // No word timings: no timed word spans, and not the server's whole-paragraph <mark> either.
    // The quote's words are spans carrying the quote (docs/design-transcript-gutter.md), and the
    // spaces between stay text, so the paragraph's text — what copy and the caret read — is exact.
    expect(body.querySelectorAll(".transcript-word")).toHaveLength(0);
    expect(body.querySelectorAll("mark.bn-cited")).toHaveLength(0);
    expect(body.querySelectorAll('[data-q="q-p1-10"]').length).toBeGreaterThan(0);
    expect(body.querySelector(".segment-body")!.textContent).toBe("I found the dashboard pretty confusing.");
  });

  it("skips html_text quote marks when words are present", async () => {
    const wordsWithHtml: TranscriptPageResponse = {
      ...mockData,
      segments: [
        {
          speaker_code: "p1",
          start_time: 10.0,
          end_time: 19.0,
          text: "I found it confusing.",
          html_text:
            '<mark class="bn-cited">I found it confusing.</mark>',
          is_moderator: false,
          is_quoted: true,
          quote_ids: ["q-p1-10"],
          segment_index: 0,
          words: [
            { text: "I", start: 10.0, end: 10.5 },
            { text: "found", start: 10.5, end: 11.2 },
            { text: "it", start: 11.2, end: 11.6 },
            { text: "confusing.", start: 11.6, end: 12.8 },
          ],
        },
      ],
    };
    mockedGetTranscript.mockResolvedValue(wordsWithHtml);
    render(<TranscriptPage projectId="1" sessionId="s1" />);
    await waitFor(() => {
      expect(screen.getByTestId("transcript-body")).toBeTruthy();
    });
    const body = screen.getByTestId("transcript-body");
    // Word spans rendered instead of html_text <mark>
    const wordSpans = body.querySelectorAll(".transcript-word");
    expect(wordSpans).toHaveLength(4);
    const marks = body.querySelectorAll("mark.bn-cited");
    expect(marks).toHaveLength(0);
  });

  // ── Sticky-header session selector: embedded gating ──────────────────
  // The native macOS build replaces session switching with the titlebar
  // popover; the browser keeps the dropdown. BOTH directions asserted — a
  // negative-only test on either side passes on an inverted gate
  // (design-sessions-popover-navigation.md, review finding on the SPA tests).

  const twoSessions = [
    { session_id: "s1", session_number: 1, session_date: null, speakers: [] },
    { session_id: "s2", session_number: 2, session_date: null, speakers: [] },
  ];

  it("browser keeps the session dropdown when several sessions exist", async () => {
    mockEmbedded = false;
    mockedGetSessionList.mockResolvedValue(twoSessions);
    mockedGetTranscript.mockResolvedValue(mockData);
    render(<TranscriptPage projectId="1" sessionId="s1" />);
    await waitFor(() => {
      expect(screen.getByTestId("session-selector")).toBeTruthy();
    });
    expect(screen.queryByTestId("session-label")).toBeNull();
  });

  it("embedded drops the dropdown but KEEPS the label naming the session", async () => {
    mockEmbedded = true;
    mockedGetSessionList.mockResolvedValue(twoSessions);
    mockedGetTranscript.mockResolvedValue(mockData);
    render(<TranscriptPage projectId="1" sessionId="s1" />);
    await waitFor(() => {
      expect(screen.getByTestId("transcript-body")).toBeTruthy();
    });
    // The disclosure is gone — the native popover owns switching…
    expect(screen.queryByTestId("session-selector")).toBeNull();
    // …but the label stays: it is the only thing naming the session here.
    expect(screen.getByTestId("session-label").textContent).toContain("Session 1");
  });
});

describe("TranscriptPage — the person picker (design-people.md §J8.7)", () => {
  it("names the speaker from the header, the roles line or any paragraph", async () => {
    mockedGetTranscript.mockResolvedValue(mockData);
    render(<TranscriptPage projectId="1" sessionId="s1" />);
    await waitFor(() => expect(screen.getByTestId("transcript-roles")).toBeTruthy());
    const header = screen.getByTestId("transcript-header-people");
    const roles = screen.getByTestId("transcript-roles");
    // Header and roles line: reachable by Tab.
    expect(header.querySelector('[data-testid="bn-speaker-trigger-p1"]')?.getAttribute("tabindex")).toBe("0");
    expect(roles.querySelector('[data-testid="bn-speaker-trigger-m1"]')?.getAttribute("tabindex")).toBe("0");
    // Paragraphs: a click target each, never a Tab stop each.
    const paragraphs = document.querySelectorAll(".segment-speaker .bn-person-picker-trigger");
    expect(paragraphs.length).toBeGreaterThan(0);
    paragraphs.forEach((b) => expect(b.getAttribute("tabindex")).toBe("-1"));
  });

  it("re-reads the transcript when a speaker write has landed", async () => {
    mockedGetTranscript.mockResolvedValue(mockData);
    render(<TranscriptPage projectId="1" sessionId="s1" />);
    await waitFor(() => expect(screen.getByTestId("transcript-roles")).toBeTruthy());
    const before = mockedGetTranscript.mock.calls.length;
    window.dispatchEvent(new CustomEvent("bn:speakers-written"));
    await waitFor(() => expect(mockedGetTranscript.mock.calls.length).toBe(before + 1));
  });
});


describe("TranscriptPage — split and join (design-transcript-editing.md, stage 1)", () => {
  const bodyOf = (i: number) =>
    screen.getByTestId("transcript-body").querySelectorAll<HTMLElement>(".segment-body")[i];
  const caret = (el: HTMLElement, offset: number) => {
    const range = document.createRange();
    range.setStart(el.firstChild!.firstChild ?? el.firstChild!, offset);
    range.collapse(true);
    window.getSelection()!.removeAllRanges();
    window.getSelection()!.addRange(range);
  };

  it("Return at a caret splits the paragraph there, counted in words", async () => {
    mockedGetTranscript.mockResolvedValue(mockData);
    render(<TranscriptPage projectId="1" sessionId="s1" />);
    await waitFor(() => expect(screen.getByTestId("transcript-body")).toBeTruthy());
    const body = bodyOf(0);
    caret(body, "Thanks for ".length);
    fireEvent.keyDown(body, { key: "Enter" });
    await waitFor(() => expect(postParagraphSplit).toHaveBeenCalledWith("s1", 0, 2, "joining me today."));
  });

  it("the whole transcript is one editable region, so a selection can run across paragraphs", async () => {
    mockedGetTranscript.mockResolvedValue(mockData);
    render(<TranscriptPage projectId="1" sessionId="s1" />);
    await waitFor(() => expect(screen.getByTestId("transcript-body")).toBeTruthy());
    const section = screen.getByTestId("transcript-body");
    expect(section.getAttribute("contenteditable")).toBe("true");
    // No paragraph is an editing region of its own: a selection could not leave one.
    expect(bodyOf(0).getAttribute("contenteditable")).toBeNull();
    expect(bodyOf(1).getAttribute("contenteditable")).toBeNull();
    // Timecodes, badges and the margin take no caret.
    for (const sel of [".segment-timecode-cell", ".segment-speaker"]) {
      expect(section.querySelector(sel)?.getAttribute("contenteditable")).toBe("false");
    }
  });

  it("Return in a selection spanning paragraphs splits nothing", async () => {
    mockedGetTranscript.mockResolvedValue(mockData);
    render(<TranscriptPage projectId="1" sessionId="s1" />);
    await waitFor(() => expect(screen.getByTestId("transcript-body")).toBeTruthy());
    const range = document.createRange();
    range.setStart(bodyOf(0).firstChild!, 2);
    range.setEnd(bodyOf(1), 1);
    window.getSelection()!.removeAllRanges();
    window.getSelection()!.addRange(range);
    fireEvent.keyDown(bodyOf(0), { key: "Enter" });
    expect(postParagraphSplit).not.toHaveBeenCalled();
  });

  it("typing is refused: the words are the recording's", async () => {
    mockedGetTranscript.mockResolvedValue(mockData);
    render(<TranscriptPage projectId="1" sessionId="s1" />);
    await waitFor(() => expect(screen.getByTestId("transcript-body")).toBeTruthy());
    const event = new InputEvent("beforeinput", { bubbles: true, cancelable: true, data: "x" });
    bodyOf(0).dispatchEvent(event);
    expect(event.defaultPrevented).toBe(true);
  });

  it("a field inside an island still takes typing and Backspace; a timecode keeps its Enter", async () => {
    mockedGetTranscript.mockResolvedValue(mockData);
    render(<TranscriptPage projectId="1" sessionId="s1" />);
    await waitFor(() => expect(screen.getByTestId("transcript-body")).toBeTruthy());
    // The inline picker's name field sits in the speaker island.
    const field = document.createElement("input");
    document.querySelector(".segment-speaker")!.appendChild(field);
    const typed = new InputEvent("beforeinput", { bubbles: true, cancelable: true, data: "x" });
    field.dispatchEvent(typed);
    expect(typed.defaultPrevented).toBe(false);
    expect(fireEvent.keyDown(field, { key: "Backspace" })).toBe(true);
    const link = document.querySelector(".segment-timecode-cell a, .segment-timecode-cell .timecode")!;
    expect(fireEvent.keyDown(link, { key: "Enter" })).toBe(true);
    expect(postParagraphSplit).not.toHaveBeenCalled();
    expect(postParagraphJoin).not.toHaveBeenCalled();
  });

  it("an unknown session language is no language, not the interface's", async () => {
    mockedGetTranscript.mockResolvedValue({ ...mockData, language: null });
    render(<TranscriptPage projectId="1" sessionId="s1" />);
    await waitFor(() => expect(screen.getByTestId("transcript-body")).toBeTruthy());
    expect(bodyOf(0).getAttribute("lang")).toBe("");
  });

  it("marks the paragraphs that begin a sentence, and gives them the session's language", async () => {
    const p = mockData.segments[1];
    const split = {
      ...mockData,
      language: "tr",
      segments: [
        { ...p, text: "so when it's fermenting the air" },
        { ...p, start_time: 15, text: "it's kind of a simple solution." },
        { ...p, start_time: 17, text: "it keeps the air out" },
      ],
    };
    mockedGetTranscript.mockResolvedValue(split);
    render(<TranscriptPage projectId="1" sessionId="s1" />);
    await waitFor(() => expect(screen.getByTestId("transcript-body")).toBeTruthy());
    // First paragraph: a start. Second carries on mid-sentence. Third follows a full stop.
    expect([0, 1, 2].map((i) => bodyOf(i).classList.contains("bn-sentence-start"))).toEqual([true, false, true]);
    expect(bodyOf(0).getAttribute("lang")).toBe("tr");
  });

  it("Backspace at the start joins only the same speaker's paragraph above", async () => {
    const twoInARow = { ...mockData, segments: [mockData.segments[1], { ...mockData.segments[1], start_time: 15, text: "And slow." }] };
    mockedGetTranscript.mockResolvedValue(twoInARow);
    render(<TranscriptPage projectId="1" sessionId="s1" />);
    await waitFor(() => expect(screen.getByTestId("transcript-body")).toBeTruthy());
    const second = bodyOf(1);
    caret(second, 0);
    fireEvent.keyDown(second, { key: "Backspace" });
    await waitFor(() => expect(postParagraphJoin).toHaveBeenCalledWith("s1", 1, "And slow."));
  });
});

describe("TranscriptPage copy", () => {
  it("a drag across paragraphs copies the house transcript format", async () => {
    mockedGetTranscript.mockResolvedValue(mockData);
    render(<TranscriptPage projectId="1" sessionId="s1" />);
    await waitFor(() => expect(screen.getByTestId("transcript-body")).toBeTruthy());
    const body = screen.getByTestId("transcript-body");
    const paras = body.querySelectorAll<HTMLElement>(".segment-body");
    const range = document.createRange();
    range.setStart(paras[0], 0);
    range.setEnd(paras[1], paras[1].childNodes.length);
    const sel = window.getSelection()!;
    sel.removeAllRanges();
    sel.addRange(range);
    const data = new Map<string, string>();
    fireEvent.copy(body, {
      clipboardData: { setData: (type: string, v: string) => data.set(type, v) },
    });
    expect(data.get("text/plain")).toMatch(/^\*\*`\[00:02\]` m1\*\* Thanks for joining me today\.\n\n\*\*`\[/);
    expect(data.get("text/html")).toMatch(/font-family:Menlo,Consolas,monospace[^>]*color:#007aff">.*00:02.*<\/span> <b>m1<\/b> Thanks/);
  });
});

describe("TranscriptPage — new data while it is open (progressive lenses)", () => {
  // Before the session's quotes: no highlights, no margin, no journey.
  const beforeQuotes: TranscriptPageResponse = {
    ...mockData,
    journey_labels: [],
    annotations: {},
    segments: mockData.segments.map((s) => ({
      ...s, is_quoted: false, quote_ids: [], html_text: null,
    })),
  };

  beforeEach(() => {
    resetLastRunStore();
    window.location.hash = "";
    // `addRange` does nothing while a range exists, and an earlier test leaves one.
    window.getSelection()?.removeAllRanges();
  });

  async function openThenBump(after: TranscriptPageResponse) {
    mockedGetTranscript.mockResolvedValueOnce(beforeQuotes).mockResolvedValue(after);
    render(<TranscriptPage projectId="1" sessionId="s1" />);
    await waitFor(() => expect(screen.getByTestId("transcript-body")).toBeTruthy());
    act(() => bumpRefreshKey());
  }

  it("re-reads when the report moves on, and shows the quotes that arrived", async () => {
    await openThenBump(mockData);
    expect(screen.queryByTestId("transcript-loading")).toBeNull();
    await waitFor(() => expect(mockedGetTranscript).toHaveBeenCalledTimes(2));
    await waitFor(() =>
      expect(screen.getByTestId("transcript-body").querySelector(".segment-quoted")).not.toBeNull(),
    );
    const chain = screen.getByTestId("transcript-journey-chain");
    // The highlight is placed when the sections arrive, not at the next scroll.
    await waitFor(() => expect(chain.querySelector(".bn-journey-label--active")).not.toBeNull());
    expect(mockedGetSessionList).toHaveBeenCalledTimes(2);
  });

  it("waits while the reader has text selected, then re-reads", async () => {
    mockedGetTranscript.mockResolvedValueOnce(beforeQuotes).mockResolvedValue(mockData);
    render(<TranscriptPage projectId="1" sessionId="s1" />);
    await waitFor(() => expect(screen.getByTestId("transcript-body")).toBeTruthy());
    const para = screen.getByTestId("transcript-body").querySelector(".segment-body")!;
    const range = document.createRange();
    range.selectNodeContents(para);
    window.getSelection()!.addRange(range);

    act(() => bumpRefreshKey());
    await new Promise((r) => setTimeout(r, 20));
    expect(mockedGetTranscript).toHaveBeenCalledTimes(1);

    window.getSelection()!.removeAllRanges();
    act(() => {
      document.dispatchEvent(new Event("selectionchange"));
    });
    await waitFor(() => expect(mockedGetTranscript).toHaveBeenCalledTimes(2));
  });

  it("keeps the reader's place when highlights move the lines above it", async () => {
    // Paragraphs 100px tall from y = -250; once any paragraph is quoted, a
    // highlight above the reader adds 40px (jsdom has no layout of its own).
    const rect = vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockImplementation(
      function (this: HTMLElement) {
        const starts = ["2", "10", "19", "26", "46"];
        const i = starts.indexOf(this.dataset.startSeconds ?? "");
        if (i < 0) return { top: 0, bottom: 0 } as DOMRect;
        const shift = document.querySelector(".segment-quoted") ? 40 : 0;
        const top = -250 + i * 100 + shift;
        return { top, bottom: top + 100 } as DOMRect;
      },
    );
    const scroll = vi.spyOn(window, "scrollBy").mockImplementation(() => {});
    await openThenBump(mockData);
    await waitFor(() => expect(scroll).toHaveBeenCalledWith(0, 40));
    rect.mockRestore();
    scroll.mockRestore();
  });

  it("does not pull the reader back to the link they arrived by", async () => {
    window.location.hash = "#t-26";
    await openThenBump(mockData);
    await waitFor(() => expect(mockedGetTranscript).toHaveBeenCalledTimes(2));
    await new Promise((r) => setTimeout(r, 50));
    expect(scrolledInto.filter((id) => id === "t-26")).toHaveLength(1);
  });

  it("scrolls to the link again on a later visit by it", async () => {
    mockedGetTranscript.mockResolvedValue(mockData);
    window.location.hash = "#t-26";
    const view = render(<TranscriptPage projectId="1" sessionId="s1" />);
    await waitFor(() => expect(scrolledInto).toContain("t-26"));
    window.location.hash = "";
    view.rerender(<TranscriptPage projectId="1" sessionId="s2" />);
    await waitFor(() => expect(mockedGetTranscript).toHaveBeenCalledTimes(2));
    await new Promise((r) => setTimeout(r, 20));
    window.location.hash = "#t-26";
    view.rerender(<TranscriptPage projectId="1" sessionId="s1" />);
    await waitFor(() => expect(scrolledInto.filter((id) => id === "t-26")).toHaveLength(2));
  });

  it("never lets another session's late re-read land", async () => {
    let releaseOld: (r: TranscriptPageResponse) => void = () => {};
    mockedGetTranscript
      .mockResolvedValueOnce(beforeQuotes) // s1, first read
      .mockReturnValueOnce(new Promise((r) => { releaseOld = r; })) // s1 re-read, held
      .mockResolvedValueOnce({ ...beforeQuotes, session_id: "s2",
        segments: [{ ...beforeQuotes.segments[0], text: "Session two speaking." }] });
    const view = render(<TranscriptPage projectId="1" sessionId="s1" />);
    await waitFor(() => expect(screen.getByTestId("transcript-body")).toBeTruthy());
    act(() => bumpRefreshKey());
    view.rerender(<TranscriptPage projectId="1" sessionId="s2" />);
    await waitFor(() => expect(screen.getByText("Session two speaking.")).toBeTruthy());
    await act(async () => {
      releaseOld(mockData);
    });
    expect(screen.getByText("Session two speaking.")).toBeTruthy();
    expect(screen.queryByText("Thanks for joining me today.")).toBeNull();
  });

  it("re-reads after a first read the bump overtook", async () => {
    let releaseFirst: (r: TranscriptPageResponse) => void = () => {};
    mockedGetTranscript
      .mockReturnValueOnce(new Promise((r) => { releaseFirst = r; }))
      .mockResolvedValue(mockData);
    render(<TranscriptPage projectId="1" sessionId="s1" />);
    act(() => bumpRefreshKey()); // the quotes landed while the first read was out
    await act(async () => {
      releaseFirst(beforeQuotes);
    });
    await waitFor(() => expect(mockedGetTranscript).toHaveBeenCalledTimes(2));
    await waitFor(() =>
      expect(screen.getByTestId("transcript-body").querySelector(".segment-quoted")).not.toBeNull(),
    );
  });

  it("holds a re-read that lands while the reader has started selecting", async () => {
    let release: (r: TranscriptPageResponse) => void = () => {};
    mockedGetTranscript
      .mockResolvedValueOnce(beforeQuotes)
      .mockReturnValueOnce(new Promise((r) => { release = r; }))
      .mockResolvedValue(mockData);
    render(<TranscriptPage projectId="1" sessionId="s1" />);
    await waitFor(() => expect(screen.getByTestId("transcript-body")).toBeTruthy());
    act(() => bumpRefreshKey());
    const para = screen.getByTestId("transcript-body").querySelector(".segment-body")!;
    const range = document.createRange();
    range.selectNodeContents(para);
    window.getSelection()!.addRange(range); // they start selecting meanwhile
    await act(async () => {
      release(mockData);
    });
    expect(screen.getByTestId("transcript-body").querySelector(".segment-quoted")).toBeNull();
    window.getSelection()!.removeAllRanges();
    act(() => {
      document.dispatchEvent(new Event("selectionchange"));
    });
    await waitFor(() =>
      expect(screen.getByTestId("transcript-body").querySelector(".segment-quoted")).not.toBeNull(),
    );
  });

  it("waits while a text field has focus, then re-reads when it loses it", async () => {
    mockedGetTranscript.mockResolvedValueOnce(beforeQuotes).mockResolvedValue(mockData);
    render(<TranscriptPage projectId="1" sessionId="s1" />);
    await waitFor(() => expect(screen.getByTestId("transcript-body")).toBeTruthy());
    const field = document.createElement("input"); // the speaker picker's name, say
    document.body.appendChild(field);
    field.focus();
    act(() => bumpRefreshKey());
    await new Promise((r) => setTimeout(r, 20));
    expect(mockedGetTranscript).toHaveBeenCalledTimes(1);
    // Focus leaves without a selection change (only `focusout` says so).
    field.remove();
    act(() => {
      document.dispatchEvent(new FocusEvent("focusout"));
    });
    await waitFor(() => expect(mockedGetTranscript).toHaveBeenCalledTimes(2));
  });

  it("does not bring back a badge deleted while a re-read was in flight", async () => {
    let releaseReread: (r: TranscriptPageResponse) => void = () => {};
    mockedGetTranscript
      .mockResolvedValueOnce(mockData)
      .mockReturnValueOnce(new Promise((r) => { releaseReread = r; }))
      .mockResolvedValue({
        ...mockData,
        annotations: {
          ...mockData.annotations,
          "q-p1-10": { ...mockData.annotations["q-p1-10"], deleted_badges: ["confusion"] },
        },
      });
    render(<TranscriptPage projectId="1" sessionId="s1" />);
    const badge = await screen.findByTestId("annotation-q-p1-10-sentiment");
    act(() => bumpRefreshKey());
    fireEvent.click(badge); // deleted while the re-read is out
    expect(screen.queryByTestId("annotation-q-p1-10-sentiment")).toBeNull();
    await act(async () => {
      releaseReread(mockData); // from before the delete: the badge is in it
    });
    expect(screen.queryByTestId("annotation-q-p1-10-sentiment")).toBeNull();
    await waitFor(() => expect(mockedGetTranscript).toHaveBeenCalledTimes(3), { timeout: 2000 });
    expect(screen.queryByTestId("annotation-q-p1-10-sentiment")).toBeNull();
  });
});


// ---------------------------------------------------------------------------
// The gutter (docs/design-transcript-gutter.md)
// ---------------------------------------------------------------------------

describe("TranscriptPage — the gutter", () => {
  function withGutterData(): TranscriptPageResponse {
    return {
      ...mockData,
      annotations: {
        ...mockData.annotations,
        "q-p1-10": { ...mockData.annotations["q-p1-10"], anchor: "section-5" },
        "q-p1-26": { ...mockData.annotations["q-p1-26"], anchor: "section-5", is_hidden: true },
      },
    };
  }

  async function renderGutter() {
    mockedGetTranscript.mockResolvedValue(withGutterData());
    render(<TranscriptPage projectId="1" sessionId="s1" />);
    await waitFor(() => expect(screen.getByTestId("annotation-q-p1-10")).toBeTruthy());
  }

  it("draws a quote's mark as a link to its group in the Quotes lens", async () => {
    await renderGutter();
    const mark = screen.getByTestId("annotation-q-p1-10").querySelector("a.bn-gutter-mark")!;
    expect(mark.getAttribute("href")).toBe("/report/quotes/?reveal=q-p1-10#section-5");
    expect(mark.getAttribute("aria-label")).toBe("Quotes: Dashboard");
    // The margin's title is the same link.
    const title = screen.getByTestId("annotation-q-p1-10").querySelector("a.bn-gutter-title")!;
    expect(title.getAttribute("href")).toBe("/report/quotes/?reveal=q-p1-10#section-5");
  });

  it("marks the quote's own words, and greys a hidden quote's words and entry", async () => {
    await renderGutter();
    const body = screen.getByTestId("transcript-body");
    expect(body.querySelectorAll('[data-q="q-p1-10"]').length).toBeGreaterThan(0);
    expect(body.querySelector('[data-q="q-p1-10"][data-q-hidden]')).toBeNull();
    expect(body.querySelector('[data-q="q-p1-26"]')!.hasAttribute("data-q-hidden")).toBe(true);
    expect(screen.getByTestId("annotation-q-p1-26").hasAttribute("data-hidden")).toBe(true);
  });

  it("follows a mark in the app, leaving Back on the paragraph it was made from", async () => {
    await renderGutter();
    const mark = screen.getByTestId("annotation-q-p1-10").querySelector("a.bn-gutter-mark")!;
    fireEvent.click(mark);
    expect(vi.mocked(navigateTo).mock.calls).toEqual([
      ["/report/sessions/s1#t-10", { replace: true }],
      ["/report/quotes/?reveal=q-p1-10#section-5"],
    ]);
  });

  it("leaves a modifier click to the browser, for a new tab", async () => {
    await renderGutter();
    const mark = screen.getByTestId("annotation-q-p1-10").querySelector("a.bn-gutter-mark")!;
    fireEvent.click(mark, { metaKey: true });
    expect(navigateTo).not.toHaveBeenCalled();
  });

  it("draws a quote with no group as a mark that leads nowhere", async () => {
    mockedGetTranscript.mockResolvedValue(mockData); // no anchors: an older server, or uncategorised
    render(<TranscriptPage projectId="1" sessionId="s1" />);
    await waitFor(() => expect(screen.getByTestId("annotation-q-p1-10")).toBeTruthy());
    const entry = screen.getByTestId("annotation-q-p1-10");
    expect(entry.querySelector("a.bn-gutter-mark")).toBeNull();
    expect(entry.querySelector("span.bn-gutter-mark")).toBeTruthy();
  });
});
