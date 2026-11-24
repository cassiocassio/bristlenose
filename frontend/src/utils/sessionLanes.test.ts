import { describe, expect, it } from "vitest";
import { isTeamTurn, sessionLanes } from "./sessionLanes";

const turn = (speaker: string, team?: boolean) => ({ t0: 0, t1: 10, speaker, colour: null, ...(team === undefined ? {} : { team }) });

describe("sessionLanes", () => {
  it("says which lanes a session has, from its own data", () => {
    expect(sessionLanes({ sections: [], turns: [turn("p1")], quotes: [] })).toEqual({ sections: false, team: false, most: 2 });
    expect(sessionLanes({
      sections: [{ t0: 0, label: "Intro" }],
      turns: [turn("m1"), turn("p1")],
      quotes: [{ theme: null }, { theme: "Trust" }],
    } as never)).toEqual({ sections: true, team: true, most: 5 });
  });

  it("takes the server's word on a turn's role over its code, and the displayed code otherwise", () => {
    expect(isTeamTurn(turn("p1", true))).toBe(true);
    expect(isTeamTurn(turn("m1", false))).toBe(false);
    expect(isTeamTurn(turn("s2"), (slot) => (slot === "s2" ? "o1" : slot))).toBe(true);
  });
});
