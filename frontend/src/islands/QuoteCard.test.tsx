import { render, screen, fireEvent } from "@testing-library/react";
import { QuoteCard } from "./QuoteCard";
import type { QuoteResponse, ModeratorQuestionResponse } from "../utils/types";

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
      proposedTags={[]}
      flashingTags={new Set()}
      moderatorQuestion={extra.moderatorQuestion ?? null}
      isQuestionOpen={extra.isQuestionOpen ?? false}
      isPillVisible={extra.isPillVisible ?? false}
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
