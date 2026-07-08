import { render, screen, act } from "@testing-library/react";
import { UncategorisedFloor } from "./UncategorisedFloor";
import {
  initFromQuotes,
  resetStore,
  getVisibleQuotes,
  getQuotesSnapshot,
} from "../contexts/QuotesContext";
import type { QuoteResponse } from "../utils/types";

function makeQuote(overrides: Partial<QuoteResponse> = {}): QuoteResponse {
  return {
    dom_id: "q-p1-42",
    text: "The screws weren't labelled",
    verbatim_excerpt: "screws weren't labelled",
    participant_id: "p1",
    session_id: "s3",
    speaker_name: "Priya",
    start_timecode: 42,
    end_timecode: 48,
    sentiment: null,
    intensity: 0,
    researcher_context: null,
    quote_type: "theme",
    topic_label: "Assembly",
    is_starred: true,
    is_hidden: false,
    edited_text: null,
    tags: [],
    deleted_badges: [],
    proposed_tags: [],
    segment_index: 0,
    ...overrides,
  };
}

// Seed only the uncategorised bucket, leaving sections/themes empty.
function seedFloor(quotes: QuoteResponse[]): void {
  act(() => {
    initFromQuotes([], true, quotes);
  });
}

beforeEach(() => {
  resetStore();
});

describe("UncategorisedFloor", () => {
  it("renders nothing when the floor is empty (the common case)", () => {
    render(<UncategorisedFloor />);
    expect(screen.queryByTestId("bn-uncategorised-floor")).not.toBeInTheDocument();
  });

  it("floor quotes stay walled off from the visible-quote / export scope", () => {
    // The floor lives in its own store slice, never in `quotes`, so exports
    // and counts (which read getVisibleQuotes) must not see it. Regression
    // guard: a future selector refactor must not leak the floor into scope.
    seedFloor([makeQuote({ dom_id: "q-p1-42" })]);
    expect(getVisibleQuotes(getQuotesSnapshot())).toHaveLength(0);
  });

  it("surfaces a homeless pinned quote read-only, in its frozen form", () => {
    seedFloor([makeQuote({ dom_id: "q-p1-42", text: "The screws weren't labelled" })]);
    render(<UncategorisedFloor />);

    expect(screen.getByTestId("bn-uncategorised-floor")).toBeInTheDocument();
    expect(screen.getByText(/The screws weren't labelled/)).toBeInTheDocument();
    // Starred quotes carry the .starred class (visual continuity with cards).
    expect(screen.getByTestId("bn-uncategorised-q-p1-42")).toHaveClass("starred");
    // No star/hide/tag-add buttons — read-only until Phase 0 re-assignment.
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });

  it("prefers the edited form and shows the quote's tags read-only", () => {
    seedFloor([
      makeQuote({
        dom_id: "q-p1-99",
        text: "raw text",
        edited_text: "the trimmed wording the researcher kept",
        tags: [
          { name: "compliance", codebook_group: "Legal", colour_set: "sunset", colour_index: 2, source: "human" },
        ],
      }),
    ]);
    render(<UncategorisedFloor />);

    expect(screen.getByText("the trimmed wording the researcher kept")).toBeInTheDocument();
    expect(screen.queryByText("raw text")).not.toBeInTheDocument();
    expect(screen.getByTestId("bn-uncategorised-q-p1-99-badge-compliance")).toHaveTextContent(
      "compliance",
    );
  });
});
