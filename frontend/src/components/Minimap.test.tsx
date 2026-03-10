/**
 * Tests for Minimap — VS Code-style abstract overview of quote page.
 */

import { describe, it, expect, beforeEach, vi, type Mock } from "vitest";
import { render, fireEvent, act } from "@testing-library/react";
import { Minimap } from "./Minimap";
import type { QuotesListResponse, QuoteResponse } from "../utils/types";

// ── Mocks ────────────────────────────────────────────────────────────────

vi.mock("../hooks/useProjectId", () => ({
  useProjectId: () => "test-project",
}));

function makeQuote(id: number): QuoteResponse {
  return {
    dom_id: `q${id}`,
    text: `Quote ${id}`,
    verbatim_excerpt: `Quote ${id}`,
    participant_id: "p1",
    session_id: "s1",
    speaker_name: "Alice",
    start_timecode: 0,
    end_timecode: 10,
    sentiment: "neutral",
    intensity: 1,
    researcher_context: null,
    quote_type: "verbatim",
    topic_label: "Topic",
    is_starred: false,
    is_hidden: false,
    edited_text: null,
    tags: [],
    deleted_badges: [],
    proposed_tags: [],
    segment_index: 0,
  };
}

const MOCK_RESPONSE: QuotesListResponse = {
  sections: [
    {
      cluster_id: 1,
      screen_label: "Homepage",
      description: "Main page",
      display_order: 1,
      quotes: [makeQuote(1), makeQuote(2), makeQuote(3)],
    },
    {
      cluster_id: 2,
      screen_label: "Checkout",
      description: "Payment",
      display_order: 2,
      quotes: [makeQuote(4)],
    },
  ],
  themes: [
    {
      theme_id: 1,
      theme_label: "Navigation",
      description: "Getting around",
      quotes: [makeQuote(5), makeQuote(6)],
    },
  ],
  total_quotes: 6,
  total_hidden: 0,
  total_starred: 0,
  has_moderator: false,
};

// ── Setup ────────────────────────────────────────────────────────────────

beforeEach(() => {
  vi.clearAllMocks();
  (globalThis.fetch as Mock) = vi.fn().mockResolvedValue({
    ok: true,
    json: () => Promise.resolve(MOCK_RESPONSE),
  });
});

// ── Tests ────────────────────────────────────────────────────────────────

describe("Minimap", () => {
  it("renders empty minimap-slot while loading", () => {
    (globalThis.fetch as Mock) = vi.fn().mockReturnValue(new Promise(() => {}));
    const { container } = render(<Minimap />);
    const slot = container.querySelector(".minimap-slot");
    expect(slot).toBeTruthy();
    expect(container.querySelector(".bn-minimap-content")).toBeNull();
    expect(container.querySelector(".bn-minimap-viewport")).toBeNull();
  });

  it("renders correct number of quote lines", async () => {
    const { container } = render(<Minimap />);
    await act(async () => {
      await new Promise((r) => setTimeout(r, 0));
    });
    // 3 + 1 + 2 = 6 quotes
    const quoteLines = container.querySelectorAll(".bn-minimap-quote");
    expect(quoteLines.length).toBe(6);
  });

  it("renders correct number of heading lines", async () => {
    const { container } = render(<Minimap />);
    await act(async () => {
      await new Promise((r) => setTimeout(r, 0));
    });
    // 2 section headings + 1 theme heading = 3
    const headingLines = container.querySelectorAll(".bn-minimap-heading");
    expect(headingLines.length).toBe(3);
  });

  it("renders two group headings (Sections + Themes)", async () => {
    const { container } = render(<Minimap />);
    await act(async () => {
      await new Promise((r) => setTimeout(r, 0));
    });
    const groupHeadings = container.querySelectorAll(".bn-minimap-group-heading");
    expect(groupHeadings.length).toBe(2);
  });

  it("renders one division between sections and themes", async () => {
    const { container } = render(<Minimap />);
    await act(async () => {
      await new Promise((r) => setTimeout(r, 0));
    });
    const divisions = container.querySelectorAll(".bn-minimap-division");
    expect(divisions.length).toBe(1);
  });

  it("renders viewport indicator", async () => {
    const { container } = render(<Minimap />);
    await act(async () => {
      await new Promise((r) => setTimeout(r, 0));
    });
    expect(container.querySelector(".bn-minimap-viewport")).toBeTruthy();
  });

  it("click on minimap triggers window.scrollTo", async () => {
    const scrollToMock = vi.fn();
    window.scrollTo = scrollToMock as unknown as typeof window.scrollTo;

    const { container } = render(<Minimap />);
    await act(async () => {
      await new Promise((r) => setTimeout(r, 0));
    });

    const slot = container.querySelector(".minimap-slot") as HTMLElement;
    fireEvent.click(slot, { clientY: 100 });
    expect(scrollToMock).toHaveBeenCalled();
  });

  it("re-fetches on bn:tags-changed event", async () => {
    render(<Minimap />);
    await act(async () => {
      await new Promise((r) => setTimeout(r, 0));
    });

    expect(globalThis.fetch).toHaveBeenCalledTimes(1);

    await act(async () => {
      document.dispatchEvent(new Event("bn:tags-changed"));
      await new Promise((r) => setTimeout(r, 0));
    });

    expect(globalThis.fetch).toHaveBeenCalledTimes(2);
  });

  it("does not render division when only sections exist", async () => {
    const sectionsOnly: QuotesListResponse = {
      ...MOCK_RESPONSE,
      themes: [],
    };
    (globalThis.fetch as Mock) = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(sectionsOnly),
    });

    const { container } = render(<Minimap />);
    await act(async () => {
      await new Promise((r) => setTimeout(r, 0));
    });

    expect(container.querySelectorAll(".bn-minimap-division").length).toBe(0);
    expect(container.querySelectorAll(".bn-minimap-group-heading").length).toBe(1);
  });

  it("does not render division when only themes exist", async () => {
    const themesOnly: QuotesListResponse = {
      ...MOCK_RESPONSE,
      sections: [],
    };
    (globalThis.fetch as Mock) = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(themesOnly),
    });

    const { container } = render(<Minimap />);
    await act(async () => {
      await new Promise((r) => setTimeout(r, 0));
    });

    expect(container.querySelectorAll(".bn-minimap-division").length).toBe(0);
    expect(container.querySelectorAll(".bn-minimap-group-heading").length).toBe(1);
  });

  it("renders 2000 quote lines without error (stress test)", async () => {
    const largeResponse: QuotesListResponse = {
      sections: [
        {
          cluster_id: 1,
          screen_label: "All Quotes",
          description: "Stress test section",
          display_order: 1,
          quotes: Array.from({ length: 2000 }, (_, i) => makeQuote(i)),
        },
      ],
      themes: [],
      total_quotes: 2000,
      total_hidden: 0,
      total_starred: 0,
      has_moderator: false,
    };
    (globalThis.fetch as Mock) = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(largeResponse),
    });

    const { container } = render(<Minimap />);
    await act(async () => {
      await new Promise((r) => setTimeout(r, 0));
    });

    const quoteLines = container.querySelectorAll(".bn-minimap-quote");
    expect(quoteLines.length).toBe(2000);
  });
});
