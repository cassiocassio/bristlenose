import { describe, expect, it } from "vitest";

import { knownPeopleOf, stateAfter } from "./speakerPicking";
import type { SessionsListResponse } from "./types";

const study = (speakers: Array<Record<string, unknown>>[]): SessionsListResponse =>
  ({ sessions: speakers.map((sp, i) => ({ session_id: `s${i + 1}`, speakers: sp })) }) as unknown as SessionsListResponse;

describe("knownPeopleOf", () => {
  it("a person is confirmed if anyone said yes to them in any session (§J8.10)", () => {
    const known = knownPeopleOf(study([
      [{ speaker_code: "m1", name: "Kerri", person: "id-k", name_confirmed: false }],
      [{ speaker_code: "m1", name: "Kerri", person: "id-k", name_confirmed: true }],
      [{ speaker_code: "m2", name: "Dana", person: "id-d", name_confirmed: false }],
    ]));
    expect(known.moderator.map((r) => [r.name, r.confirmed])).toEqual([["Kerri", true], ["Dana", false]]);
  });

  it("a missing flag reads as confirmed, as the grid draws it", () => {
    const known = knownPeopleOf(study([[{ speaker_code: "m1", name: "Sarah", person: "id-s" }]]));
    expect(known.moderator[0].confirmed).toBe(true);
  });
});

describe("stateAfter", () => {
  const before = { full_name: "Martin Storey", short_name: "Martin", confirmed: false, person: "id-m" };

  it("names each act's next state (§J8)", () => {
    expect(stateAfter({ kind: "confirm" }, before)).toEqual({ ...before, confirmed: true });
    expect(stateAfter({ kind: "clear" }, before)).toEqual({ full_name: "", short_name: "", confirmed: false });
    expect(stateAfter({ kind: "name", name: "Martyn" }, before)).toEqual({ ...before, short_name: "Martyn", confirmed: true });
    expect(stateAfter({ kind: "new", name: "Mike" }, before, () => "id-new")).toEqual({
      person: "id-new", create: true, full_name: "Mike", short_name: "Mike", confirmed: true,
    });
  });
});
