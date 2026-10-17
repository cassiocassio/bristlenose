import { describe, expect, it, vi, afterEach } from "vitest";
import { discussionArrival, discussionPath, questionsAsked } from "./discussionLinks";
import type { DiscussionData, DiscussionTurn } from "./types";

const exportState = vi.hoisted(() => ({ on: false }));
vi.mock("../../utils/exportData", async (orig) => ({
  ...(await orig<typeof import("../../utils/exportData")>()),
  isExportMode: () => exportState.on,
}));
import { appQuery } from "../../utils/appQuery";

const turn = (id: string, session: string, sec: number, item: string | null): DiscussionTurn => ({
  id, session, sec, time: "", text: "", kind: item ? "planned" : "chat", item,
});
const item = (id: string, terse: string) => ({
  id, terse, verbatim: terse, source: "planned" as const, placed: "" as const, role: "core" as const, asks: [],
});
function record(turns: DiscussionTurn[]): DiscussionData {
  return {
    version: 1, guide: true, sessions: [], spine: [], quotes: [], turns,
    sections: [{ id: "s1", title: "Objects", heading: "Objects", kind: "questions", origin: "planned",
      items: [item("s1.1", "Objects with meaning"), item("s1.2", "How they found it")] }],
    standalone: [item("a4", "Wrapping up")],
  };
}
// Paragraphs every 10 s.
const at = (sec: number) => (sec >= 0 && sec < 100 ? Math.floor(sec / 10) : null);

describe("questionsAsked", () => {
  it("puts each question of the guide in the paragraph it was asked in, for this session", () => {
    const asked = questionsAsked(record([
      turn("s1@00:22", "s1", 22, "s1.1"), turn("s2@00:05", "s2", 5, "s1.1"), turn("s1@01:52", "s1", 52, "s1.2"),
    ]), "s1", at);
    expect([...asked.keys()]).toEqual([2, 5]);
    expect(asked.get(2)).toEqual([{ item: "s1.1", topic: "Objects with meaning", turn: "s1@00:22" }]);
    expect(asked.get(5)![0].topic).toBe("How they found it");
  });

  it("gives a turn that asks nothing of the guide no mark, and names a standalone item", () => {
    const asked = questionsAsked(record([turn("s1@00:03", "s1", 3, null), turn("s1@01:30", "s1", 30, "a4")]), "s1", at);
    expect([...asked.keys()]).toEqual([3]);
    expect(asked.get(3)![0].topic).toBe("Wrapping up");
  });

  it("marks one item once in a paragraph, at its first asking", () => {
    const asked = questionsAsked(record([turn("s1@00:24", "s1", 24, "s1.1"), turn("s1@00:21", "s1", 21, "s1.1")]), "s1", at);
    expect(asked.get(2)).toEqual([{ item: "s1.1", topic: "Objects with meaning", turn: "s1@00:21" }]);
  });
});

describe("the arrival address", () => {
  afterEach(() => {
    exportState.on = false;
    window.history.replaceState(null, "", "/");
  });

  it("round-trips an item and a turn", () => {
    const path = discussionPath("s1.2", "s1@01:52");
    expect(path).toBe("/report/discussion/?item=s1.2&turn=s1%4001%3A52");
    window.history.replaceState(null, "", path);
    expect(discussionArrival(appQuery())).toEqual({ item: "s1.2", turn: "s1@01:52" });
  });

  it("is read from the hash in an export, whose router keeps the address there", () => {
    exportState.on = true;
    window.history.replaceState(null, "", `/report.html#${discussionPath("s1.2", "s1@01:52")}`);
    expect(discussionArrival(appQuery())).toEqual({ item: "s1.2", turn: "s1@01:52" });
  });

  it("asks for nothing without both halves", () => {
    window.history.replaceState(null, "", "/report/discussion/?item=s1.2");
    expect(discussionArrival(appQuery())).toBeNull();
  });
});
