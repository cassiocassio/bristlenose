import { act, cleanup, render, screen, fireEvent } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { QuoteCard } from "./QuoteCard";
import { _resetDisplayPrefs, setDisplayPref } from "../contexts/DisplayPrefsStore";
import { parseQuery } from "../utils/searchMatch";
import type { QuoteResponse } from "../utils/types";
import type { BreaksChange } from "../hooks/useCropEdit";
import { _resetPlatformCache } from "../utils/platform";

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

  it("keeps the paragraphs while it is being edited, so nothing moves", () => {
    setDisplayPref("breaks", "on");
    renderCard();
    fireEvent.click(textEl());
    expect(blockEls().map((b) => b.textContent)).toEqual(["\u201c[one two", "three four\u201d]"]);
    // The quote marks keep their places inside the paragraphs, the brackets laid over them,
    // and none is drawn outside the text as well.
    expect(blockEls()[0].querySelector(".bn-mark .smart-quote")).toHaveTextContent("\u201c");
    expect(textEl().parentElement!.querySelectorAll(":scope > .smart-quote")).toHaveLength(0);
  });
});

// ── Paragraphs typed while editing (docs/design-quote-editing.md §"Paragraphs") ──

type Commit = (domId: string, newText: string | null, breaks?: BreaksChange) => void;

function renderEditing(opts: { researcherBreaks?: number[] | null; onEditCommit?: Commit } = {}) {
  const quote = makeQuote();
  render(
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
      researcherBreaks={opts.researcherBreaks ?? null}
      onToggleStar={NOOP}
      onToggleHide={NOOP}
      onEditCommit={opts.onEditCommit ?? NOOP}
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
  fireEvent.click(textEl());
}

/** Put the caret in paragraph `block`'s typed text, at `offset` characters in. */
function caretIn(block: number, offset: number) {
  const run = blockEls()[block].querySelector(".crop-editable")!;
  const r = document.createRange();
  r.setStart(run.firstChild!, offset);
  r.collapse(true);
  window.getSelection()!.removeAllRanges();
  window.getSelection()!.addRange(r);
}

const key = (k: string, mods: Partial<KeyboardEventInit> = {}) => fireEvent.keyDown(textEl(), { key: k, ...mods });

describe("QuoteCard — paragraphs typed while editing", () => {
  beforeEach(() => setDisplayPref("breaks", "on"));

  it("Shift-Return starts a paragraph at the caret, and Return saves them as the researcher's own", () => {
    const onEditCommit = vi.fn<Commit>();
    renderEditing({ onEditCommit });
    caretIn(1, "three ".length);
    key("Enter", { shiftKey: true });
    expect(blockEls().map((b) => b.textContent)).toEqual(["\u201c[one two", "three", "four\u201d]"]);
    key("Enter");
    // The words did not change: only the paragraphs are written.
    expect(onEditCommit).toHaveBeenCalledExactlyOnceWith("q-p1-26", null, { value: [1, 2] });
  });

  it("inside a word, the new paragraph starts before the word (the transcript's rule)", () => {
    renderEditing();
    caretIn(1, "three fo".length);
    key("Enter", { shiftKey: true });
    expect(blockEls().map((b) => b.textContent)).toEqual(["\u201c[one two", "three", "four\u201d]"]);
  });

  it("Backspace at a paragraph's start joins it to the one above", () => {
    const onEditCommit = vi.fn<Commit>();
    renderEditing({ onEditCommit });
    caretIn(1, 0);
    key("Backspace");
    expect(blockEls().map((b) => b.textContent)).toEqual(["\u201c[one two three four\u201d]"]);
    key("Enter");
    // Every automatic break taken out is a choice too: an empty list, not "automatic".
    expect(onEditCommit).toHaveBeenCalledExactlyOnceWith("q-p1-26", null, { value: [] });
  });

  it("Delete at a paragraph's end joins the one below", () => {
    renderEditing();
    caretIn(0, "one two".length);
    key("Delete");
    expect(blockEls()).toHaveLength(1);
  });

  it("Backspace at the quote's very start does nothing, rather than delete the quote mark", () => {
    renderEditing();
    caretIn(0, 0);
    const ev = key("Backspace");
    expect(ev).toBe(false); // default prevented
    expect(blockEls()).toHaveLength(2);
  });

  it("Option-Return commits, as Return does: only Shift-Return makes a paragraph", () => {
    const onEditCommit = vi.fn<Commit>();
    renderEditing({ onEditCommit });
    caretIn(1, "three ".length);
    key("Enter", { altKey: true });
    expect(document.querySelector(".quote-card.editing")).toBeNull();
    expect(onEditCommit).not.toHaveBeenCalled(); // nothing changed
  });

  it("Escape puts the paragraphs back as they were", () => {
    const onEditCommit = vi.fn<Commit>();
    renderEditing({ onEditCommit });
    caretIn(1, "three ".length);
    key("Enter", { shiftKey: true });
    key("Escape");
    expect(blockEls().map((b) => b.textContent)).toEqual(["\u201cone two", "three four\u201d"]);
    expect(onEditCommit).not.toHaveBeenCalled();
  });

  it("paragraphs that come out as the automatic ones are not saved as the researcher's", () => {
    const onEditCommit = vi.fn<Commit>();
    renderEditing({ onEditCommit });
    caretIn(1, "three ".length);
    key("Enter", { shiftKey: true });
    caretIn(2, 0);
    key("Backspace");
    key("Enter");
    expect(onEditCommit).not.toHaveBeenCalled();
  });

  it("Return and Escape leave focus on the card, as Tab does", () => {
    for (const k of ["Enter", "Escape"]) {
      renderEditing();
      key(k);
      expect(document.querySelector(".quote-card.editing")).toBeNull();
      expect(document.activeElement).toBe(document.getElementById("q-p1-26"));
      cleanup();
    }
  });

  it("the Enter that confirms an input method's word is not a commit (WebKit: keyCode 229)", () => {
    const onEditCommit = vi.fn<Commit>();
    renderEditing({ onEditCommit });
    key("Enter", { keyCode: 229 });
    expect(document.querySelector(".quote-card.editing")).not.toBeNull();
    expect(onEditCommit).not.toHaveBeenCalled();
  });

  /** Select from paragraph `a`'s typed text at `ao` to paragraph `b`'s at `bo`. */
  const selectAcross = (a: number, ao: number, b: number, bo: number) => {
    const [x, y] = [a, b].map((i) => blockEls()[i].querySelector(".crop-editable")!.firstChild!);
    const r = document.createRange();
    r.setStart(x, ao);
    r.setEnd(y, bo);
    window.getSelection()!.removeAllRanges();
    window.getSelection()!.addRange(r);
  };

  it("⌘X across a paragraph break cuts the selected words and joins the paragraphs (26 Nov)", () => {
    const onEditCommit = vi.fn<Commit>();
    renderEditing({ onEditCommit });
    selectAcross(0, "one ".length, 1, "three".length);
    const setData = vi.fn();
    const cut = fireEvent.cut(textEl(), { clipboardData: { setData } });
    expect(cut).toBe(false); // the card cut it, not the browser
    expect(setData).toHaveBeenCalledExactlyOnceWith("text/plain", "two\nthree");
    expect(blockEls()).toHaveLength(1);
    key("Enter");
    expect(onEditCommit.mock.calls[0][1]).toBe("one four");
  });

  it("⌘X inside one paragraph's words is the browser's own", () => {
    renderEditing();
    selectAcross(1, 0, 1, "three".length);
    const setData = vi.fn();
    expect(fireEvent.cut(textEl(), { clipboardData: { setData } })).toBe(true);
    expect(setData).not.toHaveBeenCalled();
  });

  it("Delete and typing over a selection across paragraphs act on it (26 Nov)", () => {
    const onEditCommit = vi.fn<Commit>();
    renderEditing({ onEditCommit });
    const beforeInput = (inputType: string, data?: string) =>
      textEl().dispatchEvent(new InputEvent("beforeinput", { inputType, data, cancelable: true, bubbles: true }));
    selectAcross(0, "one ".length, 1, "three ".length);
    expect(beforeInput("deleteContentBackward")).toBe(false);
    expect(blockEls()).toHaveLength(1);
    key("Enter");
    expect(onEditCommit.mock.calls[0][1]).toBe("one four");
  });

  it("typing over a selection across paragraphs replaces it", () => {
    const onEditCommit = vi.fn<Commit>();
    renderEditing({ onEditCommit });
    selectAcross(0, "one ".length, 1, "three".length);
    const e = new InputEvent("beforeinput", { inputType: "insertText", data: "X", cancelable: true, bubbles: true });
    expect(textEl().dispatchEvent(e)).toBe(false);
    key("Enter");
    expect(onEditCommit.mock.calls[0][1]).toBe("one X four");
  });

  it("a paste over a selection across paragraphs replaces it, as typing does (findings 29, 33)", () => {
    const onEditCommit = vi.fn<Commit>();
    const exec = vi.fn(() => true);
    const had = Object.getOwnPropertyDescriptor(document, "execCommand");
    Object.defineProperty(document, "execCommand", { value: exec, configurable: true });
    try {
      renderEditing({ onEditCommit });
      const paste = () =>
        fireEvent.paste(textEl(), { clipboardData: { getData: () => "pasted words" } });
      selectAcross(0, "one ".length, 1, "three".length);
      paste();
      expect(exec).not.toHaveBeenCalled(); // the card replaced it, on the words
      expect(blockEls()).toHaveLength(1);
      caretIn(0, 0);
      paste();
      expect(exec).toHaveBeenCalledExactlyOnceWith("insertText", false, "pasted words");
      key("Enter");
      expect(onEditCommit.mock.calls[0][1]).toBe("one pasted words four");
    } finally {
      if (had) Object.defineProperty(document, "execCommand", had);
      else delete (document as { execCommand?: unknown }).execCommand;
    }
  });

  it("⌘A selects the paragraph's words; on the Mac Ctrl-A stays the text system's (finding 35)", () => {
    const platform = Object.getOwnPropertyDescriptor(Navigator.prototype, "platform");
    Object.defineProperty(navigator, "platform", { value: "MacIntel", configurable: true });
    _resetPlatformCache();
    try {
      renderEditing();
      const selected = () => window.getSelection()!.toString();
      caretIn(1, 1);
      key("a", { ctrlKey: true });
      expect(selected()).toBe("");
      key("a", { metaKey: true });
      expect(selected()).toBe("three four");
      caretIn(0, 1);
      key("ф", { metaKey: true, code: "KeyA" }); // a Cyrillic layout's A key
      expect(selected()).toBe("one two");
    } finally {
      delete (navigator as { platform?: string }).platform;
      if (platform) Object.defineProperty(Navigator.prototype, "platform", platform);
      _resetPlatformCache();
    }
  });

  it("with Break long paragraphs off, a paragraph placed where the automatic one would go is kept", () => {
    setDisplayPref("breaks", "off");
    const onEditCommit = vi.fn<Commit>();
    renderEditing({ onEditCommit });
    expect(blockEls()).toHaveLength(1);
    caretIn(0, "one two ".length);
    key("Enter", { shiftKey: true });
    key("Enter");
    expect(onEditCommit).toHaveBeenCalledExactlyOnceWith("q-p1-26", null, { value: [1] });
  });

  it("with Break long paragraphs off, a paragraph made and taken out again is no change", () => {
    setDisplayPref("breaks", "off");
    const onEditCommit = vi.fn<Commit>();
    renderEditing({ onEditCommit });
    caretIn(0, "one two ".length);
    key("Enter", { shiftKey: true });
    caretIn(1, 0);
    key("Backspace");
    key("Enter");
    expect(onEditCommit).not.toHaveBeenCalled();
  });

  it("Tab commits once and leaves focus on the card", () => {
    vi.useFakeTimers();
    try {
      const onEditCommit = vi.fn<Commit>();
      renderEditing({ onEditCommit });
      caretIn(1, "three ".length);
      key("Enter", { shiftKey: true });
      key("Tab");
      // Moving focus to the card blurs the text; that blur's deferred commit
      // must not commit the same edit again (a second write and a second
      // undo entry, so ⌘Z undid only the copy: found live, 21 Nov 2026).
      act(() => { vi.runOnlyPendingTimers(); });
      expect(document.querySelector(".quote-card.editing")).toBeNull();
      expect(onEditCommit).toHaveBeenCalledOnce();
      expect(document.activeElement).toBe(document.getElementById("q-p1-26"));
    } finally {
      vi.useRealTimers();
    }
  });

  it("the researcher's own paragraphs show even with Break long paragraphs off", () => {
    setDisplayPref("breaks", "off");
    const quote = makeQuote();
    render(
      <QuoteCard
        quote={quote}
        displayText={quote.text}
        isStarred={false}
        isHidden={false}
        userTags={[]}
        allTagNames={[]}
        deletedBadges={[]}
        isEdited
        tagVocabulary={[]}
        sessionId="s1"
        hasMedia={false}
        hasModerator={false}
        proposedTags={[]}
        flashingTags={new Set()}
        moderatorQuestion={null}
        isQuestionOpen={false}
        isPillVisible={false}
        researcherBreaks={[0, 2]}
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
    expect(blockEls().map((b) => b.textContent)).toEqual(["\u201cone", "two three", "four\u201d"]);
  });

  it("an edit to the words carries the researcher's own paragraphs with it", () => {
    const onEditCommit = vi.fn<Commit>();
    renderEditing({ researcherBreaks: [0], onEditCommit });
    const run = blockEls()[1].querySelector(".crop-editable")!;
    run.textContent = "two three five";
    key("Enter");
    // Sent again with the new words, which the server keeps them against.
    expect(onEditCommit).toHaveBeenCalledExactlyOnceWith("q-p1-26", "one two three five", { value: [0] });
  });
});
