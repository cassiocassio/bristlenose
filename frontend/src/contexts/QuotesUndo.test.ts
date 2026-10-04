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
  addTagToQuotes,
  getQuotesSnapshot,
  hideQuotes,
  initFromQuotes,
  removeTag,
  resetStore,
  setStarred,
  toggleStar,
  unhideQuotes,
} from "./QuotesContext";
import { getUndoState, redo, resetUndoStore, undo } from "./UndoStore";
import { _resetExportCache } from "../utils/exportData";

vi.mock("../utils/api", () => ({
  putHidden: vi.fn(),
  putStarred: vi.fn(),
  putEdits: vi.fn(),
  putTags: vi.fn(),
  putDeletedBadges: vi.fn(),
  acceptProposal: vi.fn().mockResolvedValue(undefined),
  denyProposal: vi.fn().mockResolvedValue(undefined),
}));

import { putHidden, putStarred, putTags } from "../utils/api";

const putStarredMock = vi.mocked(putStarred);
const putHiddenMock = vi.mocked(putHidden);
const putTagsMock = vi.mocked(putTags);

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
    expect(putStarredMock).toHaveBeenCalledTimes(3);
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
    expect(putStarredMock).toHaveBeenCalledTimes(1);
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
    expect(putHiddenMock).toHaveBeenLastCalledWith({});
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
    await redo();
    vi.advanceTimersByTime(HIDE_DURATION);
    expect(getQuotesSnapshot().hidden).toEqual({ q1: true });
  });

  it("undoing an unhide hides the quotes again", async () => {
    hideQuotes(["q1"]);
    vi.advanceTimersByTime(HIDE_DURATION);
    unhideQuotes(["q1"]);
    expect(getUndoState().undoAction).toBe("unhide");
    await undo();
    vi.advanceTimersByTime(HIDE_DURATION);
    expect(getQuotesSnapshot().hidden).toEqual({ q1: true });
  });
});

describe("tags", () => {
  it("a tag on a selection is one write and one entry, and undo is one write", async () => {
    addTag("q2", tag("Trust"));
    vi.clearAllMocks();
    addTagToQuotes(["q1", "q2", "q3"], tag("Trust"));
    expect(putTagsMock).toHaveBeenCalledTimes(1);
    await undo();
    expect(putTagsMock).toHaveBeenCalledTimes(2);
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

  it("undo is a delta: a tag added since by another path survives", async () => {
    addTagToQuotes(["q1"], tag("Trust"));
    // Not on the stack: an AutoCode accept or a refetch adding another tag.
    addTagToQuotes(["q1"], tag("Speed"), false);
    await undo();
    expect(tagNames("q1")).toEqual(["Speed"]);
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
    expect(getUndoState().canUndo).toBe(false);
  });
});
