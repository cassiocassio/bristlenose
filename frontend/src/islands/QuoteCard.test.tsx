import { render, screen, fireEvent } from "@testing-library/react";
import { QuoteCard } from "./QuoteCard";
import type { QuoteResponse, ModeratorQuestionResponse, TranscriptSegmentResponse } from "../utils/types";

const NOOP = () => {};

function makeQuote(overrides: Partial<QuoteResponse> = {}): QuoteResponse {
  return {
    dom_id: "q-p1-26",
    text: "The navigation was hidden behind a hamburger menu",
    verbatim_excerpt: "The navigation was hidden",
    participant_id: "p1",
    session_id: "s1",
    speaker_name: "Alice",
    start_timecode: 26,
    end_timecode: 35,
    sentiment: null,
    intensity: 1,
    researcher_context: null,
    quote_type: "screen_specific",
    topic_label: "Dashboard",
    is_starred: false,
    is_hidden: false,
    edited_text: null,
    tags: [],
    deleted_badges: [],
    proposed_tags: [],
    segment_index: 3,
    ...overrides,
  };
}

const MOD_QUESTION: ModeratorQuestionResponse = {
  text: "What specifically was confusing about it?",
  speaker_code: "m1",
  start_time: 19,
  end_time: 25,
  segment_index: 2,
};

function renderCard(
  overrides: Partial<QuoteResponse> = {},
  extra: {
    moderatorQuestion?: ModeratorQuestionResponse | null;
    isQuestionOpen?: boolean;
    isPillVisible?: boolean;
    onToggleQuestion?: (domId: string) => void;
    canExpandAbove?: boolean;
    canExpandBelow?: boolean;
    onExpandAbove?: () => void;
    onExpandBelow?: () => void;
    exhaustedAbove?: boolean;
    exhaustedBelow?: boolean;
    contextAbove?: TranscriptSegmentResponse[];
    contextBelow?: TranscriptSegmentResponse[];
  } = {},
) {
  const quote = makeQuote(overrides);
  return render(
    <QuoteCard
      quote={quote}
      displayText={quote.text}
      isStarred={false}
      isHidden={false}
      userTags={[]}
      deletedBadges={[]}
      isEdited={false}
      tagVocabulary={[]}
      sessionId="s1"
      hasMedia={false}
      hasModerator={true}
      proposedTags={[]}
      flashingTags={new Set()}
      moderatorQuestion={extra.moderatorQuestion ?? null}
      isQuestionOpen={extra.isQuestionOpen ?? false}
      isPillVisible={extra.isPillVisible ?? false}
      canExpandAbove={extra.canExpandAbove}
      canExpandBelow={extra.canExpandBelow}
      onExpandAbove={extra.onExpandAbove}
      onExpandBelow={extra.onExpandBelow}
      exhaustedAbove={extra.exhaustedAbove}
      exhaustedBelow={extra.exhaustedBelow}
      contextAbove={extra.contextAbove}
      contextBelow={extra.contextBelow}
      onToggleStar={NOOP}
      onToggleHide={NOOP}
      onEditCommit={NOOP}
      onTagAdd={NOOP}
      onTagRemove={NOOP}
      onBadgeDelete={NOOP}
      onBadgeRestore={NOOP}
      onProposedAccept={NOOP}
      onProposedDeny={NOOP}
      onToggleQuestion={extra.onToggleQuestion ?? NOOP}
      onQuoteHoverEnter={NOOP}
      onQuoteHoverLeave={NOOP}
      onPillHoverEnter={NOOP}
      onPillHoverLeave={NOOP}
    />,
  );
}

describe("QuoteCard — moderator question", () => {
  it("renders pill button when segment_index > 0", () => {
    renderCard({ segment_index: 3 }, { isPillVisible: true });
    expect(screen.getByTestId("bn-quote-q-p1-26-mod-q")).toBeInTheDocument();
    expect(screen.getByText("Question?")).toBeInTheDocument();
  });

  it("does not render pill when segment_index <= 0", () => {
    renderCard({ segment_index: -1 });
    expect(screen.queryByTestId("bn-quote-q-p1-26-mod-q")).not.toBeInTheDocument();
  });

  it("does not render pill when segment_index = 0", () => {
    renderCard({ segment_index: 0 });
    expect(screen.queryByTestId("bn-quote-q-p1-26-mod-q")).not.toBeInTheDocument();
  });

  it("pill has .visible class when isPillVisible is true", () => {
    renderCard({ segment_index: 3 }, { isPillVisible: true });
    const pill = screen.getByTestId("bn-quote-q-p1-26-mod-q");
    expect(pill.className).toContain("visible");
  });

  it("pill has no .visible class when isPillVisible is false", () => {
    renderCard({ segment_index: 3 }, { isPillVisible: false });
    const pill = screen.getByTestId("bn-quote-q-p1-26-mod-q");
    expect(pill.className).not.toContain("visible");
  });

  it("pill is hidden when isQuestionOpen is true", () => {
    renderCard(
      { segment_index: 3 },
      { isPillVisible: true, isQuestionOpen: true, moderatorQuestion: MOD_QUESTION },
    );
    expect(screen.queryByTestId("bn-quote-q-p1-26-mod-q")).toBeNull();
  });

  it("clicking pill calls onToggleQuestion", async () => {
    const onToggle = vi.fn();
    renderCard(
      { segment_index: 3 },
      { isPillVisible: true, onToggleQuestion: onToggle },
    );
    fireEvent.click(screen.getByTestId("bn-quote-q-p1-26-mod-q"));
    expect(onToggle).toHaveBeenCalledWith("q-p1-26");
  });

  it("shows moderator question block when open with data", () => {
    renderCard(
      { segment_index: 3 },
      { isQuestionOpen: true, moderatorQuestion: MOD_QUESTION },
    );
    const block = screen.getByTestId("bn-quote-q-p1-26-mod-q-block");
    expect(block).toBeInTheDocument();
    expect(screen.getByText(/confusing about it/)).toBeInTheDocument();
  });

  it("hides moderator question block when not open", () => {
    renderCard(
      { segment_index: 3 },
      { isQuestionOpen: false, moderatorQuestion: MOD_QUESTION },
    );
    expect(screen.queryByTestId("bn-quote-q-p1-26-mod-q-block")).not.toBeInTheDocument();
  });

  it("hides moderator question block when data is null", () => {
    renderCard(
      { segment_index: 3 },
      { isQuestionOpen: true, moderatorQuestion: null },
    );
    expect(screen.queryByTestId("bn-quote-q-p1-26-mod-q-block")).not.toBeInTheDocument();
  });

  it("shows more… button for multi-sentence moderator text", () => {
    const longQuestion: ModeratorQuestionResponse = {
      ...MOD_QUESTION,
      text: "First sentence here. And then a second sentence with more detail.",
    };
    renderCard(
      { segment_index: 3 },
      { isQuestionOpen: true, moderatorQuestion: longQuestion },
    );
    expect(screen.getByText("more\u2026")).toBeInTheDocument();
    expect(screen.getByText(/First sentence here\./)).toBeInTheDocument();
  });

  it("clicking more… shows full text", () => {
    const longQuestion: ModeratorQuestionResponse = {
      ...MOD_QUESTION,
      text: "First sentence here. And then a second sentence with more detail.",
    };
    renderCard(
      { segment_index: 3 },
      { isQuestionOpen: true, moderatorQuestion: longQuestion },
    );
    fireEvent.click(screen.getByText("more\u2026"));
    expect(screen.getByText(/And then a second sentence/)).toBeInTheDocument();
    expect(screen.queryByText("more\u2026")).not.toBeInTheDocument();
  });

  it("single-sentence text shows no more… button", () => {
    renderCard(
      { segment_index: 3 },
      { isQuestionOpen: true, moderatorQuestion: MOD_QUESTION },
    );
    expect(screen.queryByText("more\u2026")).not.toBeInTheDocument();
  });

  it("hover zone has cursor:help class when segment_index > 0", () => {
    renderCard({ segment_index: 3 });
    const zone = document.querySelector(".quote-hover-zone");
    expect(zone).toBeInTheDocument();
  });

  it("no hover zone when segment_index <= 0", () => {
    renderCard({ segment_index: -1 });
    expect(document.querySelector(".quote-hover-zone")).not.toBeInTheDocument();
  });

  it("no hover zone when question is open (dismiss via × instead)", () => {
    renderCard(
      { segment_index: 3 },
      { isQuestionOpen: true, moderatorQuestion: MOD_QUESTION },
    );
    expect(document.querySelector(".quote-hover-zone")).not.toBeInTheDocument();
  });
});

describe("QuoteCard — context expansion", () => {
  it("wraps timecode in ExpandableTimecode when expansion callbacks provided", () => {
    renderCard({ start_timecode: 26 }, {
      canExpandAbove: true,
      canExpandBelow: true,
      onExpandAbove: () => {},
      onExpandBelow: () => {},
    });
    expect(screen.getByTestId("bn-quote-q-p1-26-expand")).toBeInTheDocument();
    expect(screen.getByTestId("bn-quote-q-p1-26-expand")).toHaveClass("timecode-expandable");
  });

  it("does not wrap timecode when no expansion callbacks", () => {
    renderCard({ start_timecode: 26 });
    expect(screen.queryByTestId("bn-quote-q-p1-26-expand")).not.toBeInTheDocument();
  });

  it("renders up and down arrows when both can expand", () => {
    renderCard({ start_timecode: 26 }, {
      canExpandAbove: true,
      canExpandBelow: true,
      onExpandAbove: () => {},
      onExpandBelow: () => {},
    });
    expect(screen.getByTestId("bn-quote-q-p1-26-expand-arrow-up")).toBeInTheDocument();
    expect(screen.getByTestId("bn-quote-q-p1-26-expand-arrow-down")).toBeInTheDocument();
  });

  it("calls onExpandAbove when up arrow clicked", () => {
    const onAbove = vi.fn();
    renderCard({ start_timecode: 26 }, {
      canExpandAbove: true,
      canExpandBelow: true,
      onExpandAbove: onAbove,
      onExpandBelow: () => {},
    });
    fireEvent.click(screen.getByTestId("bn-quote-q-p1-26-expand-arrow-up"));
    expect(onAbove).toHaveBeenCalledTimes(1);
  });

  it("calls onExpandBelow when down arrow clicked", () => {
    const onBelow = vi.fn();
    renderCard({ start_timecode: 26 }, {
      canExpandAbove: true,
      canExpandBelow: true,
      onExpandAbove: () => {},
      onExpandBelow: onBelow,
    });
    fireEvent.click(screen.getByTestId("bn-quote-q-p1-26-expand-arrow-down"));
    expect(onBelow).toHaveBeenCalledTimes(1);
  });

  it("disables up arrow when exhaustedAbove is true", () => {
    renderCard({ start_timecode: 26 }, {
      canExpandAbove: true,
      canExpandBelow: true,
      onExpandAbove: () => {},
      onExpandBelow: () => {},
      exhaustedAbove: true,
    });
    expect(screen.getByTestId("bn-quote-q-p1-26-expand-arrow-up")).toBeDisabled();
  });

  it("hides researcher_context when segment_index > 0", () => {
    renderCard({ segment_index: 3, researcher_context: "When asked about the dashboard" });
    expect(screen.queryByText(/When asked about the dashboard/)).not.toBeInTheDocument();
  });

  it("shows researcher_context when segment_index <= 0", () => {
    renderCard({ segment_index: -1, researcher_context: "When asked about the dashboard" });
    expect(screen.getByText(/When asked about the dashboard/)).toBeInTheDocument();
  });

  it("dismiss button calls onToggleQuestion", () => {
    const onToggle = vi.fn();
    renderCard(
      { segment_index: 3 },
      { isQuestionOpen: true, moderatorQuestion: MOD_QUESTION, onToggleQuestion: onToggle },
    );
    fireEvent.click(screen.getByTestId("bn-quote-q-p1-26-mod-q-dismiss"));
    expect(onToggle).toHaveBeenCalledWith("q-p1-26");
  });

  it("moderator question row is above the quote-row (context sits above the quote)", () => {
    renderCard(
      { segment_index: 3 },
      { isQuestionOpen: true, moderatorQuestion: MOD_QUESTION },
    );
    const row = screen.getByTestId("bn-quote-q-p1-26-mod-q-block");
    // The moderator row's parent should be the blockquote (quote-card).
    expect(row.parentElement?.tagName).toBe("BLOCKQUOTE");
    // It should be a .quote-row for alignment.
    expect(row.className).toContain("quote-row");
  });
});

describe("QuoteCard — context segments inside blockquote", () => {
  const makeSeg = (overrides: Partial<TranscriptSegmentResponse> = {}): TranscriptSegmentResponse => ({
    speaker_code: "p1",
    start_time: 20,
    end_time: 25,
    text: "Some context",
    html_text: null,
    is_moderator: false,
    is_quoted: false,
    quote_ids: [],
    segment_index: 2,
    ...overrides,
  });

  it("renders context segments above and below inside the blockquote", () => {
    renderCard({}, {
      contextAbove: [makeSeg({ text: "Before the quote", segment_index: 2, start_time: 20 })],
      contextBelow: [makeSeg({ text: "After the quote", segment_index: 4, start_time: 40 })],
    });
    const above = screen.getByTestId("bn-quote-q-p1-26-ctx-above-0");
    const below = screen.getByTestId("bn-quote-q-p1-26-ctx-below-0");
    // Both should be inside the blockquote.
    expect(above.closest("blockquote")).toBeTruthy();
    expect(below.closest("blockquote")).toBeTruthy();
    expect(screen.getByText("Before the quote")).toBeInTheDocument();
    expect(screen.getByText("After the quote")).toBeInTheDocument();
  });

  it("hides speaker badge when context segment speaker matches quote participant", () => {
    const { container } = renderCard({}, {
      contextBelow: [makeSeg({ speaker_code: "p1", text: "Same speaker" })],
    });
    const ctxSegment = screen.getByTestId("bn-quote-q-p1-26-ctx-below-0");
    expect(ctxSegment.querySelector(".bn-person-badge")).not.toBeInTheDocument();
    // But the quote's own speaker badge should still be there.
    expect(container.querySelector(".speaker .bn-person-badge")).toBeInTheDocument();
  });

  it("shows speaker badge when context segment is a different speaker", () => {
    renderCard({}, {
      contextBelow: [makeSeg({ speaker_code: "m1", is_moderator: true, text: "Moderator question" })],
    });
    const ctxSegment = screen.getByTestId("bn-quote-q-p1-26-ctx-below-0");
    expect(ctxSegment.querySelector(".bn-person-badge")).toBeInTheDocument();
    expect(ctxSegment.querySelector(".bn-person-badge")?.textContent).toContain("m1");
  });

  it("renders no context segments when arrays are empty", () => {
    renderCard({}, { contextAbove: [], contextBelow: [] });
    expect(screen.queryByTestId("bn-quote-q-p1-26-ctx-above-0")).not.toBeInTheDocument();
    expect(screen.queryByTestId("bn-quote-q-p1-26-ctx-below-0")).not.toBeInTheDocument();
  });
});

// ── Quote editing (trim handles) ────────────────────────────────────────

function renderEditableCard(
  overrides: Partial<QuoteResponse> = {},
  extra: {
    isEdited?: boolean;
    onEditCommit?: (domId: string, newText: string) => void;
  } = {},
) {
  const quote = makeQuote(overrides);
  return render(
    <QuoteCard
      quote={quote}
      displayText={quote.text}
      isStarred={false}
      isHidden={false}
      userTags={[]}
      deletedBadges={[]}
      isEdited={extra.isEdited ?? false}
      tagVocabulary={[]}
      sessionId="s1"
      hasMedia={false}
      hasModerator={true}
      proposedTags={[]}
      flashingTags={new Set()}
      moderatorQuestion={null}
      isQuestionOpen={false}
      isPillVisible={false}
      onToggleStar={NOOP}
      onToggleHide={NOOP}
      onEditCommit={extra.onEditCommit ?? NOOP}
      onTagAdd={NOOP}
      onTagRemove={NOOP}
      onBadgeDelete={NOOP}
      onBadgeRestore={NOOP}
      onProposedAccept={NOOP}
      onProposedDeny={NOOP}
      onToggleQuestion={NOOP}
      onQuoteHoverEnter={NOOP}
      onQuoteHoverLeave={NOOP}
      onPillHoverEnter={NOOP}
      onPillHoverLeave={NOOP}
    />,
  );
}

describe("QuoteCard — editing (trim handles)", () => {
  it("does not render a pencil edit button", () => {
    renderEditableCard();
    expect(document.querySelector(".edit-pencil")).not.toBeInTheDocument();
  });

  it("renders undo button", () => {
    renderEditableCard();
    expect(screen.getByTestId("bn-quote-q-p1-26-undo")).toBeInTheDocument();
  });

  it("undo button has .visible class when isEdited is true", () => {
    renderEditableCard({}, { isEdited: true });
    const btn = screen.getByTestId("bn-quote-q-p1-26-undo");
    expect(btn.className).toContain("visible");
  });

  it("undo button does not have .visible class when isEdited is false", () => {
    renderEditableCard({}, { isEdited: false });
    const btn = screen.getByTestId("bn-quote-q-p1-26-undo");
    expect(btn.className).not.toContain("visible");
  });

  it("undo button calls onEditCommit with original text", () => {
    const onEditCommit = vi.fn();
    renderEditableCard({}, { isEdited: true, onEditCommit });
    fireEvent.click(screen.getByTestId("bn-quote-q-p1-26-undo"));
    expect(onEditCommit).toHaveBeenCalledWith(
      "q-p1-26",
      "The navigation was hidden behind a hamburger menu",
    );
  });

  it("renders smart quotes as separate spans", () => {
    renderEditableCard();
    const smartQuotes = document.querySelectorAll(".smart-quote");
    expect(smartQuotes.length).toBe(2);
    expect(smartQuotes[0].textContent).toBe("\u201c");
    expect(smartQuotes[1].textContent).toBe("\u201d");
  });

  it("quote text is rendered in .quote-text span", () => {
    renderEditableCard();
    expect(screen.getByTestId("bn-quote-q-p1-26-text")).toBeInTheDocument();
    expect(screen.getByTestId("bn-quote-q-p1-26-text").textContent).toBe(
      "The navigation was hidden behind a hamburger menu",
    );
  });
});
