/**
 * TocSidebar — the Quotes lens's contents, in the order the column draws them
 * (docs/mockups/quote-grouping-sidebar.html).
 *
 * The invariants a researcher would notice:
 *   • the list leaves out exactly the groups the column leaves out, in both
 *     groupings — a link must never scroll to a heading that is not there
 *   • a renamed section's link lands on its renamed heading
 *   • in Sessions grouping the rows are the Sessions lens's rows, and a click
 *     scrolls to that session's quotes; it does not open the transcript
 */

import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { TocSidebar } from "./TocSidebar";
import { commitHeadingEdit, initFromQuotes, resetStore, setSearchQuery, setStarred } from "../contexts/QuotesContext";
import { publishQuoteGrouping, resetQuoteGroupingSlot } from "../contexts/QuoteGroupingSlot";
import { resetSidebarStore } from "../contexts/SidebarStore";
import type { QuoteResponse, QuotesListResponse, SessionResponse } from "../utils/types";

vi.mock("../utils/api", async (importOriginal) => ({
  ...((await importOriginal()) as Record<string, unknown>),
  apiGet: vi.fn(),
  patchStarred: vi.fn(() => Promise.resolve()),
}));

import { apiGet } from "../utils/api";

// The run's refresh key, which a test moves to stand for an import.
const lastRun = { refreshKey: 0 };
vi.mock("../contexts/LastRunStore", async (importOriginal) => ({
  ...((await importOriginal()) as Record<string, unknown>),
  useLastRun: () => ({ ...lastRun }),
}));

function quote(session: string, start: number, text: string, hidden = false): QuoteResponse {
  return {
    dom_id: `q-${session}-${start}`,
    text,
    verbatim_excerpt: text,
    participant_id: "p1",
    session_id: session,
    speaker_name: "",
    start_timecode: start,
    end_timecode: start + 5,
    sentiment: null,
    intensity: 1,
    researcher_context: null,
    quote_type: "section",
    topic_label: "",
    is_starred: false,
    is_hidden: hidden,
    edited_text: null,
    tags: [],
    deleted_badges: [],
    proposed_tags: [],
    segment_index: 0,
  } as unknown as QuoteResponse;
}

function section(id: number, label: string, quotes: QuoteResponse[], edited: string | null = null) {
  return {
    cluster_id: id, screen_label: label, description: "", display_order: id,
    edited_label: edited, edited_description: null, is_new: false, quotes,
  };
}

function session(n: number, name: string): SessionResponse {
  return {
    session_id: `s${n}`, session_number: n, session_date: "2026-09-14T10:00:00",
    duration_seconds: 2700, has_media: true, has_video: false, thumbnail_url: null,
    speakers: [{ speaker_code: `p${n}`, name, role: "participant" }],
    journey_labels: [], journey: [], sentiment_counts: {}, source_files: [],
  } as unknown as SessionResponse;
}

const CHECKOUT = quote("s1", 10, "The checkout total surprised me");
const SEARCH = quote("s2", 20, "Search found nothing useful");
const HIDDEN_ONLY = quote("s3", 30, "A quote somebody hid", true);
const FLOOR = quote("s4", 40, "Kept from an earlier analysis");

const QUOTES: QuotesListResponse = {
  sections: [
    section(1, "Checkout", [CHECKOUT]),
    section(2, "Search and filters", [SEARCH], "Finding things"),
    section(3, "Delivery", [HIDDEN_ONLY]),
  ],
  themes: [],
  uncategorised: [FLOOR],
  total_quotes: 4,
  total_hidden: 1,
  total_starred: 0,
  has_moderator: false,
} as unknown as QuotesListResponse;

const SESSIONS = {
  sessions: [session(1, "Sarah Chen"), session(2, "Marcus Reid"), session(3, "Priya Raman"), session(4, "Tom Lind")],
};

function seedStore() {
  initFromQuotes([CHECKOUT, SEARCH, HIDDEN_ONLY], false, [FLOOR]);
}

function grouping(shown: "sections" | "session") {
  publishQuoteGrouping({ shown, controlVisible: true, choose: vi.fn() });
}

const sessionsCalls = () => vi.mocked(apiGet).mock.calls.filter(([p]) => p === "/sessions").length;

beforeEach(() => {
  vi.clearAllMocks();
  lastRun.refreshKey = 0;
  // jsdom has no scrollIntoView. The sidebar keeps its active row in view,
  // and the scroll spy may mark one active at any moment.
  Element.prototype.scrollIntoView = vi.fn();
  resetStore();
  resetSidebarStore();
  resetQuoteGroupingSlot();
  vi.mocked(apiGet).mockImplementation(((path: string) =>
    Promise.resolve(path === "/sessions" ? SESSIONS : QUOTES)) as never);
});

describe("Sections & themes", () => {
  it("lists the displayed labels, linking to the headings the column draws", async () => {
    seedStore();
    grouping("sections");
    render(<TocSidebar />);
    const renamed = await screen.findByRole("link", { name: "Finding things" });
    // QuoteSections anchors on the durable id, never the name.
    expect(renamed).toHaveAttribute("href", "#section-2");
    expect(screen.queryByText("Search and filters")).toBeNull();
  });

  it("shows a rename made in this session, and the link does not move", async () => {
    seedStore();
    grouping("sections");
    render(<TocSidebar />);
    expect(await screen.findByRole("link", { name: "Checkout" })).toHaveAttribute("href", "#section-1");
    act(() => commitHeadingEdit("section-cluster-1:title", "Paying"));
    // The anchor is the cluster id, so a rename cannot break a link to it.
    expect(screen.getByRole("link", { name: "Paying" })).toHaveAttribute("href", "#section-1");
  });

  it("keeps a section whose quotes are all hidden, as the column does", async () => {
    seedStore();
    grouping("sections");
    render(<TocSidebar />);
    expect(await screen.findByRole("link", { name: "Delivery" })).toBeInTheDocument();
  });

  it("leaves out a section the filters have emptied", async () => {
    seedStore();
    grouping("sections");
    render(<TocSidebar />);
    await screen.findByRole("link", { name: "Checkout" });
    act(() => setSearchQuery("checkout"));
    expect(screen.queryByRole("link", { name: "Finding things" })).toBeNull();
    expect(screen.getByRole("link", { name: "Checkout" })).toBeInTheDocument();
  });
});

describe("Sessions", () => {
  it("lists the sessions the column draws, as the Sessions lens's rows", async () => {
    seedStore();
    grouping("session");
    render(<TocSidebar />);
    const nav = await screen.findByRole("navigation", { name: "Table of contents" });
    await waitFor(() => expect(nav.querySelectorAll("a.session-entry")).toHaveLength(4));
    const hrefs = [...nav.querySelectorAll("a.session-entry")].map((a) => a.getAttribute("href"));
    // s4 holds only a floor quote: the column's session grouping counts the
    // floor, so the list does too.
    expect(hrefs).toEqual([
      "#session-quotes-s1",
      "#session-quotes-s2",
      "#session-quotes-s3",
      "#session-quotes-s4",
    ]);
    expect(nav.querySelector("nav")).toBeNull(); // one landmark, not two
  });

  it("leaves out a session the filters have emptied, keeping one with hidden quotes", async () => {
    seedStore();
    grouping("session");
    const { container } = render(<TocSidebar />);
    await waitFor(() => expect(container.querySelectorAll("a.session-entry")).toHaveLength(4));
    act(() => setSearchQuery("checkout"));
    const hrefs = [...container.querySelectorAll("a.session-entry")].map((a) => a.getAttribute("href"));
    expect(hrefs).toEqual(["#session-quotes-s1", "#session-quotes-s3"]);
  });

  it("scrolls to the session's quotes on a click, and does not navigate", async () => {
    seedStore();
    grouping("session");
    const target = document.createElement("h3");
    target.id = "session-quotes-s2";
    target.scrollIntoView = vi.fn();
    document.body.appendChild(target);
    const { container } = render(<TocSidebar />);
    await waitFor(() => expect(container.querySelectorAll("a.session-entry")).toHaveLength(4));
    const row = container.querySelector<HTMLAnchorElement>('a[href="#session-quotes-s2"]')!;
    const notPrevented = fireEvent.click(row);
    expect(notPrevented).toBe(false);
    expect(target.scrollIntoView).toHaveBeenCalledWith({ behavior: "smooth", block: "start" });
    target.remove();
  });

  it("follows a run: refetches when it imports, and asks for sessions only when one joins", async () => {
    seedStore();
    grouping("session");
    const { container, rerender } = render(<TocSidebar />);
    await waitFor(() => expect(sessionsCalls()).toBe(1));
    act(() => setStarred([CHECKOUT.dom_id], true));
    expect(sessionsCalls()).toBe(1);

    const withS5 = { ...QUOTES, unjoined: [quote("s5", 50, "A new session arrives")] };
    vi.mocked(apiGet).mockImplementation(((path: string) =>
      Promise.resolve(path === "/sessions" ? { sessions: [...SESSIONS.sessions, session(5, "Mei Tanaka")] } : withS5)) as never);
    lastRun.refreshKey = 1;
    rerender(<TocSidebar />);
    await waitFor(() => expect(container.querySelectorAll("a.session-entry")).toHaveLength(5));
    expect(sessionsCalls()).toBe(2);
  });

  it("draws nothing until the page has said which grouping it shows", async () => {
    seedStore();
    const { container } = render(<TocSidebar />);
    await waitFor(() => expect(vi.mocked(apiGet)).toHaveBeenCalled());
    expect(container.querySelector("nav")).toBeNull();
  });

  it("follows the page when it switches grouping", async () => {
    seedStore();
    grouping("sections");
    const { container } = render(<TocSidebar />);
    await screen.findByRole("link", { name: "Checkout" });
    act(() => grouping("session"));
    await waitFor(() => expect(container.querySelectorAll("a.session-entry")).toHaveLength(4));
    expect(screen.queryByRole("link", { name: "Checkout" })).toBeNull();
  });
});
