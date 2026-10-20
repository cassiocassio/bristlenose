/**
 * A write that fails takes the screen back to what the server holds (R7).
 *
 * "Couldn't save" used to appear while the star, hide, tag or edit stayed
 * drawn as if it had saved. The rollback reverts only what still shows the
 * gesture's value, because a later gesture is the researcher's latest word.
 */
import type { QuoteResponse, TagResponse } from "../utils/types";
import {
  HIDE_DURATION,
  addTag,
  commitEdit,
  deleteBadge,
  getQuotesSnapshot,
  hideQuotes,
  initFromQuotes,
  removeTag,
  resetStore,
  restoreBadges,
  setStarred,
  unhideQuotes,
} from "./QuotesContext";
import { resetUndoStore, undo } from "./UndoStore";
import { _resetExportCache } from "../utils/exportData";

vi.mock("../utils/api", () => ({
  patchHidden: vi.fn(() => Promise.resolve()),
  patchStarred: vi.fn(() => Promise.resolve()),
  patchEdits: vi.fn(() => Promise.resolve()),
  patchTags: vi.fn(() => Promise.resolve()),
  patchDeletedBadges: vi.fn(() => Promise.resolve()),
  acceptProposal: vi.fn().mockResolvedValue(undefined),
  denyProposal: vi.fn().mockResolvedValue(undefined),
}));

import {
  patchDeletedBadges,
  patchEdits,
  patchHidden,
  patchStarred,
  patchTags,
} from "../utils/api";

function quote(overrides: Partial<QuoteResponse> = {}): QuoteResponse {
  return {
    dom_id: "q1",
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
    tags: [],
    deleted_badges: [],
    proposed_tags: [],
    segment_index: 0,
    ...overrides,
  } as QuoteResponse;
}

const tag = (name: string): TagResponse => ({
  name, codebook_group: "G", colour_set: "ux", colour_index: 0,
});

/** The next write to this helper fails, as `sendWrite` rejects after its toast. */
function failNext(fn: unknown): void {
  vi.mocked(fn as () => Promise<void>).mockImplementationOnce(() =>
    Promise.reject(new Error("refused")),
  );
}

/** Let a rejected write's rollback run. */
const settle = () => new Promise((r) => setTimeout(r, 0));

beforeEach(() => {
  resetStore();
  resetUndoStore();
  vi.clearAllMocks();
  _resetExportCache();
});

describe("a failed write takes the screen back", () => {
  it("a star", async () => {
    initFromQuotes([quote()]);
    failNext(patchStarred);
    setStarred(["q1"], true);
    expect(getQuotesSnapshot().starred.q1).toBe(true);
    await settle();
    expect(getQuotesSnapshot().starred.q1).toBeUndefined();
  });

  it("a restore from hidden", async () => {
    initFromQuotes([quote({ is_hidden: true })]);
    failNext(patchHidden);
    unhideQuotes(["q1"]);
    await settle();
    expect(getQuotesSnapshot().hidden.q1).toBe(true);
  });

  it("a hide, once it has landed", async () => {
    vi.useFakeTimers();
    try {
      initFromQuotes([quote()]);
      failNext(patchHidden);
      hideQuotes(["q1"]);
      vi.advanceTimersByTime(HIDE_DURATION);
      expect(getQuotesSnapshot().hidden.q1).toBe(true);
      await vi.runAllTimersAsync();
      expect(getQuotesSnapshot().hidden.q1).toBeUndefined();
    } finally {
      vi.useRealTimers();
    }
  });

  it("an edit, to the words before it", async () => {
    initFromQuotes([quote({ edited_text: "first" })]);
    failNext(patchEdits);
    commitEdit("q1", "second");
    await settle();
    expect(getQuotesSnapshot().edits.q1).toBe("first");
  });

  it("a tag added", async () => {
    initFromQuotes([quote()]);
    failNext(patchTags);
    addTag("q1", tag("Trust"));
    await settle();
    expect(getQuotesSnapshot().tags.q1).toBeUndefined();
  });

  it("a tag removed, back in its place", async () => {
    initFromQuotes([quote({ tags: [tag("A"), tag("B"), tag("C")] })]);
    failNext(patchTags);
    removeTag("q1", "B");
    await settle();
    expect(getQuotesSnapshot().tags.q1.map((t) => t.name)).toEqual(["A", "B", "C"]);
  });

  it("a badge deleted, and a restore of the badges", async () => {
    initFromQuotes([quote()]);
    failNext(patchDeletedBadges);
    deleteBadge("q1", "negative");
    await settle();
    expect(getQuotesSnapshot().deletedBadges.q1).toBeUndefined();

    initFromQuotes([quote({ deleted_badges: ["negative"] })], true);
    failNext(patchDeletedBadges);
    restoreBadges("q1");
    await settle();
    expect(getQuotesSnapshot().deletedBadges.q1).toEqual(["negative"]);
  });
});

describe("a rollback leaves a later gesture alone", () => {
  it("a star that failed after its unstar was made stays unstarred", async () => {
    initFromQuotes([quote()]);
    failNext(patchStarred);
    setStarred(["q1"], true);
    setStarred(["q1"], false);
    await settle();
    expect(getQuotesSnapshot().starred.q1).toBeUndefined();
  });

  it("a star that failed, then an unstar and a star again, stays starred", async () => {
    initFromQuotes([quote()]);
    failNext(patchStarred);
    setStarred(["q1"], true);
    setStarred(["q1"], false);
    setStarred(["q1"], true);
    await settle();
    expect(getQuotesSnapshot().starred.q1).toBe(true);
  });

  it("a tag add that failed, then a remove and an add again, stays", async () => {
    initFromQuotes([quote()]);
    failNext(patchTags);
    addTag("q1", tag("Trust"));
    removeTag("q1", "Trust");
    addTag("q1", tag("Trust"));
    await settle();
    expect(getQuotesSnapshot().tags.q1.map((t) => t.name)).toEqual(["Trust"]);
  });

  it("a failed tag add leaves the quote's other tags", async () => {
    initFromQuotes([quote({ tags: [tag("A")] })]);
    failNext(patchTags);
    addTag("q1", tag("Trust"));
    addTag("q1", tag("Other"));
    await settle();
    expect(getQuotesSnapshot().tags.q1.map((t) => t.name)).toEqual(["A", "Other"]);
  });

  it("an edit that failed after a newer edit keeps the newer words", async () => {
    initFromQuotes([quote()]);
    failNext(patchEdits);
    commitEdit("q1", "one");
    commitEdit("q1", "two");
    await settle();
    expect(getQuotesSnapshot().edits.q1).toBe("two");
  });

  it("undo of a gesture that never landed sends nothing", async () => {
    initFromQuotes([quote()]);
    failNext(patchStarred);
    setStarred(["q1"], true);
    await settle();
    vi.mocked(patchStarred).mockClear();
    await undo();
    expect(patchStarred).not.toHaveBeenCalled();
    expect(getQuotesSnapshot().starred.q1).toBeUndefined();
  });
});
