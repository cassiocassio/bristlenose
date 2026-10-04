import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { getUndoState, redo, resetUndoStore, undo } from "../contexts/UndoStore";
import { getPeople, sendPut } from "./api";
import {
  PEOPLE_CHANGED_EVENT,
  actionFor,
  nameSpeaker,
  resetSpeakerNameQueue,
  type PeopleChangedDetail,
  type SpeakerNameState,
} from "./speakerNames";

vi.mock("./api", async (importOriginal) => {
  const real = await importOriginal<typeof import("./api")>();
  return { ...real, getPeople: vi.fn(), sendPut: vi.fn() };
});

const putMock = vi.mocked(sendPut);
const peopleMock = vi.mocked(getPeople);

const proposed: SpeakerNameState = { full_name: "Martin Storey", short_name: "Martin", confirmed: false };
const picked: SpeakerNameState = { full_name: "Jo Lee", short_name: "Jo Lee", confirmed: true };

/** Every PUT the module made, in order, as [path, body]. */
const puts = () => putMock.mock.calls.map(([path, body]) => [path, body]);

beforeEach(() => {
  putMock.mockReset().mockResolvedValue(undefined);
  peopleMock.mockReset();
});

afterEach(() => {
  resetUndoStore();
  resetSpeakerNameQueue();
});

describe("nameSpeaker — a moderator", () => {
  it("writes the whole state in one per-session request", async () => {
    await nameSpeaker({ sessionId: "s1", code: "m1", before: proposed, after: picked });
    expect(puts()).toEqual([["/sessions/s1/speakers/m1", picked]]);
  });

  it("undo restores both names and returns the slot to proposed", async () => {
    await nameSpeaker({ sessionId: "s1", code: "m1", before: proposed, after: picked });
    await undo();
    expect(puts()[1]).toEqual(["/sessions/s1/speakers/m1", proposed]);
  });

  it("redo writes the pick again", async () => {
    await nameSpeaker({ sessionId: "s1", code: "m1", before: proposed, after: picked });
    await undo();
    await redo();
    expect(puts()[2]).toEqual(["/sessions/s1/speakers/m1", picked]);
  });

  it("an undo pressed before the pick has landed waits for it", async () => {
    let land!: () => void;
    putMock.mockImplementationOnce(() => new Promise<void>((r) => { land = r; }));
    void nameSpeaker({ sessionId: "s1", code: "m1", before: proposed, after: picked });
    const undone = undo();
    await Promise.resolve();
    expect(putMock).toHaveBeenCalledTimes(1);
    land();
    await undone;
    expect(puts().map(([, body]) => body)).toEqual([picked, proposed]);
  });

  it("tells views what the slot now holds on undo and redo", async () => {
    const seen: PeopleChangedDetail[] = [];
    const on = (e: Event) => seen.push((e as CustomEvent<PeopleChangedDetail>).detail);
    window.addEventListener(PEOPLE_CHANGED_EVENT, on);
    await nameSpeaker({ sessionId: "s2", code: "o1", before: proposed, after: picked });
    expect(seen).toEqual([]);
    await undo();
    await redo();
    window.removeEventListener(PEOPLE_CHANGED_EVENT, on);
    expect(seen).toEqual([
      { sessionId: "s2", code: "o1", state: proposed },
      { sessionId: "s2", code: "o1", state: picked },
    ]);
  });
});

describe("nameSpeaker — a full name the caller does not know", () => {
  it("is left as stored, not blanked", async () => {
    const before = { short_name: "Jo", confirmed: false };
    const after = { short_name: "Joanna", confirmed: true };
    await nameSpeaker({ sessionId: "s1", code: "m1", before, after });
    await undo();
    // JSON drops the undefined field, so the server leaves full_name alone.
    expect(puts().map(([, body]) => JSON.parse(JSON.stringify(body)))).toEqual([after, before]);
  });

  it("a participant keeps the full name /people holds", async () => {
    peopleMock.mockResolvedValue({ p1: { full_name: "Ann Archer", short_name: "Ann", role: "" } });
    await nameSpeaker({
      sessionId: "s1", code: "p1",
      before: { short_name: "Ann", confirmed: false },
      after: { short_name: "Annie", confirmed: true },
    });
    expect(puts()[0]).toEqual([
      "/people", { p1: { full_name: "Ann Archer", short_name: "Annie", role: "" } },
    ]);
  });
});

describe("nameSpeaker — a participant", () => {
  const people = {
    p1: { full_name: "Ann Archer", short_name: "Ann", role: "" },
    p2: { full_name: "Bea Baker", short_name: "Bea", role: "" },
  };
  const ann: SpeakerNameState = { full_name: "Ann Archer", short_name: "Ann", confirmed: false };
  const annie: SpeakerNameState = { full_name: "Ann Archer", short_name: "Annie", confirmed: true };

  it("renames through /people, then sets the flag on the slot", async () => {
    peopleMock.mockResolvedValue(structuredClone(people));
    await nameSpeaker({ sessionId: "s1", code: "p1", before: ann, after: annie });
    expect(puts()).toEqual([
      ["/people", { ...people, p1: { ...people.p1, short_name: "Annie" } }],
      ["/sessions/s1/speakers/p1", { confirmed: true }],
    ]);
  });

  it("undo writes only this participant back, onto the map as it is now", async () => {
    peopleMock.mockResolvedValueOnce(structuredClone(people));
    await nameSpeaker({ sessionId: "s1", code: "p1", before: ann, after: annie });
    // Meanwhile p2 was renamed by someone else's write.
    const now = { p1: { ...people.p1, short_name: "Annie" }, p2: { ...people.p2, short_name: "Beatrice" } };
    peopleMock.mockResolvedValueOnce(structuredClone(now));
    await undo();
    expect(puts().slice(2)).toEqual([
      ["/people", { ...now, p1: { ...people.p1, short_name: "Ann" } }],
      ["/sessions/s1/speakers/p1", { confirmed: false }],
    ]);
  });

  it("a confirm alone touches only the flag", async () => {
    peopleMock.mockResolvedValue(structuredClone(people));
    await nameSpeaker({ sessionId: "s1", code: "p1", before: ann, after: { ...ann, confirmed: true } });
    expect(puts()).toEqual([["/sessions/s1/speakers/p1", { confirmed: true }]]);
  });
});

describe("nameSpeaker — the undo entry", () => {
  it("names the act for the Edit menu", async () => {
    await nameSpeaker({ sessionId: "s1", code: "m1", before: proposed, after: picked });
    expect(getUndoState().undoAction).toBe("renameModerator");
  });

  it("records nothing when nothing changes", async () => {
    await nameSpeaker({ sessionId: "s1", code: "m1", before: picked, after: picked });
    expect(putMock).not.toHaveBeenCalled();
    expect(getUndoState().canUndo).toBe(false);
  });

  it.each([
    ["m1", "renameModerator"],
    ["o2", "renameObserver"],
    ["p3", "renameParticipant"],
  ])("a rename of %s is %s", (code, key) => {
    expect(actionFor(code, proposed, picked)).toBe(key);
  });

  it("a confirm is a confirm whatever the role", () => {
    expect(actionFor("m1", proposed, { ...proposed, confirmed: true })).toBe(
      "confirmName",
    );
  });
});
