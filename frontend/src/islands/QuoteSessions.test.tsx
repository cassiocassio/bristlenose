/**
 * The Quotes lens By session (docs/design-progressive-lenses.md, Phase 2):
 * the grouping, the session headings, and the control that switches.
 */

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { groupBySession, QuoteSessions } from "./QuoteSessions";
import { QuoteGroupingToggle, useQuoteGrouping } from "./QuoteGroupingToggle";
import type { QuoteResponse, QuotesListResponse } from "../utils/types";
import { resetStore } from "../contexts/QuotesContext";
import { renderHook, act } from "@testing-library/react";

vi.mock("../utils/api", () => ({
  apiGet: vi.fn(),
  getCodebook: vi.fn(),
  putEdits: vi.fn(),
  putStarred: vi.fn(),
}));

import { apiGet, getCodebook } from "../utils/api";

function quote(session: string, start: number, text = `${session} at ${start}`): QuoteResponse {
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
    is_hidden: false,
    edited_text: null,
    tags: [],
    deleted_badges: [],
    proposed_tags: [],
    segment_index: 0,
  } as unknown as QuoteResponse;
}

const DURING_THE_RUN: QuotesListResponse = {
  sections: [],
  themes: [],
  unjoined: [quote("s10", 30), quote("s2", 90), quote("s2", 10)],
  total_quotes: 3,
  total_hidden: 0,
  total_starred: 0,
  has_moderator: false,
};

beforeEach(() => {
  resetStore();
  vi.mocked(getCodebook).mockResolvedValue({ all_tag_names: [], groups: [], ungrouped: [] } as never);
  try {
    localStorage.clear();
  } catch {
    /* jsdom without storage */
  }
});

describe("groupBySession", () => {
  it("orders sessions by number and quotes by time", () => {
    const groups = groupBySession(DURING_THE_RUN);
    expect(groups.map((g) => g.sessionId)).toEqual(["s2", "s10"]);
    expect(groups[0].quotes.map((q) => q.start_timecode)).toEqual([10, 90]);
  });

  it("puts every quote in exactly one group, whatever list it came in", () => {
    const joined: QuotesListResponse = {
      ...DURING_THE_RUN,
      sections: [{
        cluster_id: 1, screen_label: "Login", description: "", display_order: 1,
        edited_label: null, edited_description: null, is_new: false,
        quotes: [quote("s1", 5)],
      }],
      themes: [{
        theme_id: 1, theme_label: "Trust", description: "",
        edited_label: null, edited_description: null, is_new: false,
        quotes: [quote("s1", 50)],
      }] as never,
      unjoined: [],
    };
    const groups = groupBySession(joined);
    expect(groups).toHaveLength(1);
    expect(groups[0].quotes.map((q) => q.dom_id)).toEqual(["q-s1-5", "q-s1-50"]);
  });
});

describe("QuoteSessions", () => {
  it("draws one group per session, headed by the session and not editable", async () => {
    vi.mocked(apiGet).mockResolvedValue(DURING_THE_RUN);
    const { container } = render(<QuoteSessions projectId="1" />);
    await waitFor(() => expect(screen.getByText("s10 at 30")).toBeInTheDocument());
    const headings = [...container.querySelectorAll(".bn-group-header h3")].map((h) => h.textContent);
    expect(headings).toEqual(["Session 2", "Session 10"]);
    expect(container.querySelector(".bn-group-header .edit-pencil")).toBeNull();
  });

  it("clears a failed refetch once the next one answers", async () => {
    vi.mocked(apiGet).mockRejectedValueOnce(new Error("busy")).mockResolvedValue(DURING_THE_RUN);
    const { rerender, container } = render(<QuoteSessions projectId="1" refreshKey={0} />);
    await waitFor(() => expect(container.querySelector(".bn-empty-state")).not.toBeNull());
    rerender(<QuoteSessions projectId="1" refreshKey={1} />);
    await waitFor(() => expect(screen.getByText("s10 at 30")).toBeInTheDocument());
    expect(container.querySelector(".bn-empty-state")).toBeNull();
  });
});

describe("the grouping control", () => {
  it("says which grouping is on and asks to switch", () => {
    const onChange = vi.fn();
    render(<QuoteGroupingToggle grouping="sections" onChange={onChange} />);
    expect(screen.getByTestId("bn-quote-grouping-sections")).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByTestId("bn-quote-grouping-session")).toHaveAttribute("aria-pressed", "false");
    fireEvent.click(screen.getByTestId("bn-quote-grouping-session"));
    expect(onChange).toHaveBeenCalledWith("session");
  });

  it("puts the default first and is the shipped split control", () => {
    // Sections & themes is the default and Sessions the second choice, so the
    // control reads in that order (docs/mockups/quote-grouping-sidebar.html).
    const { container } = render(<QuoteGroupingToggle grouping="session" onChange={vi.fn()} />);
    const group = container.querySelector(".dimension-toggle")!;
    const buttons = [...group.querySelectorAll("button.dimension-btn")];
    expect(buttons.map((b) => b.getAttribute("data-testid"))).toEqual([
      "bn-quote-grouping-sections",
      "bn-quote-grouping-session",
    ]);
    expect(buttons.map((b) => b.classList.contains("active"))).toEqual([false, true]);
  });

  it("is remembered per project, and defaults to sections and themes", () => {
    const { result } = renderHook(() => useQuoteGrouping("7"));
    expect(result.current[0]).toBe("sections");
    act(() => result.current[1]("session"));
    expect(renderHook(() => useQuoteGrouping("7")).result.current[0]).toBe("session");
    expect(renderHook(() => useQuoteGrouping("8")).result.current[0]).toBe("sections");
  });
});
