import { render, screen, fireEvent } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { QuoteCard } from "./QuoteCard";
import { _resetDisplayPrefs, setDisplayPref } from "../contexts/DisplayPrefsStore";
import { parseQuery } from "../utils/searchMatch";
import type { QuoteResponse } from "../utils/types";

// The break algorithm belongs to another session and its output will keep
// changing, so this file never asserts what it returns: it hands the card
// whatever blocks the mock gives and checks the card draws them.
const blocks = vi.hoisted(() => ({ value: ["one two", "three four"] as string[] }));
vi.mock("../utils/breakParagraphs", () => ({
  breakIntoBlocks: vi.fn(() => blocks.value),
}));

const NOOP = () => {};
const TEXT = "one two three four";

function makeQuote(): QuoteResponse {
  return {
    dom_id: "q-p1-26",
    text: TEXT,
    verbatim_excerpt: "one",
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
  };
}

function renderCard(highlight?: ReturnType<typeof parseQuery>) {
  const quote = makeQuote();
  return render(
    <QuoteCard
      quote={quote}
      displayText={quote.text}
      isStarred={false}
      isHidden={false}
      userTags={[]}
      allTagNames={[]}
      deletedBadges={[]}
      isEdited={false}
      tagVocabulary={[]}
      sessionId="s1"
      hasMedia={false}
      hasModerator={false}
      proposedTags={[]}
      flashingTags={new Set()}
      moderatorQuestion={null}
      isQuestionOpen={false}
      isPillVisible={false}
      highlight={highlight}
      onToggleStar={NOOP}
      onToggleHide={NOOP}
      onEditCommit={NOOP}
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

const textEl = () => screen.getByTestId("bn-quote-q-p1-26-text");
const blockEls = () => Array.from(textEl().querySelectorAll(".bn-block"));

beforeEach(() => {
  localStorage.clear();
  _resetDisplayPrefs();
  blocks.value = ["one two", "three four"];
});
afterEach(_resetDisplayPrefs);

describe("QuoteCard — Break long paragraphs", () => {
  it("breaks a long quote with no choice made: on is the default", () => {
    renderCard();
    expect(blockEls()).toHaveLength(2);
  });

  it("draws the quote as one piece when the reader has turned it off", () => {
    setDisplayPref("breaks", "off");
    renderCard();
    expect(blockEls()).toHaveLength(0);
    expect(textEl()).toHaveTextContent(TEXT);
  });

  it("draws one block per block the function returns when it is on", () => {
    setDisplayPref("breaks", "on");
    renderCard();
    expect(blockEls().map((b) => b.textContent)).toEqual(["“one two", "three four”"]);
  });

  it("puts the opening quote in the first block and the closing one in the last", () => {
    setDisplayPref("breaks", "on");
    blocks.value = ["a", "b", "c"];
    renderCard();
    const els = blockEls();
    expect(els).toHaveLength(3);
    expect(els[0].querySelector(".smart-quote")).toHaveTextContent("“");
    expect(els[1].querySelector(".smart-quote")).toBeNull();
    expect(els[2].querySelector(".smart-quote")).toHaveTextContent("”");
    // No quote mark outside the blocks, so neither can stand alone on a line.
    const wrapper = textEl().parentElement!;
    expect(Array.from(wrapper.children).filter((c) => c.classList.contains("smart-quote"))).toHaveLength(0);
  });

  it("leaves a quote the function does not break exactly as it is", () => {
    setDisplayPref("breaks", "on");
    blocks.value = [TEXT];
    renderCard();
    expect(blockEls()).toHaveLength(0);
    const wrapper = textEl().parentElement!;
    expect(wrapper.querySelectorAll(":scope > .smart-quote")).toHaveLength(2);
  });

  it("marks search matches inside the blocks", () => {
    setDisplayPref("breaks", "on");
    renderCard(parseQuery("three"));
    const marks = textEl().querySelectorAll("mark.search-mark");
    expect(marks).toHaveLength(1);
    expect(blockEls()[1].contains(marks[0])).toBe(true);
  });

  it("always shows the text unbroken while it is being edited", () => {
    setDisplayPref("breaks", "on");
    renderCard();
    fireEvent.click(textEl());
    expect(blockEls()).toHaveLength(0);
    expect(textEl().textContent).toContain("one two three four");
    // The card's own quote marks are back round the text, not dropped.
    expect(textEl().parentElement!.querySelectorAll(":scope > .smart-quote")).toHaveLength(2);
  });
});
