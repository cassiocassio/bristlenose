/**
 * Star, hide and tag on the report's undo stack (docs/design-people.md §B10).
 *
 * Each gesture is one entry; undo and redo are the same store calls with
 * recording off, so they do not record themselves; and the inverse is a delta
 * over what the gesture changed, never a snapshot of the whole map.
 */
import type { QuoteResponse, TagResponse } from "../utils/types";
import {
  HIDE_DURATION,
  addTag,
  commitEdit,
  commitHeadingEdit,
  addTagToQuotes,
  deleteBadge,
  getQuotesSnapshot,
  hideQuotes,
  initFromQuotes,
  removeTag,
  resetStore,
  restoreBadges,
  setStarred,
  toggleStar,
  unhideQuotes,
} from "./QuotesContext";
import { getUndoState, redo, resetUndoStore, undo } from "./UndoStore";
import { _resetExportCache } from "../utils/exportData";
import { TRANSCRIPT_WRITTEN_EVENT } from "../utils/transcriptWritten";

vi.mock("../utils/api", () => ({
  toastSaveFailed: vi.fn(),
  patchHidden: vi.fn(() => Promise.resolve()),
  patchStarred: vi.fn(() => Promise.resolve()),
  patchEdits: vi.fn(() => Promise.resolve()),
  patchQuoteBreaks: vi.fn(() => Promise.resolve()),
  patchTags: vi.fn(() => Promise.resolve()),
  patchDeletedBadges: vi.fn(() => Promise.resolve()),
  acceptProposal: vi.fn().mockResolvedValue(undefined),
  denyProposal: vi.fn().mockResolvedValue(undefined),
}));

import { patchDeletedBadges, patchEdits, patchHidden, patchQuoteBreaks, patchStarred, patchTags } from "../utils/api";

const patchStarredMock = vi.mocked(patchStarred);
const patchHiddenMock = vi.mocked(patchHidden);
const patchTagsMock = vi.mocked(patchTags);
const patchEditsMock = vi.mocked(patchEdits);
const patchBreaksMock = vi.mocked(patchQuoteBreaks);
const patchBadgesMock = vi.mocked(patchDeletedBadges);

function quote(dom_id: string, tags: TagResponse[] = []): QuoteResponse {
  return {
    dom_id,
    text: "x",
    verbatim_excerpt: "x",
    participant_id: "P1",
    session_id: "s1",
    speaker_name: "P1",
    start_timecode: 0,
    end_timecode: 1,
    sentiment: null,
    intensity: 0,
    researcher_context: null,
    quote_type: "section",
    topic_label: "T",
    is_starred: false,
    is_hidden: false,
    edited_text: null,
    tags,
    deleted_badges: [],
    proposed_tags: [],
    segment_index: 0,
  } as QuoteResponse;
}

const tag = (name: string): TagResponse => ({
  name, codebook_group: "G", colour_set: "ux", colour_index: 0,
});

const tagNames = (id: string) => (getQuotesSnapshot().tags[id] || []).map((t) => t.name);

beforeEach(() => {
  resetStore();
  resetUndoStore();
  vi.clearAllMocks();
  _resetExportCache();
  initFromQuotes([quote("q1"), quote("q2"), quote("q3")]);
});

describe("star", () => {
  it("undo unstars, redo stars again, one write each", async () => {
    toggleStar("q1", true);
    expect(getUndoState().undoAction).toBe("star");
    await undo();
    expect(getQuotesSnapshot().starred.q1).toBeUndefined();
    await redo();
    expect(getQuotesSnapshot().starred.q1).toBe(true);
    expect(patchStarredMock).toHaveBeenCalledTimes(3);
  });

  it("a bulk star undoes only the quotes it changed", async () => {
    setStarred(["q1"], true);
    setStarred(["q1", "q2", "q3"], true);
    await undo();
    expect(getQuotesSnapshot().starred).toEqual({ q1: true });
  });

  it("an undo does not record itself", async () => {
    toggleStar("q1", true);
    await undo();
    expect(getUndoState()).toMatchObject({ canUndo: false, canRedo: true, redoAction: "star" });
  });

  it("starring what is already starred records nothing", () => {
    setStarred(["q1"], true);
    setStarred(["q1"], true);
    expect(patchStarredMock).toHaveBeenCalledTimes(1);
  });

  it("unstar is its own act", () => {
    setStarred(["q1"], true);
    setStarred(["q1"], false);
    expect(getUndoState().undoAction).toBe("unstar");
  });
});

describe("hide", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it("undo after the collapse brings the quotes back", async () => {
    hideQuotes(["q1", "q2"]);
    vi.advanceTimersByTime(HIDE_DURATION);
    expect(getQuotesSnapshot().hidden).toEqual({ q1: true, q2: true });
    expect(getUndoState().undoAction).toBe("hide");
    await undo();
    expect(getQuotesSnapshot().hidden).toEqual({});
    expect(patchHiddenMock).toHaveBeenLastCalledWith({ q1: false, q2: false });
  });

  it("undo during the collapse stops the hide landing", async () => {
    hideQuotes(["q1"]);
    await undo();
    vi.advanceTimersByTime(HIDE_DURATION);
    expect(getQuotesSnapshot().hidden).toEqual({});
    expect(getQuotesSnapshot().hiding.size).toBe(0);
  });

  it("redo hides again", async () => {
    hideQuotes(["q1"]);
    vi.advanceTimersByTime(HIDE_DURATION);
    await undo();
    // A hide's redo resolves once the collapse has committed and saved.
    const redone = redo();
    vi.advanceTimersByTime(HIDE_DURATION);
    expect(await redone).toBe(true);
    expect(getQuotesSnapshot().hidden).toEqual({ q1: true });
  });

  it("undoing an unhide hides the quotes again", async () => {
    hideQuotes(["q1"]);
    vi.advanceTimersByTime(HIDE_DURATION);
    unhideQuotes(["q1"]);
    expect(getUndoState().undoAction).toBe("unhide");
    const undone = undo();
    vi.advanceTimersByTime(HIDE_DURATION);
    expect(await undone).toBe(true);
    expect(getQuotesSnapshot().hidden).toEqual({ q1: true });
  });
});

describe("tags", () => {
  it("a tag on a selection is one write and one entry, and undo is one write", async () => {
    addTag("q2", tag("Trust"));
    vi.clearAllMocks();
    addTagToQuotes(["q1", "q2", "q3"], tag("Trust"));
    expect(patchTagsMock).toHaveBeenCalledTimes(1);
    await undo();
    expect(patchTagsMock).toHaveBeenCalledTimes(2);
    // q2 had the tag before the gesture, so the undo leaves it.
    expect(tagNames("q1")).toEqual([]);
    expect(tagNames("q2")).toEqual(["Trust"]);
    expect(tagNames("q3")).toEqual([]);
    expect(getUndoState().undoAction).toBe("addTag");
  });

  it("undoing a removal puts the tag back where it was, colours and all", async () => {
    resetStore();
    initFromQuotes([quote("q1", [tag("A"), tag("B"), tag("C")])]);
    removeTag("q1", "B");
    expect(getUndoState().undoAction).toBe("removeTag");
    await undo();
    expect(tagNames("q1")).toEqual(["A", "B", "C"]);
    expect(getQuotesSnapshot().tags.q1[1]).toEqual(tag("B"));
    await redo();
    expect(tagNames("q1")).toEqual(["A", "C"]);
  });

  it("undoing the removal of an accepted suggestion puts it back as AutoCode (#14)", async () => {
    resetStore();
    const accepted = { ...tag("Trust"), source: "autocode" };
    initFromQuotes([quote("q1", [accepted])]);
    removeTag("q1", "Trust");
    patchTagsMock.mockClear();
    await undo();
    expect(patchTagsMock).toHaveBeenCalledWith({ q1: { add: ["Trust"], source: "autocode" } });
    expect(getQuotesSnapshot().tags.q1).toEqual([accepted]);
  });

  it("undoing the removal of a hand-made tag sends a plain add", async () => {
    resetStore();
    initFromQuotes([quote("q1", [{ ...tag("Trust"), source: "human" }])]);
    removeTag("q1", "Trust");
    patchTagsMock.mockClear();
    await undo();
    expect(patchTagsMock).toHaveBeenCalledWith({ q1: { add: ["Trust"] } });
  });

  it("undo is a delta: a tag added since by another path survives", async () => {
    addTagToQuotes(["q1"], tag("Trust"));
    // Not on the stack: an AutoCode accept or a refetch adding another tag.
    addTagToQuotes(["q1"], tag("Speed"), false);
    await undo();
    expect(tagNames("q1")).toEqual(["Speed"]);
  });
});

// A sentiment badge is a tag on the card ("Restore tags" undeletes them), so
// deleting one is Edit ▸ Undo Remove Tag (R10).
describe("sentiment badges", () => {
  const deleted = () => getQuotesSnapshot().deletedBadges.q1;

  it("deleting one is Remove Tag; undo puts it back in one write, redo deletes it again", async () => {
    deleteBadge("q1", "negative");
    expect(getUndoState().undoAction).toBe("removeTag");
    await undo();
    expect(deleted()).toBeUndefined();
    expect(patchBadgesMock).toHaveBeenLastCalledWith({ q1: { remove: ["negative"] } });
    await redo();
    expect(deleted()).toEqual(["negative"]);
    expect(patchBadgesMock).toHaveBeenCalledTimes(3);
  });

  it("an undo does not record itself", async () => {
    deleteBadge("q1", "negative");
    await undo();
    expect(getUndoState()).toMatchObject({ canUndo: false, canRedo: true, redoAction: "removeTag" });
  });

  it("undo is a delta: a badge deleted since by another path stays deleted", async () => {
    deleteBadge("q1", "negative");
    deleteBadge("q1", "positive", false);
    await undo();
    expect(deleted()).toEqual(["positive"]);
  });

  it("deleting a badge already deleted records and writes nothing", () => {
    resetStore();
    initFromQuotes([{ ...quote("q1"), deleted_badges: ["negative"] }]);
    deleteBadge("q1", "negative");
    expect(patchBadgesMock).not.toHaveBeenCalled();
    expect(getUndoState().canUndo).toBe(false);
    expect(deleted()).toEqual(["negative"]);
  });

  it("Restore tags is not an act on the stack, and an undo after it writes nothing", async () => {
    deleteBadge("q1", "negative");
    restoreBadges("q1");
    expect(getUndoState().undoAction).toBe("removeTag");
    patchBadgesMock.mockClear();
    expect(await undo()).toBe(true);
    expect(patchBadgesMock).not.toHaveBeenCalled();
    expect(deleted()).toBeUndefined();
  });
});

describe("a quote's own paragraphs", () => {
  const snap = () => getQuotesSnapshot();

  it("paragraphs alone are one gesture that writes the breaks with the words they were placed in", async () => {
    commitEdit("q1", null, { value: [0] });
    expect(snap().breaks.q1).toEqual([0]);
    expect(patchEditsMock).not.toHaveBeenCalled();
    await vi.waitFor(() => expect(patchBreaksMock).toHaveBeenLastCalledWith({ q1: { breaks: [0], text: "x" } }));
    expect(getUndoState().undoAction).toBe("editQuote");
    await undo();
    expect("q1" in snap().breaks).toBe(false);
    expect(patchBreaksMock).toHaveBeenLastCalledWith({ q1: null });
  });

  it("new words and paragraphs together are ONE undo, and the breaks go with the new words", async () => {
    commitEdit("q1", "a b c", { value: [1] });
    expect(snap().edits.q1).toBe("a b c");
    expect(patchEditsMock).toHaveBeenLastCalledWith({ q1: "a b c" });
    await vi.waitFor(() =>
      expect(patchBreaksMock).toHaveBeenLastCalledWith({ q1: { breaks: [1], text: "a b c" } }),
    );
    await undo();
    expect("q1" in snap().edits).toBe(false);
    expect("q1" in snap().breaks).toBe(false);
    expect(getUndoState().undoAction).toBeNull();
  });

  it("the card's revert hands the paragraphs back to the automatic placing", async () => {
    commitEdit("q1", "a b c", { value: [1] });
    commitEdit("q1", "x", { value: null });
    // The pipeline's words clear the edit rather than store a copy, which would
    // pin the quote against re-runs (review 25 Nov, finding 36).
    expect("q1" in snap().edits).toBe(false);
    expect(patchEditsMock).toHaveBeenLastCalledWith({ q1: null });
    expect("q1" in snap().breaks).toBe(false);
    await undo();
    expect(snap().breaks.q1).toEqual([1]);
  });

  it("reverting a quote whose only change is its paragraphs writes no edit, so it does not pin it", async () => {
    commitEdit("q1", null, { value: [0] });
    commitEdit("q1", "x", { value: null });
    await vi.waitFor(() => expect(patchBreaksMock).toHaveBeenLastCalledWith({ q1: null }));
    expect(patchEditsMock).not.toHaveBeenCalled();
    expect("q1" in snap().edits).toBe(false);
  });

  it("the words saving and the paragraphs failing keeps the words, and the undo", async () => {
    patchBreaksMock.mockRejectedValueOnce(new Error("PATCH /quote-breaks → 500"));
    commitEdit("q1", "a b c", { value: [1] });
    await vi.waitFor(() => expect("q1" in snap().breaks).toBe(false));
    expect(snap().edits.q1).toBe("a b c");
    expect(getUndoState().undoAction).toBe("editQuote");
  });

  it("the words failing sends no paragraphs, rolls both back and withdraws the undo", async () => {
    patchEditsMock.mockRejectedValueOnce(new Error("PATCH /edits → 500"));
    commitEdit("q1", "a b c", { value: [1] });
    await vi.waitFor(() => expect("q1" in snap().edits).toBe(false));
    expect("q1" in snap().breaks).toBe(false);
    expect(patchBreaksMock).not.toHaveBeenCalled();
    await vi.waitFor(() => expect(getUndoState().undoAction).toBeNull());
  });

  it("paragraphs alone failing roll back and withdraw the undo", async () => {
    // A gesture with no words to save is only its breaks: it did not partly land (finding 30).
    patchBreaksMock.mockRejectedValueOnce(new Error("PATCH /quote-breaks → 500"));
    commitEdit("q1", null, { value: [0] });
    await vi.waitFor(() => expect(getUndoState().undoAction).toBeNull());
    expect("q1" in snap().breaks).toBe(false);
  });

  it("new words saving and their paragraphs failing go back to automatic, not the old set", async () => {
    // The old set was placed in the old words, which the server no longer shows (finding 31).
    initFromQuotes([{ ...quote("q1"), researcher_breaks: [0] }], true);
    patchBreaksMock.mockRejectedValueOnce(new Error("PATCH /quote-breaks → 500"));
    commitEdit("q1", "a b c", { value: [1] });
    await vi.waitFor(() => expect(patchBreaksMock).toHaveBeenCalled());
    await vi.waitFor(() => expect("q1" in snap().breaks).toBe(false));
    expect(snap().edits.q1).toBe("a b c");
  });

  it("paragraphs alone failing keep the set the server still shows", async () => {
    initFromQuotes([{ ...quote("q1"), researcher_breaks: [0] }], true);
    patchBreaksMock.mockRejectedValueOnce(new Error("PATCH /quote-breaks → 500"));
    commitEdit("q1", null, { value: null });
    await vi.waitFor(() => expect(snap().breaks.q1).toEqual([0]));
  });

  it("a later gesture's paragraphs do not overtake an earlier one's held behind its words", async () => {
    // Finding 32: the server must end with the last gesture's breaks.
    let land!: () => void;
    patchEditsMock.mockImplementationOnce(() => new Promise<void>((r) => (land = r)));
    commitEdit("q1", "a b c", { value: [1] });
    commitEdit("q1", null, { value: [0] });
    await Promise.resolve();
    expect(patchBreaksMock).not.toHaveBeenCalled();
    land();
    await vi.waitFor(() => expect(patchBreaksMock).toHaveBeenCalledTimes(2));
    expect(patchBreaksMock.mock.calls.map((c) => c[0].q1)).toEqual([
      { breaks: [1], text: "a b c" },
      { breaks: [0], text: "a b c" },
    ]);
  });

  it("a refetch reads the researcher's breaks from the quote", () => {
    initFromQuotes([{ ...quote("q1"), researcher_breaks: [2] }], true);
    expect(snap().breaks.q1).toEqual([2]);
    initFromQuotes([{ ...quote("q1"), researcher_breaks: null }], true);
    expect("q1" in snap().breaks).toBe(false);
  });
});

describe("text edits", () => {
  const edits = () => getQuotesSnapshot().edits;

  it("undoing a first edit removes it, so the pipeline's text shows again", async () => {
    commitEdit("q1", "Edited");
    expect(getUndoState().undoAction).toBe("editQuote");
    await undo();
    expect("q1" in edits()).toBe(false);
    expect(patchEditsMock).toHaveBeenLastCalledWith({ q1: null });
    await redo();
    expect(edits().q1).toBe("Edited");
  });

  it("undoing a second edit restores the first", async () => {
    commitEdit("q1", "One");
    commitEdit("q1", "Two");
    await undo();
    expect(edits().q1).toBe("One");
  });

  it("the card's revert to the original is undoable too", async () => {
    commitEdit("q1", "Edited");
    commitEdit("q1", "x"); // the quote's own text — what the card's revert sends
    await undo();
    expect(edits().q1).toBe("Edited");
  });

  it("committing the text already there records and writes nothing", () => {
    commitEdit("q1", "Same");
    vi.clearAllMocks();
    commitEdit("q1", "Same");
    expect(patchEditsMock).not.toHaveBeenCalled();
    expect(getUndoState().undoAction).toBe("editQuote");
  });

  it.each([
    ["section-cluster-4:title", "renameSection"],
    ["theme-group-2:title", "renameTheme"],
    ["section-cluster-4:desc", "editDescription"],
    ["theme-group-2:desc", "editDescription"],
  ])("a heading edit to %s is %s, and its undo leaves quote edits alone", async (key, action) => {
    commitEdit("q1", "Kept");
    commitHeadingEdit(key, "Renamed");
    expect(getUndoState().undoAction).toBe(action);
    await undo();
    expect(edits()).toEqual({ q1: "Kept" });
  });
});

// A transcript open while ⌘Z undoes a quote act made in another lens keeps its
// own copy of the tags, badges and hidden grey: the undo tells it to read again,
// once per step that landed, and an act itself does not (R10 follow-up).
describe("an open transcript", () => {
  let reads = 0;
  const count = () => { reads += 1; };
  beforeEach(() => {
    reads = 0;
    window.addEventListener(TRANSCRIPT_WRITTEN_EVENT, count);
  });
  afterEach(() => window.removeEventListener(TRANSCRIPT_WRITTEN_EVENT, count));

  it("re-reads once after an undo and once after a redo, not after the act", async () => {
    toggleStar("q1", true);
    // Past every answer the act's write chains (send's, recordGesture's).
    await new Promise((r) => setTimeout(r, 0));
    expect(reads).toBe(0);
    await undo();
    expect(reads).toBe(1);
    await redo();
    expect(reads).toBe(2);
  });

  it("re-reads after the undo of a tag removal and of a badge delete", async () => {
    resetStore();
    initFromQuotes([quote("q1", [tag("A")])]);
    removeTag("q1", "A");
    deleteBadge("q1", "negative");
    await undo();
    await undo();
    expect(reads).toBe(2);
  });

  it("does not re-read after an undo whose write failed", async () => {
    toggleStar("q1", true);
    patchStarredMock.mockImplementationOnce(() => Promise.reject(new Error("refused")));
    expect(await undo()).toBe(false);
    expect(reads).toBe(0);
  });
});

describe("an exported report", () => {
  afterEach(() => {
    delete (window as unknown as Record<string, unknown>).BRISTLENOSE_EXPORT;
    _resetExportCache();
  });

  it("records nothing, because it changes nothing", () => {
    (window as unknown as Record<string, unknown>).BRISTLENOSE_EXPORT = { project: {} };
    _resetExportCache();
    toggleStar("q1", true);
    deleteBadge("q1", "negative");
    expect(getUndoState().canUndo).toBe(false);
  });
});
