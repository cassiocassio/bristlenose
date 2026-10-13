import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { getQuotesSnapshot, resetStore } from "../../contexts/QuotesContext";
import type { QuoteResponse, QuotesListResponse } from "../../utils/types";
import { resetArrangementMemory } from "./layout";

vi.mock("../../utils/api", () => ({
  apiGet: vi.fn(),
  getCodebook: vi.fn(),
  putStarred: vi.fn(),
  putHidden: vi.fn(),
  putTags: vi.fn(),
  putEdits: vi.fn(),
}));

import { apiGet, getCodebook } from "../../utils/api";
import { ScreensLens } from "./ScreensLens";

beforeAll(() => {
  // jsdom has no ResizeObserver; the board measures through one.
  (globalThis as unknown as Record<string, unknown>).ResizeObserver = class {
    observe() {}
    disconnect() {}
  };
});

function quote(start: number, text: string): QuoteResponse {
  return {
    dom_id: `q-p1-${start}`, text, verbatim_excerpt: text, participant_id: "p1", session_id: "s1",
    speaker_name: "p1", start_timecode: start, end_timecode: start + 5, sentiment: null, intensity: 1,
    researcher_context: null, quote_type: "screen_specific", topic_label: "", is_starred: false,
    is_hidden: false, edited_text: null, tags: [], deleted_badges: [], proposed_tags: [], segment_index: 0,
  } as unknown as QuoteResponse;
}

const QUOTES: QuotesListResponse = {
  sections: [], themes: [],
  unjoined: [quote(10, "so I click continue to checkout now"), quote(30, "this is quite expensive")],
  total_quotes: 2, total_hidden: 0, total_starred: 0, has_moderator: false,
} as unknown as QuotesListResponse;

const TAB = {
  session_id: "s1", code: "p1", t: 12, crop: [0, 0.1, 0.9, 1], heading: "Shopping Bag", visits: [[0, 60]],
  pins: [{ dom_id: "q-p1-10", box: [0.5, 0.6, 0.3, 0.04], phrase: "continue to checkout", line: "Continue to checkout" }],
  loose: ["q-p1-30"],
};

function screensResponse(over: Record<string, unknown> = {}) {
  return {
    enabled: true, unavailable: null, pending: false, reading: null, videos: 1, indexed: 1,
    screens: [
      { key: "url:/shoppingcart", name: "/shoppingcart", quotes: 2, tabs: [TAB] },
      { key: "url:/order/delivery", name: "/order/delivery", quotes: 0,
        tabs: [{ ...TAB, heading: "Delivery or collect", pins: [], loose: [], t: 80 }] },
    ],
    ...over,
  };
}

function mockApi(screens: unknown) {
  vi.mocked(apiGet).mockImplementation(((path: string) => {
    if (path === "/screens") return Promise.resolve(screens);
    if (path === "/quotes") return Promise.resolve(QUOTES);
    if (path.startsWith("/screens/still")) return Promise.resolve({ src: "data:image/jpeg;base64,AA==" });
    return Promise.reject(new Error(path));
  }) as typeof apiGet);
}

beforeEach(() => {
  resetStore();
  resetArrangementMemory();
  vi.mocked(getCodebook).mockResolvedValue({ all_tag_names: [], groups: [], ungrouped: [] } as never);
  try {
    localStorage.clear();
  } catch {
    /* jsdom without storage */
  }
});

describe("ScreensLens", () => {
  it("lists every screen by its page title and address, most said-about first", async () => {
    mockApi(screensResponse());
    render(<ScreensLens />);
    await waitFor(() => expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Shopping Bag"));
    const nav = screen.getByRole("navigation", { name: "Screens" });
    expect(nav).toHaveTextContent("2 screens · 1 participant");
    expect(nav).toHaveTextContent("/shoppingcart");
    expect(nav).toHaveTextContent("Delivery or collect");
  });

  it("pins a quote beside the screen, marks the words read aloud, and lists the rest under it", async () => {
    mockApi(screensResponse());
    const { container } = render(<ScreensLens />);
    await waitFor(() => expect(container.querySelector(".screens-col blockquote")).not.toBeNull());
    const pinned = container.querySelector(".screens-col blockquote")!;
    expect(pinned.querySelector("mark.screens-read")).toHaveTextContent("continue to checkout");
    const loose = container.querySelector(".screens-loose blockquote")!;
    expect(loose).toHaveTextContent("this is quite expensive");
    // No heading over the unpinned quotes: they are not lesser, only unmatched.
    expect(container.querySelector(".screens-main h2, .screens-main h3")).toBeNull();
  });

  it("stars and hides through the report's own store", async () => {
    mockApi(screensResponse());
    const { container } = render(<ScreensLens />);
    await waitFor(() => expect(container.querySelector(".screens-loose blockquote")).not.toBeNull());
    const loose = container.querySelector<HTMLElement>(".screens-loose blockquote")!;
    fireEvent.click(loose.querySelector(".star-btn")!);
    expect(getQuotesSnapshot().starred["q-p1-30"]).toBe(true);
    act(() => {
      fireEvent.click(loose.querySelector(".hide-btn")!);
    });
    await waitFor(() => expect(getQuotesSnapshot().hidden["q-p1-30"]).toBe(true));
    await waitFor(() => expect(container.querySelector(".screens-loose blockquote")).toBeNull());
    expect(screen.getByText(/1 hidden quote/)).toBeInTheDocument();
  });

  it("moves between screens with the arrow keys", async () => {
    mockApi(screensResponse());
    render(<ScreensLens />);
    await waitFor(() => expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Shopping Bag"));
    fireEvent.keyDown(window, { key: "ArrowDown" });
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Delivery or collect");
  });

  it("says why there is nothing to show", async () => {
    mockApi(screensResponse({ enabled: false, screens: [] }));
    const { unmount } = render(<ScreensLens />);
    await waitFor(() => expect(screen.getByText(/Screens are off/)).toBeInTheDocument());
    unmount();
    mockApi(screensResponse({ screens: [], indexed: 1, videos: 1 }));
    render(<ScreensLens />);
    await waitFor(() => expect(screen.getByText(/No screens found/)).toBeInTheDocument());
  });

  it("names a recording it could not read, and one with no text, instead of reading for ever", async () => {
    mockApi(screensResponse({ screens: [], indexed: 1, videos: 2, failed: { s2: "ValueError: no video stream" },
                              blank: ["s1"] }));
    render(<ScreensLens />);
    await waitFor(() => expect(screen.getByText(/Couldn’t read s2: ValueError: no video stream/)).toBeInTheDocument());
    expect(screen.getByText(/No text found in s1’s recording/)).toBeInTheDocument();
    expect(screen.queryByText(/Reading screens/)).toBeNull();
    expect(screen.queryByText(/No screens found/)).toBeNull();  // the one indexed recording had no text
  });

  it("says the quotes failed to load rather than showing every screen empty", async () => {
    vi.mocked(apiGet).mockImplementation(((path: string) => {
      if (path === "/screens") return Promise.resolve(screensResponse());
      if (path === "/quotes") return Promise.reject(new Error("401"));
      return Promise.resolve({ src: "data:image/jpeg;base64,AA==" });
    }) as typeof apiGet);
    render(<ScreensLens />);
    await waitFor(() => expect(screen.getByText(/couldn’t load the quotes \(401\)/)).toBeInTheDocument());
  });
});
