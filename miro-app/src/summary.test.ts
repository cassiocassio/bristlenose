import { describe, expect, it } from "vitest";
import type { BoardPlan } from "./layout";
import { failure, summary } from "./summary";

const plan = (over: Partial<BoardPlan> = {}): BoardPlan =>
  ({ expectedQuotes: 8, droppedLinks: 0, unknownColours: 0, ...over }) as BoardPlan;

describe("the summary", () => {
  it("says built only when every quote was drawn", () => {
    expect(summary(plan(), 8)).toBe("Board built: 8 quotes.");
    expect(summary(plan({ expectedQuotes: 1 }), 1)).toBe("Board built: 1 quote.");
    expect(summary(plan(), 5)).toBe("Built 5 of 8 quotes — some are missing.");
  });

  it("counts dropped links and unknown colours in the right number", () => {
    expect(summary(plan({ droppedLinks: 1 }), 8)).toContain("1 clip link wasn't a web address and was left out.");
    expect(summary(plan({ droppedLinks: 2 }), 8)).toContain("2 clip links weren't web addresses and were left out.");
    expect(summary(plan({ unknownColours: 1 }), 8)).toContain("1 sticky had a colour Miro doesn't have and is yellow.");
    expect(summary(plan({ unknownColours: 3 }), 8)).toContain("3 stickies had a colour Miro doesn't have and are yellow.");
  });

  it("gives Miro's own reason when a build fails, not a guess", () => {
    expect(failure(plan(), 3, "Miro SDK is not connected")).toBe(
      "Stopped after 3 of 8 quotes. What was drawn stays on the board. Miro said: Miro SDK is not connected",
    );
  });
});
